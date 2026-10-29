"""Three ways to find chunks: keyword (Postgres full text), vector (pgvector), and hybrid (both, fused)."""

import re
from dataclasses import dataclass

import numpy as np

from job_rag import db
from job_rag.ingest import embedder

RRF_K = 60  # standard reciprocal-rank-fusion constant


@dataclass
class Hit:
    id: str
    job_id: str
    title: str
    company: str
    url: str
    text: str
    score: float


COLUMNS = "id, job_id, title, company, url, text"


def keyword(conn, query: str, k: int = 10) -> list[Hit]:
    """Full-text search where any word may match, ranked by how many and how rare the matches are.

    Questions are long, so requiring every word (websearch_to_tsquery) usually matches nothing.
    ts_rank with normalization 1 divides by log(length), so long boilerplate chunks don't win
    just by containing many common words. Postgres drops English stop words itself.
    """
    words = [w for w in re.findall(r"[A-Za-z0-9+#.]+", query) if len(w) > 1]
    if not words:
        return []
    rows = conn.execute(
        f"SELECT {COLUMNS}, ts_rank(tsv, q, 1) FROM chunks, "
        "to_tsquery('english', %s) q WHERE tsv @@ q ORDER BY 7 DESC LIMIT %s",
        (" | ".join(f"'{w}'" for w in words), k),
    ).fetchall()
    return [Hit(*r) for r in rows]


def vector(conn, query: str, k: int = 10) -> list[Hit]:
    # bge models expect this prefix on queries (not on passages).
    q = next(iter(embedder().embed([f"Represent this sentence for searching relevant passages: {query}"])))
    rows = conn.execute(
        f"SELECT {COLUMNS}, 1 - (embedding <=> %s) FROM chunks ORDER BY embedding <=> %s LIMIT %s",
        (np.asarray(q), np.asarray(q), k),
    ).fetchall()
    return [Hit(*r) for r in rows]


def hybrid(conn, query: str, k: int = 10, pool: int = 40) -> list[Hit]:
    """Reciprocal rank fusion: each list votes 1/(60 + rank); no score calibration needed."""
    fused: dict[str, tuple[float, Hit]] = {}
    for hits in (keyword(conn, query, pool), vector(conn, query, pool)):
        for rank, h in enumerate(hits):
            score = fused.get(h.id, (0.0, h))[0] + 1 / (RRF_K + rank + 1)
            fused[h.id] = (score, h)
    ranked = sorted(fused.values(), key=lambda x: x[0], reverse=True)[:k]
    return [Hit(**{**h.__dict__, "score": s}) for s, h in ranked]


METHODS = {"keyword": keyword, "vector": vector, "hybrid": hybrid}


def search(query: str, method: str = "hybrid", k: int = 10) -> list[Hit]:
    with db.rag() as conn:
        return METHODS[method](conn, query, k)
