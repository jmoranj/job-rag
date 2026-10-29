# Retrieval eval — 2026-10-28

56 questions written by Claude from one chunk each (one per job), paraphrased. A hit means any chunk of the source job is returned. Synthetic questions favour the wording of the source text, so treat absolute numbers as optimistic; the comparison between methods is the point. 4 questions skipped because their job is no longer listed.

| Method | Recall@1 | Recall@5 | MRR@10 |
|---|---|---|---|
| keyword | 88% | 98% | 0.92 |
| vector | 68% | 88% | 0.77 |
| hybrid | 82% | 98% | 0.88 |

**Recall@5 by whether the question names the company:**

| Method | Names company | Doesn't |
|---|---|---|
| keyword | 100% (n=3) | 98% (n=53) |
| vector | 100% (n=3) | 87% (n=53) |
| hybrid | 100% (n=3) | 98% (n=53) |

## End to end (20 questions, hybrid search + Claude)

- Answer cites the source job: **20/20**
- Claude said the excerpts couldn't answer: 0
- Cost: $0.83 total, $0.041 per answer at API list price

**Misses:**

- none
