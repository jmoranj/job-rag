# Retrieval eval — 2026-10-28

60 questions written by Claude from one chunk each (one per job), paraphrased. A hit means any chunk of the source job is returned. Synthetic questions favour the wording of the source text, so treat absolute numbers as optimistic; the comparison between methods is the point.

| Method | Recall@1 | Recall@5 | MRR@10 |
|---|---|---|---|
| keyword | 82% | 92% | 0.86 |
| vector | 67% | 80% | 0.72 |
| hybrid | 77% | 92% | 0.83 |

**Recall@5 by whether the question names the company:**

| Method | Names company | Doesn't |
|---|---|---|
| keyword | 75% (n=4) | 93% (n=56) |
| vector | 75% (n=4) | 80% (n=56) |
| hybrid | 75% (n=4) | 93% (n=56) |

## End to end (20 questions, hybrid search + Claude)

- Answer cites the source job: **17/20**
- Claude said the excerpts couldn't answer: 3
- Cost: $1.13 total, $0.056 per answer at API list price

**Misses:**

- Fullstack product engineer role at a startup building a business modeling tool to replace Excel, needing 5+ years of experience and the ability to ship quality work fast — expected Runway
- Senior design engineer role at a crypto wallet company that wants React and React Native experience plus a portfolio showing motion, animation, and haptics work — expected MetaMask
- Remote entry-level platform access engineer job working on Okta/SAML identity federation and Kubernetes RBAC across AWS, Azure and GCP — which states can't apply? — expected Twilio
