"""Retrieval eval: which search method finds the right job?

build: sample chunks, have Claude write one question per chunk that only that job answers,
       paraphrased so it can't just copy keywords -> evals/questions.jsonl
run:   for each question, search with keyword / vector / hybrid and record where the source
       job ranks -> recall@1, recall@5, MRR@10; then answer a subset end to end and check
       the answer cites the source job -> evals/REPORT.md
"""

import json
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

from job_rag import db, llm
from job_rag.answer import answer
from job_rag.search import METHODS

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "evals" / "questions.jsonl"
REPORT = ROOT / "evals" / "REPORT.md"

QUESTION_SYSTEM = """You write evaluation questions for a search engine over remote job postings.
Given one excerpt from a posting, write a question a job seeker might type that this excerpt answers
and that is specific enough to point at this job, not jobs in general.
- Paraphrase: don't copy distinctive phrases from the excerpt word for word; use the words a person would use.
- You may mention the company name in about half of the questions; leave it out in the others.
- If the excerpt is generic boilerplate (equal-opportunity text, benefits lists that fit any company), set usable to false."""


class Question(BaseModel):
    question: str
    mentions_company: bool
    usable: bool = Field(description="False if the excerpt is generic boilerplate")


def build(n: int = 60, seed: int = 7) -> None:
    if QUESTIONS.exists():
        raise SystemExit(f"{QUESTIONS} exists; delete it to rebuild")
    with db.rag() as conn:
        rows = conn.execute(
            "SELECT id, job_id, title, company, text FROM chunks WHERE length(text) > 400"
        ).fetchall()
    random.Random(seed).shuffle(rows)
    # One chunk per job, so no job dominates the set.
    picked, seen = [], set()
    for r in rows:
        if r[1] not in seen:
            picked.append(r)
            seen.add(r[1])
        if len(picked) >= int(n * 1.4):  # some come back unusable
            break

    def write(r):
        chunk_id, job_id, title, company, text = r
        q, _ = llm.ask(QUESTION_SYSTEM, f"{title} at {company}\n\n{text}", Question)
        return {"question": q.question, "chunk_id": chunk_id, "job_id": job_id,
                "company": company, "mentions_company": q.mentions_company, "usable": q.usable}

    with ThreadPoolExecutor(2) as pool:
        made = [q for q in pool.map(write, picked) if q["usable"]][:n]
    QUESTIONS.parent.mkdir(exist_ok=True)
    QUESTIONS.write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in made))
    print(f"wrote {len(made)} questions to {QUESTIONS}")


def _rank(hits, job_id: str) -> int | None:
    """1-based rank of the first chunk from the source job, or None if absent."""
    return next((i + 1 for i, h in enumerate(hits) if h.job_id == job_id), None)


def _metrics(ranks: list[int | None]) -> dict:
    n = len(ranks) or 1
    return {
        "recall@1": sum(1 for r in ranks if r == 1) / n,
        "recall@5": sum(1 for r in ranks if r and r <= 5) / n,
        "mrr@10": sum(1 / r for r in ranks if r and r <= 10) / n,
    }


def run(answer_sample: int = 20) -> None:
    qs = [json.loads(line) for line in QUESTIONS.read_text().splitlines() if line.strip()]
    # Job Radar keeps refreshing, so a question's job may have been taken down since the set was
    # built. Those questions can't be answered; skip them and say how many, instead of scoring misses.
    with db.rag() as conn:
        live = {r[0] for r in conn.execute("SELECT DISTINCT job_id FROM chunks")}
    skipped = [q for q in qs if q["job_id"] not in live]
    qs = [q for q in qs if q["job_id"] in live]
    ranks: dict[str, list] = {m: [] for m in METHODS}
    by_company: dict[str, dict[bool, list]] = {m: {True: [], False: []} for m in METHODS}
    with db.rag() as conn:
        for q in qs:
            for name, fn in METHODS.items():
                r = _rank(fn(conn, q["question"], 10), q["job_id"])
                ranks[name].append(r)
                by_company[name][q["mentions_company"]].append(r)

    # End to end: does the answer (hybrid search + Claude) cite the source job?
    sample = qs[:answer_sample]

    def end_to_end(q):
        try:
            a, hits, cost = answer(q["question"])
        except Exception as e:  # noqa: BLE001 - a failed call counts as a miss
            return {"q": q, "ok": False, "answerable": False, "cost": 0.0, "error": str(e)}
        cited_jobs = {hits[n - 1].job_id for n in a.cited}
        return {"q": q, "ok": q["job_id"] in cited_jobs, "answerable": a.answerable, "cost": cost}

    with ThreadPoolExecutor(2) as pool:
        e2e = list(pool.map(end_to_end, sample))

    REPORT.write_text(_report(qs, ranks, by_company, e2e, len(skipped)))
    print(REPORT.read_text())


def _report(qs, ranks, by_company, e2e, skipped: int) -> str:
    pct = lambda x: f"{100 * x:.0f}%"  # noqa: E731
    out = [f"# Retrieval eval — {date.today()}\n",
           f"{len(qs)} questions written by Claude from one chunk each (one per job), paraphrased. "
           "A hit means any chunk of the source job is returned. Synthetic questions favour the "
           "wording of the source text, so treat absolute numbers as optimistic; the comparison "
           "between methods is the point."
           + (f" {skipped} questions skipped because their job is no longer listed." if skipped else "") + "\n",
           "| Method | Recall@1 | Recall@5 | MRR@10 |", "|---|---|---|---|"]
    for name, r in ranks.items():
        m = _metrics(r)
        out.append(f"| {name} | {pct(m['recall@1'])} | {pct(m['recall@5'])} | {m['mrr@10']:.2f} |")

    out += ["", "**Recall@5 by whether the question names the company:**", "",
            "| Method | Names company | Doesn't |", "|---|---|---|"]
    for name, split in by_company.items():
        out.append(f"| {name} | {pct(_metrics(split[True])['recall@5'])} (n={len(split[True])}) "
                   f"| {pct(_metrics(split[False])['recall@5'])} (n={len(split[False])}) |")

    ok = sum(r["ok"] for r in e2e)
    cost = sum(r["cost"] for r in e2e)
    out += ["", f"## End to end ({len(e2e)} questions, hybrid search + Claude)", "",
            f"- Answer cites the source job: **{ok}/{len(e2e)}**",
            f"- Claude said the excerpts couldn't answer: {sum(not r['answerable'] for r in e2e)}",
            f"- Cost: ${cost:.2f} total, ${cost / max(len(e2e), 1):.3f} per answer at API list price", "",
            "**Misses:**", ""]
    out += [f"- {r['q']['question']} — expected {r['q']['company']}" + (f" (error: {r['error']})" if r.get("error") else "")
            for r in e2e if not r["ok"]] or ["- none"]
    return "\n".join(out) + "\n"
