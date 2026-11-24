"""Signed links to original files. Rejections happen before any DB access, so no database is needed."""
import time
import uuid

from fastapi.testclient import TestClient

from nuskha.api import _file_sig, _file_url, app

client = TestClient(app)  # no `with`: the lifespan (DB) isn't started
DOC = str(uuid.uuid4())


def test_link_names_no_user_and_verifies():
    url = _file_url(DOC)
    exp = int(url.split("exp=")[1].split("&")[0])
    assert exp > time.time()
    assert url.endswith(f"sig={_file_sig(DOC, exp)}")


def test_tampered_signature_rejected():
    exp = int(time.time()) + 600
    sig = _file_sig(DOC, exp)
    bad = ("0" if sig[0] != "0" else "1") + sig[1:]
    assert client.get(f"/documents/{DOC}/file?exp={exp}&sig={bad}").status_code == 403


def test_signature_bound_to_document():
    exp = int(time.time()) + 600
    other = str(uuid.uuid4())
    assert client.get(f"/documents/{other}/file?exp={exp}&sig={_file_sig(DOC, exp)}").status_code == 403


def test_expired_link_rejected():
    exp = int(time.time()) - 1
    assert client.get(f"/documents/{DOC}/file?exp={exp}&sig={_file_sig(DOC, exp)}").status_code == 403


def test_extended_expiry_rejected():
    exp = int(time.time()) + 600
    sig = _file_sig(DOC, exp)
    assert client.get(f"/documents/{DOC}/file?exp={exp + 86400}&sig={sig}").status_code == 403
