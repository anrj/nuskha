import os
import sys
import tempfile
from pathlib import Path

import pytest

# Settings are read once at import time, so configure the environment before any `nuskha` import.
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
# Deterministic, offline tests. Values are SET (not removed) so the real .env can't fill them back in.
os.environ["FILES_DIR"] = tempfile.mkdtemp(prefix="nuskha-files-")
os.environ.update(EMBED_PROVIDER="ngram", GEMINI_API_KEY="", LLM_API_KEY="", EMBED_API_KEY="", POSTHOG_KEY="")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


@pytest.fixture(scope="session")
def samples(tmp_path_factory) -> Path:
    import make_samples

    try:
        make_samples.georgian_font()
    except FileNotFoundError:
        pytest.skip("no Georgian-capable font on this machine")
    out = tmp_path_factory.mktemp("samples")
    make_samples.main(out)
    return out
