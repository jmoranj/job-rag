"""Ask questions about Job Radar's postings: hybrid search over pgvector + Postgres full text, cited answers by Claude."""

import argparse
import sys


def main() -> None:
    p = argparse.ArgumentParser(prog="job-rag")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest", help="copy jobs from Job Radar, chunk, embed and store")
    ask = sub.add_parser("ask", help="answer a question with citations")
    ask.add_argument("question")
    ask.add_argument("--method", choices=["keyword", "vector", "hybrid"], default="hybrid")
    find = sub.add_parser("search", help="show the top chunks for a query")
    find.add_argument("query")
    find.add_argument("--method", choices=["keyword", "vector", "hybrid"], default="hybrid")
    ev = sub.add_parser("eval", help="build the question set or run the retrieval eval")
    ev.add_argument("step", choices=["build", "run"])
    ev.add_argument("-n", type=int, default=60)
    args = p.parse_args()

    if args.cmd == "ingest":
        from job_rag.ingest import run

        print(f"stored {run()} chunks")
    elif args.cmd == "search":
        from job_rag.search import search

        for h in search(args.query, args.method, 5):
            print(f"{h.score:.3f}  {h.title} — {h.company}\n       {h.text[:160]}…")
    elif args.cmd == "ask":
        from job_rag.answer import answer

        a, hits, cost = answer(args.question, method=args.method)
        print(a.answer, "\n")
        for n in a.cited:
            h = hits[n - 1]
            print(f"[{n}] {h.title} — {h.company}  {h.url}")
        print(f"\n(${cost:.3f} at API list price)", file=sys.stderr)
    elif args.cmd == "eval":
        from job_rag import evaluate

        evaluate.build(args.n) if args.step == "build" else evaluate.run()
