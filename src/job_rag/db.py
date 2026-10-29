"""Connections and schema for the pgvector store."""

import os
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

DIM = 384  # BAAI/bge-small-en-v1.5

SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id          TEXT PRIMARY KEY,          -- job_id#n
    job_id      TEXT NOT NULL,
    title       TEXT NOT NULL,
    company     TEXT NOT NULL,
    url         TEXT NOT NULL,
    eligibility TEXT NOT NULL,
    n           INT  NOT NULL,
    text        TEXT NOT NULL,
    embedding   vector({DIM}) NOT NULL,
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', title || ' ' || company || ' ' || text)) STORED
);
CREATE INDEX IF NOT EXISTS chunks_tsv ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_job ON chunks (job_id);
"""


def load_env() -> None:
    """Reads .env next to the project root, without overriding real environment variables."""
    path = Path(__file__).resolve().parents[2] / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def rag() -> psycopg.Connection:
    load_env()
    conn = psycopg.connect(os.environ["RAG_DATABASE_URL"], autocommit=True)
    conn.execute(SCHEMA)
    register_vector(conn)
    return conn


def jobs() -> psycopg.Connection:
    """Job Radar's database, opened read-only."""
    load_env()
    conn = psycopg.connect(os.environ["JOBS_DATABASE_URL"], autocommit=True)
    conn.execute("SET default_transaction_read_only = on")
    return conn
