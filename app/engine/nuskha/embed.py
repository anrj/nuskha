"""Embedding providers behind one function: embed(texts) -> list of unit vectors."""
import hashlib
import math

from .config import settings
from .providers import ProviderError, post_json


def _ngram_embed(text: str, dim: int) -> list[float]:
    """Hashed character 2-4-grams. Offline and deterministic; handles Georgian word forms surprisingly well.

    Good enough for development and tests. Use a real model (EMBED_PROVIDER=api) for production quality.
    """
    vec = [0.0] * dim
    padded = f" {text} "
    for n in (2, 3, 4):
        for i in range(len(padded) - n + 1):
            h = int.from_bytes(hashlib.blake2b(padded[i:i + n].encode(), digest_size=8).digest(), "little")
            vec[h % dim] += 1.0 if (h >> 63) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _api_embed(texts: list[str]) -> list[list[float]]:
    """Any OpenAI-compatible /embeddings endpoint (OpenAI, Gemini, Mistral, Jina, ...)."""
    if not settings.embed_api_key:
        raise ProviderError("No embeddings key: set GEMINI_API_KEY in .env (or EMBED_PROVIDER=ngram for offline dev)")
    out: list[list[float]] = []
    for i in range(0, len(texts), 64):
        body = post_json(
            f"Embeddings ({settings.embed_model})", f"{settings.embed_base_url}/embeddings", settings.embed_api_key,
            {"model": settings.embed_model, "input": texts[i:i + 64], "dimensions": settings.embed_dim}, timeout=60,
        )
        out.extend(d["embedding"] for d in sorted(body["data"], key=lambda d: d.get("index", 0)))
    if out and len(out[0]) != settings.embed_dim:
        raise ProviderError(f"Embedding model returned {len(out[0])} dims, EMBED_DIM is {settings.embed_dim}")
    return out


def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if settings.embed_provider != "ngram":
        return _api_embed(texts)
    return [_ngram_embed(t, settings.embed_dim) for t in texts]
