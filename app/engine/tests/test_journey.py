"""End-to-end journey against a real Postgres with pgvector.

  TEST_DATABASE_URL=postgresql://... uv run pytest tests/test_journey.py -v

Use a Neon dev branch, never production: the test writes rows.
"""
import os
import uuid

import pytest

DB = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB, reason="set TEST_DATABASE_URL to run the end-to-end journey")


@pytest.fixture(scope="module")
def client(samples):
    from fastapi.testclient import TestClient

    from nuskha.api import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def user():
    return {"X-User-Id": f"test-{uuid.uuid4().hex[:12]}"}


def _upload(client, user, samples, name):
    with open(samples / name, "rb") as f:
        r = client.post("/documents", files={"file": (name, f)}, headers=user)
    assert r.status_code == 200, r.text
    return r.json()


def test_upload_index_ask_open(client, user, samples):
    names = ("contract.pdf", "invoice.pdf", "order.docx", "employees.csv", "vacations.xlsx")
    docs = {n: _upload(client, user, samples, n) for n in names}
    assert all(d["status"] == "ready" for d in docs.values()), docs
    assert docs["order.docx"]["legacy_font_fixed"] is True
    assert docs["vacations.xlsx"]["legacy_font_fixed"] is True and docs["vacations.xlsx"]["page_count"] == 2
    assert docs["contract.pdf"]["page_count"] == 2

    listed = client.get("/documents", headers=user).json()
    assert {d["filename"] for d in listed} == set(docs)

    cases = [
        ("რამდენია ნინო ბერიძის ხელფასი?", {("contract.pdf", 1), ("employees.csv", 1)}),  # both state it
        ("კონფიდენციალურობა", "contract.pdf", 2),
        ("სულ გადასახდელი თანხა ქართული ქაღალდი", "invoice.pdf", 1),
        ("gadaxdis vada", "invoice.pdf", 1),                       # Latin-typed Georgian
        ("გიორგი კაპანაძის შვებულება", "order.docx", 1),           # came from a legacy-font file
        ("shvebuleba dekembri", "order.docx", 1),
        ("თამარ ლომიძე HR მენეჯერი ხელფასი", "employees.csv", 1),   # CSV row
        ("ბიულეტენი ნინო ბერიძე", "vacations.xlsx", 2),             # 2nd sheet, legacy font
    ]
    for question, *expected in cases:
        accepted = expected[0] if isinstance(expected[0], set) else {tuple(expected)}
        r = client.post("/ask", json={"question": question}, headers=user)
        assert r.status_code == 200, r.text
        body = r.json()
        top = body["citations"][0]
        assert (top["filename"], top["page"]) in accepted, (question, body["citations"])

    opened = client.post("/source-opens", json={"question_id": body["question_id"], "chunk_id": top["chunk_id"]}, headers=user)
    assert opened.status_code == 200, opened.text
    url = opened.json()["url"]
    assert user["X-User-Id"] not in url  # the owner id must never appear in a link
    f = client.get(url.split("#")[0])
    assert f.status_code == 200 and len(f.content) > 0
    path = url.split("?")[0]
    assert client.get(f"{path}?u={user['X-User-Id']}").status_code == 422  # owner-id links no longer work


def test_owner_isolation(client, samples):
    other = {"X-User-Id": f"test-{uuid.uuid4().hex[:12]}"}
    assert client.get("/documents", headers=other).json() == []
    r = client.post("/ask", json={"question": "ხელშეკრულება"}, headers=other).json()
    assert r["citations"] == [] and r["mode"] == "none"


def test_rejects_bad_requests(client, user):
    assert client.get("/documents").status_code == 400
    r = client.post("/documents", files={"file": ("x.exe", b"MZ")}, headers=user)
    assert r.status_code == 415
    r = client.post("/documents", files={"file": ("broken.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 600)}, headers=user)
    assert r.status_code == 200 and r.json()["status"] == "failed" and ".docx" in r.json()["error"]


def test_delete_document(client, samples):
    owner = {"X-User-Id": f"test-{uuid.uuid4().hex[:12]}"}
    doc = _upload(client, owner, samples, "invoice.pdf")
    other = {"X-User-Id": f"test-{uuid.uuid4().hex[:12]}"}
    assert client.delete(f"/documents/{doc['id']}", headers=other).status_code == 404  # not theirs
    assert client.delete(f"/documents/{doc['id']}", headers=owner).status_code == 204
    assert client.get("/documents", headers=owner).json() == []
    r = client.post("/ask", json={"question": "gadaxdis vada"}, headers=owner).json()
    assert r["citations"] == []
    assert client.delete(f"/documents/{doc['id']}", headers=owner).status_code == 404
