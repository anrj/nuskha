"""HTTP API for the journey: upload -> index -> ask -> cited answer -> open source."""
import hashlib
import hmac
import mimetypes
import re
import time
import uuid
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from . import analytics, db
from .answer import answer
from .config import settings
from .embed import embed
from .georgian import normalize
from .ingest.chunk import chunk_pages
from .ingest.parse import SUPPORTED, parse
from .search import search
from .files import file_store
from .providers import ProviderError


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield
    db.close_db()


app = FastAPI(title="Nuskha engine", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.web_origins, allow_methods=["*"], allow_headers=["*"],
)

@app.exception_handler(ProviderError)
async def provider_error(_, exc: ProviderError):
    print(f"AI provider error: {exc}", flush=True)  # visible in the uvicorn terminal
    return JSONResponse({"detail": str(exc)}, status_code=502)


_OWNER = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _owner(user_id: str | None) -> str:
    """Anonymous per-browser id (no accounts in the MVP). Also the PostHog distinct_id."""
    if not user_id or not _OWNER.match(user_id):
        raise HTTPException(400, "Missing or invalid X-User-Id header")
    return user_id


_DOC_COLS = "id, filename, content_type, size_bytes, status, error, page_count, chunk_count, georgian_ratio, legacy_font_fixed, created_at"


@app.get("/health")
def health():
    with db.conn() as c:
        c.execute("SELECT 1")
    return {"ok": True, "embed": settings.embed_provider, "answers": settings.answers}


@app.get("/documents")
def list_documents(x_user_id: str | None = Header(None)):
    owner = _owner(x_user_id)
    with db.conn() as c:
        return c.execute(f"SELECT {_DOC_COLS} FROM documents WHERE owner_id = %s ORDER BY created_at DESC", (owner,)).fetchall()


@app.post("/documents")
def upload_document(file: UploadFile = File(...), x_user_id: str | None = Header(None)):
    owner = _owner(x_user_id)
    filename = file.filename or "document"
    ext = filename[filename.rfind("."):].lower() if "." in filename else ""
    if ext not in SUPPORTED:
        raise HTTPException(415, f"Unsupported file type. Supported: {', '.join(SUPPORTED)}")
    data = file.file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {settings.max_upload_mb} MB)")
    content_type = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    doc_id = str(uuid.uuid4())
    key = f"{owner}/{doc_id}{ext}"
    file_store.put(key, data, content_type)
    with db.conn() as c:
        c.execute(
            "INSERT INTO documents (id, owner_id, filename, content_type, size_bytes, storage_key) VALUES (%s,%s,%s,%s,%s,%s)",
            (doc_id, owner, filename, content_type, len(data), key),
        )
    analytics.capture(owner, "DOCUMENT_UPLOADED", {"document_id": doc_id, "file_type": ext.lstrip("."), "size_bytes": len(data)})

    started = time.monotonic()
    try:
        parsed = parse(filename, data)
        chunks = chunk_pages(parsed.pages)
        if not chunks:
            raise ValueError("No text found. Scanned PDFs need OCR, which isn't supported yet.")
        vectors = embed([normalize(ch.text) for ch in chunks])
        with db.conn() as c:
            with c.cursor() as cur:
                cur.executemany(
                    "INSERT INTO chunks (document_id, page, ord, text, norm, embedding) VALUES (%s,%s,%s,%s,%s,%s)",
                    [(doc_id, ch.page, i, ch.text, normalize(ch.text), np.array(v)) for i, (ch, v) in enumerate(zip(chunks, vectors))],
                )
            c.execute(
                "UPDATE documents SET status='ready', page_count=%s, chunk_count=%s, georgian_ratio=%s, legacy_font_fixed=%s WHERE id=%s",
                (len(parsed.pages), len(chunks), round(parsed.georgian_ratio, 3), parsed.legacy_font_fixed, doc_id),
            )
        analytics.capture(owner, "DOCUMENT_INDEXED", {
            "document_id": doc_id, "page_count": len(parsed.pages), "chunk_count": len(chunks),
            "georgian_ratio": round(parsed.georgian_ratio, 3), "legacy_font_fixed": parsed.legacy_font_fixed,
            "duration_ms": int((time.monotonic() - started) * 1000),
        })
    except Exception as e:  # keep the row so the user sees why it failed
        with db.conn() as c:
            c.execute("UPDATE documents SET status='failed', error=%s WHERE id=%s", (str(e)[:500], doc_id))

    with db.conn() as c:
        return c.execute(f"SELECT {_DOC_COLS} FROM documents WHERE id = %s", (doc_id,)).fetchone()


def _file_sig(doc_id: str, exp: int) -> str:
    msg = f"{doc_id}.{exp}".encode()
    return hmac.new(settings.file_url_secret.encode(), msg, hashlib.sha256).hexdigest()


def _file_url(doc_id: str) -> str:
    """A link to the original that expires and names no user: it ends up in history, logs and Referer headers."""
    exp = int(time.time()) + settings.file_url_ttl_s
    return f"/documents/{doc_id}/file?exp={exp}&sig={_file_sig(doc_id, exp)}"


@app.get("/documents/{doc_id}/file")
def get_file(doc_id: uuid.UUID, exp: int, sig: str):
    """Opened in a new tab (no custom headers possible), so access comes from the signed link."""
    if exp < time.time() or not hmac.compare_digest(sig, _file_sig(str(doc_id), exp)):
        raise HTTPException(403, "This link has expired. Open the source again from the answer.")
    with db.conn() as c:
        row = c.execute("SELECT filename, content_type, storage_key FROM documents WHERE id=%s", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    disposition = "inline" if row["content_type"] in ("application/pdf", "text/plain", "text/markdown", "text/csv") else "attachment"
    return Response(
        file_store.get(row["storage_key"]), media_type=row["content_type"],
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{_quote(row['filename'])}",
            "Referrer-Policy": "no-referrer", "Cache-Control": "private, no-store",
        },
    )


@app.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: uuid.UUID, x_user_id: str | None = Header(None)):
    """Removes the document, its chunks and source opens (FK cascade), then the original file."""
    owner = _owner(x_user_id)
    with db.conn() as c:
        row = c.execute(
            "DELETE FROM documents WHERE id=%s AND owner_id=%s RETURNING storage_key", (doc_id, owner)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    try:
        file_store.delete(row["storage_key"])
    except Exception as e:  # the row is gone, so the file is unreachable; log and move on
        print(f"Could not delete stored file {row['storage_key']}: {e}", flush=True)
    return Response(status_code=204)


def _quote(name: str) -> str:
    from urllib.parse import quote

    return quote(name)


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


@app.post("/ask")
def ask(body: AskIn, x_user_id: str | None = Header(None)):
    owner = _owner(x_user_id)
    with db.conn() as c:
        recent = c.execute(
            "SELECT count(*) AS n FROM questions WHERE owner_id = %s AND created_at > now() - interval '1 hour'", (owner,)
        ).fetchone()["n"]
    if recent >= settings.max_questions_per_hour:
        raise HTTPException(429, "Too many questions, try again later")
    started = time.monotonic()
    hits = search(owner, body.question)
    text, citations, mode = answer(body.question, hits)
    latency = int((time.monotonic() - started) * 1000)
    with db.conn() as c:
        qid = c.execute(
            "INSERT INTO questions (owner_id, question, answer, mode, citations, latency_ms) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (owner, body.question, text, mode, Jsonb(citations), latency),
        ).fetchone()["id"]
    analytics.capture(owner, "ANSWER_RETURNED", {
        "question_id": str(qid), "citation_count": len(citations), "latency_ms": latency, "mode": mode,
    })
    return {"question_id": qid, "answer": text, "citations": citations, "mode": mode, "latency_ms": latency}


class SourceOpenIn(BaseModel):
    question_id: uuid.UUID
    chunk_id: int


@app.post("/source-opens")
def open_source(body: SourceOpenIn, x_user_id: str | None = Header(None)):
    """Records the north-star action. The browser fires `source_opened` only after this returns 200."""
    owner = _owner(x_user_id)
    with db.conn() as c:
        row = c.execute(
            "SELECT c.document_id, c.page FROM chunks c JOIN documents d ON d.id = c.document_id "
            "JOIN questions q ON q.id = %s AND q.owner_id = %s WHERE c.id = %s AND d.owner_id = %s",
            (body.question_id, owner, body.chunk_id, owner),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Source not found")
        sid = c.execute(
            "INSERT INTO source_opens (owner_id, question_id, document_id, chunk_id, page) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (owner, body.question_id, row["document_id"], body.chunk_id, row["page"]),
        ).fetchone()["id"]
    return {
        "id": sid, "document_id": row["document_id"], "page": row["page"],
        "url": f"{_file_url(str(row['document_id']))}#page={row['page']}",
    }
