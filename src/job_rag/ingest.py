"""Copies job postings from Job Radar, splits them into chunks, embeds them and stores them."""

import re

from fastembed import TextEmbedding

from job_rag import db

MODEL = "BAAI/bge-small-en-v1.5"
MAX_CHARS = 900

_embedder: TextEmbedding | None = None


def embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(MODEL)
    return _embedder


def chunk(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """Packs sentences into chunks of at most max_chars, so a chunk never cuts a sentence."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
    chunks, current = [], ""
    for s in sentences:
        if current and len(current) + len(s) + 1 > max_chars:
            chunks.append(current)
            current = ""
        current = f"{current} {s}".strip()
    if current:
        chunks.append(current)
    return chunks


def run(eligibility: tuple[str, ...] = ("yes", "maybe")) -> int:
    """Rebuilds the store from Job Radar's current jobs. Returns the number of chunks."""
    with db.jobs() as src:
        rows = src.execute(
            "SELECT id, title, company, url, location, eligibility, description FROM jobs "
            "WHERE eligibility = ANY(%s) AND length(description) > 200",
            (list(eligibility),),
        ).fetchall()

    records = []
    for job_id, title, company, url, location, elig, description in rows:
        # Every chunk carries the job's title, company and location, so a chunk from the middle of
        # a posting can still answer "where can I work from?" and match on the company name.
        header = f"{title} at {company}. Location: {location or 'Remote'}."
        for n, text in enumerate(chunk(description)):
            records.append((f"{job_id}#{n}", job_id, title, company, url, elig, n, f"{header}\n{text}", text))

    # The embedding gets title + company but not the location line: the eval showed the full header
    # diluted chunk meaning (vector recall@5 88% -> 80%), while keyword search and answers need it.
    vectors = embedder().embed([f"{r[2]} at {r[3]}. {r[8]}" for r in records], batch_size=64)

    with db.rag() as conn:
        conn.execute("TRUNCATE chunks")
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks (id, job_id, title, company, url, eligibility, n, text, embedding) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [(*r[:8], v) for r, v in zip(records, vectors)],
            )
    return len(records)
