"""Postgres (Neon) access: one pool, schema applied at startup."""
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

_pool: ConnectionPool | None = None


def init_db() -> None:
    global _pool
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not set (run `neon deploy`, or copy app/.env.example to app/.env.local)")
    schema = (Path(__file__).parent / "schema.sql").read_text().replace("{dim}", str(settings.embed_dim))
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(schema)
    _pool = ConnectionPool(
        settings.database_url, min_size=1, max_size=5, open=True,
        # prepare_threshold=None: safe behind Neon's PgBouncer pooler (DATABASE_URL_POOLED).
        kwargs={"row_factory": dict_row, "prepare_threshold": None},
        configure=register_vector,
        check=ConnectionPool.check_connection,  # Neon scales to zero and drops idle connections
    )


def conn():
    """Usage: `with conn() as c:` — commits on success, rolls back on error."""
    if _pool is None:
        raise RuntimeError("init_db() was not called")
    return _pool.connection()


def close_db() -> None:
    if _pool is not None:
        _pool.close()
