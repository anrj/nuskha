# Nuskha (ნუსხა)

https://nuskha.tuxa.ge/
Document & file storage, retrieval, management, organization system.
Upload Georgian office documents (contracts, invoices, HR orders), ask a question in Georgian or Latin-typed Georgian, and get an answer that cites the exact file and page.

| | |
|---|---|
| Live product | _add the production URL here_ |
| PostHog dashboard | _add the shared no-login link here_ |

## Journey (MVP)

1. Open the app → 2. upload a document (`document_uploaded`) → 3. indexed (`document_indexed`) →
4. ask a question (`question_asked`) → 5. answer with citations (`answer_returned`) → 6. **open a cited source at its page (`source_opened`, north star)**

Event names live in one file, [`app/events.json`](app/events.json), read by both the engine and the web app.

## Layout

```
app/
  events.json            analytics event names (single source of truth)
  engine/                Python · FastAPI · Postgres (pgvector + pg_trgm)
    nuskha/
      georgian/          normalization, Mtavruli folding, pre-Unicode (keyboard-layout) text → Unicode by content, translit  ← the Georgian edge
      ingest/            parse (PDF, Word/Excel/PowerPoint incl. 97–2003, ODT, RTF, CSV/TSV, HTML, TXT/MD; legacy-font aware) + chunking
      embed.py           embeddings: any OpenAI-compatible API (Gemini default) | ngram (offline)
      search.py          hybrid search: vectors + trigram keywords over all query variants, fused with RRF
      answer.py          cited answers: any OpenAI-compatible LLM (Gemini default) | best-passage fallback
      files.py           original files: local disk | S3/R2
      api.py             HTTP endpoints for the journey
      schema.sql         tables, applied automatically on startup
    scripts/make_samples.py   fictional Georgian demo documents
    tests/                     Georgian module, parsing, full API journey
  web/                   Bun · Vite · Solid 2 · Tailwind 4
    src/api.ts           typed API client
    src/analytics.ts     PostHog (lazy, fires after the server confirms)
    src/components/      UploadPanel, DocumentList, AskPanel, AnswerView, ui/
```

## Run locally

Needs [uv](https://docs.astral.sh/uv/), [Bun](https://bun.sh) and a Postgres URL (a Neon branch works).

```bash
cp .env.example .env            # set DATABASE_URL (Neon) and GEMINI_API_KEY (aistudio.google.com, free)

# engine → http://localhost:8000
cd app/engine
uv sync
uv run python scripts/make_samples.py        # demo docs → app/samples/
uv run uvicorn nuskha.api:app --reload

# web → http://localhost:5173 (second terminal)
cd app/web
cp .env.example .env.local
bun install
bun run dev
```

Without an LLM key the app still completes the journey: it shows the best matching passage with its citation.
Offline development without any key: `EMBED_PROVIDER=ngram`.

**Supported files:** PDF, Word (.docx, .doc), Excel (.xlsx, .xls), PowerPoint (.pptx, .ppt), OpenDocument (.odt), RTF, CSV/TSV, HTML, TXT, Markdown.
Old 97–2003 files are read in pure Python; if LibreOffice (`soffice`) is installed, files those readers can't handle are converted first.
Files that are really HTML/CSV/RTF under a .xls/.doc name (common in accounting/bank exports) are detected by content.
Google Docs/Sheets/Slides: *File → Download* as .docx/.odt, .xlsx/.csv or .pptx.
Citations point to the page (PDF), slide (PowerPoint) or sheet (Excel).

## Test

```bash
cd app/engine
uv run pytest                                             # Georgian + parsing tests
TEST_DATABASE_URL=postgresql://... uv run pytest          # + full journey (use a Neon dev branch, it writes rows)
```

## Reconcile (north star)

```sql
SELECT count(*) FROM source_opens WHERE owner_id NOT LIKE 'test-%';  -- must equal PostHog `source_opened` count
```

## Deploy

- **Engine:** Render via [`render.yaml`](render.yaml) (or Railway/Fly), `DATABASE_URL` from Neon, originals in Cloudflare R2 (`FILE_STORE=s3`). Set `FILE_URL_SECRET` (signs the short-lived links that open original files; `render.yaml` generates one).
- **Web:** Vercel or Cloudflare Pages, root `app/web`, build `bun run build`, output `dist`, set `VITE_API_URL` and `VITE_POSTHOG_KEY`.
- Secrets only in host environment variables.
