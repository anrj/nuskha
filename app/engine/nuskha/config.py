"""All settings come from environment variables (.env locally, host env vars in production)."""
import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

_ENGINE, _APP, _REPO = (Path(__file__).resolve().parents[i] for i in (1, 2, 3))
for env_file in (_ENGINE / ".env", _REPO / ".env.local", _REPO / ".env"):  # `neon deploy` writes the repo-root one
    load_dotenv(env_file)


GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL"))
    web_origins: list[str] = field(default_factory=lambda: _env("WEB_ORIGINS", "http://localhost:5173").split(","))

    # One Google AI Studio key (GEMINI_API_KEY) powers both embeddings and answers by default (free tier).
    # Embeddings: "api" (any OpenAI-compatible /embeddings endpoint: Gemini, OpenAI, Mistral, Jina...)
    # or "ngram" (offline, no key; tests). Same EMBED_DIM across providers keeps the DB schema unchanged.
    embed_provider: str = field(default_factory=lambda: _env("EMBED_PROVIDER", "api"))
    embed_dim: int = field(default_factory=lambda: int(_env("EMBED_DIM", "768")))
    embed_base_url: str = field(default_factory=lambda: _env("EMBED_BASE_URL", GEMINI_OPENAI_URL).rstrip("/"))
    embed_api_key: str = field(default_factory=lambda: _env("EMBED_API_KEY") or _env("GEMINI_API_KEY"))
    embed_model: str = field(default_factory=lambda: _env("EMBED_MODEL", "gemini-embedding-001"))

    # Answers: any OpenAI-compatible /chat/completions API (Gemini, Groq, OpenRouter, Mistral, Cerebras...).
    # No key = no LLM: the best matching passage is shown instead.
    # EMBED_API_KEY / LLM_API_KEY override GEMINI_API_KEY when you point either one at another provider.
    llm_base_url: str = field(default_factory=lambda: _env("LLM_BASE_URL", GEMINI_OPENAI_URL).rstrip("/"))
    llm_api_key: str = field(default_factory=lambda: _env("LLM_API_KEY") or _env("GEMINI_API_KEY"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "gemini-3.8-flash"))
    # Tried in order when the main model is overloaded or rate-limited.
    llm_fallback_models: list[str] = field(default_factory=lambda: [
        m.strip() for m in _env("LLM_FALLBACK_MODELS", "gemini-3.6-flash,gemini-3.5-flash-lite").split(",") if m.strip()
    ])

    @property
    def answers(self) -> str:
        return "llm" if self.llm_api_key else "none"

    # Files: "local" (FILES_DIR) or "s3" (any S3-compatible bucket, e.g. Cloudflare R2).
    file_store: str = field(default_factory=lambda: _env("FILE_STORE", "local"))
    files_dir: str = field(default_factory=lambda: _env("FILES_DIR", "./data/files"))
    s3_endpoint: str = field(default_factory=lambda: _env("S3_ENDPOINT"))
    s3_bucket: str = field(default_factory=lambda: _env("S3_BUCKET"))
    s3_access_key: str = field(default_factory=lambda: _env("S3_ACCESS_KEY_ID"))
    s3_secret_key: str = field(default_factory=lambda: _env("S3_SECRET_ACCESS_KEY"))

    # Signs the short-lived links that open original files. Without it, a random per-process secret is used:
    # fine for one process, but links then break on restart and across several workers.
    file_url_secret: str = field(default_factory=lambda: _env("FILE_URL_SECRET") or secrets.token_hex(32))
    file_url_ttl_s: int = field(default_factory=lambda: int(_env("FILE_URL_TTL_S", "900")))

    environment: str = field(default_factory=lambda: _env("APP_ENV", "development"))  # "production" on the host
    posthog_key: str = field(default_factory=lambda: _env("POSTHOG_KEY"))
    posthog_host: str = field(default_factory=lambda: _env("POSTHOG_HOST", "https://eu.i.posthog.com"))

    max_upload_mb: int = field(default_factory=lambda: int(_env("MAX_UPLOAD_MB", "15")))
    # The URL is public and answers cost money: cap questions per anonymous user.
    max_questions_per_hour: int = field(default_factory=lambda: int(_env("MAX_QUESTIONS_PER_HOUR", "60")))


settings = Settings()

EVENTS: dict[str, str] = {
    k: v for k, v in json.loads((_APP / "events.json").read_text()).items()
    if not k.startswith("_")
}
