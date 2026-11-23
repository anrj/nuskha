-- Applied on engine startup (idempotent). {dim} is replaced with EMBED_DIM.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS documents (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id          text NOT NULL,
  filename          text NOT NULL,
  content_type      text NOT NULL,
  size_bytes        integer NOT NULL,
  storage_key       text NOT NULL,
  status            text NOT NULL DEFAULT 'processing',  -- processing | ready | failed
  error             text,
  page_count        integer,
  chunk_count       integer,
  georgian_ratio    real,
  legacy_font_fixed boolean NOT NULL DEFAULT false,
  created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS documents_owner_idx ON documents (owner_id, created_at DESC);

CREATE TABLE IF NOT EXISTS chunks (
  id          bigserial PRIMARY KEY,
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  page        integer NOT NULL,
  ord         integer NOT NULL,
  text        text NOT NULL,   -- original, shown to users
  norm        text NOT NULL,   -- normalized, used for keyword search
  embedding   vector({dim}) NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks (document_id);
CREATE INDEX IF NOT EXISTS chunks_norm_trgm_idx ON chunks USING gin (norm gin_trgm_ops);
-- No HNSW index on purpose: an approximate index returns the global top matches *before* the owner filter,
-- so on a shared database a user could get zero vector hits. Exact scan is correct and fast up to ~100k chunks.
-- At scale: add HNSW back with `SET hnsw.iterative_scan = relaxed_order` (pgvector >= 0.8).
DROP INDEX IF EXISTS chunks_embedding_idx;

CREATE TABLE IF NOT EXISTS questions (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id   text NOT NULL,
  question   text NOT NULL,
  answer     text NOT NULL,
  mode       text NOT NULL,      -- llm | none | unavailable
  citations  jsonb NOT NULL,
  latency_ms integer NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- North star: one row per cited source a user opened. Reconcile against PostHog `source_opened`.
CREATE TABLE IF NOT EXISTS source_opens (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id    text NOT NULL,
  question_id uuid NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_id    bigint NOT NULL,
  page        integer NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
