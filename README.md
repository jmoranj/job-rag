# job-rag

Ask questions about the jobs [Job Radar](https://github.com/jmoranj/personal-job-api) collected, and get answers that cite the postings they came from.

```text
$ job-rag ask "Which companies hiring in Latin America mention evals or guardrails for LLM work?"
- phData, Sr. Applied AI Engineer: covers production LLM apps "including evaluation, monitoring, and guardrails" [1] ...
[1] Sr. Applied AI Engineer — phData  https://...
```

Python 3.12 · Postgres + pgvector · fastembed (local `bge-small-en-v1.5`, no API key) · Claude (`claude-opus-5-5`) for answers.

## How it works

```text
Job Radar Postgres (read-only) ──► chunk (≤900 chars, sentence-aligned, header: title · company · location)
                                   ──► embed locally (bge-small, 384-d) ──► pgvector + tsvector (GIN) in one table
question ──► keyword search (Postgres full text, OR of terms, length-normalised rank)
         ──► vector search (HNSW, cosine)
         ──► reciprocal rank fusion (k=60) ──► top 8 chunks ──► Claude, structured output:
             answer with [n] citations, cited excerpt numbers, "answerable" flag
```

- **Grounded answers:** the prompt allows only the numbered excerpts; citations to excerpts that weren't given are dropped in code, so every source shown is real.
- **Two Claude backends:** `claude-code` (default) runs `claude -p` on your Claude Code subscription; `LLM_BACKEND=api` uses the Anthropic SDK (`beta.messages.parse` with a Pydantic schema and server-side fallbacks).

## Run

```bash
docker compose -f infra/compose.yml up -d     # pgvector on :5434
cp .env.example .env                          # Job Radar's DB must be running on :5433
uv run job-rag ingest                         # ~6 min on a laptop CPU for ~3,600 chunks
uv run job-rag search "remote Brazil TypeScript LLM agents"
uv run job-rag ask "Which roles in Brazil use Claude or MCP?"
```

## Retrieval eval

```bash
uv run job-rag eval build -n 60   # Claude writes one paraphrased question per sampled chunk (one per job)
uv run job-rag eval run           # rank of the source job per method + 20 end-to-end answers -> evals/REPORT.md
```

A hit means any chunk of the question's source job is returned. Questions whose job has since been taken down from Job Radar are skipped and counted.

| 56 questions | Recall@1 | Recall@5 | MRR@10 |
|---|---|---|---|
| Keyword (final) | 88% | 98% | 0.92 |
| Vector | 68% | 88% | 0.77 |
| **Hybrid (final)** | **82%** | **98%** | **0.88** |

End to end (hybrid + Claude): **20/20** answers cite the source job, $0.041 per answer at API list price.

### What the eval changed

| Iteration | Finding | Change |
|---|---|---|
| v1 | Keyword search found the right job in the top 5 only 13% of the time; it dragged hybrid's #1 accuracy to 58% (vector alone: 75%) | Match any term instead of all terms; rank by matches normalised for chunk length |
| v2 | Keyword 13% → 92%, but vector and end-to-end seemed to drop | Suspected the location header diluted embeddings; tested by embedding without it (v3) — no difference |
| v3 | Real cause: Job Radar had refreshed and 4 source jobs were gone, so those questions were unanswerable | Eval now skips and reports questions whose job no longer exists |

Reports for each step are in `evals/REPORT-v1.md`, `REPORT-v2.md` and `REPORT.md`.

### Caveats

- Questions are synthetic (Claude-written from the chunk), which favours word overlap with the source — one reason keyword search scores so high. The comparison between methods matters more than the absolute numbers.
- Claude was asked to name the company in about half the questions but did so in only 3 of 56, so the "names company" split is too small to read.
- Next: a small set of hand-written questions, and a reranker to lift recall@1.
