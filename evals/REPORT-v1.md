# Retrieval eval — 2026-10-28

60 questions written by Claude from one chunk each (one per job), paraphrased. A hit means any chunk of the source job is returned. Synthetic questions favour the wording of the source text, so treat absolute numbers as optimistic; the comparison between methods is the point.

| Method | Recall@1 | Recall@5 | MRR@10 |
|---|---|---|---|
| keyword | 2% | 13% | 0.06 |
| vector | 75% | 88% | 0.82 |
| hybrid | 58% | 93% | 0.73 |

**Recall@5 by whether the question names the company:**

| Method | Names company | Doesn't |
|---|---|---|
| keyword | 50% (n=4) | 11% (n=56) |
| vector | 100% (n=4) | 88% (n=56) |
| hybrid | 100% (n=4) | 93% (n=56) |

## End to end (20 questions, hybrid search + Claude)

- Answer cites the source job: **20/20**
- Claude said the excerpts couldn't answer: 1
- Cost: $1.20 total, $0.060 per answer at API list price

**Misses:**

- none
