"""Answers a question about the job postings, citing the chunks it used."""

from pydantic import BaseModel, Field

from job_rag import llm
from job_rag.search import Hit, search

SYSTEM = """You answer questions about remote job postings using only the numbered excerpts provided.
- Every factual sentence must end with the excerpt numbers it comes from, like [2] or [1][4].
- If the excerpts don't contain the answer, say so plainly; never fill gaps from general knowledge.
- Name the company and role when you mention a job."""


class Answer(BaseModel):
    answer: str = Field(description="The answer, with [n] citations after each factual sentence")
    cited: list[int] = Field(description="Excerpt numbers the answer relies on")
    answerable: bool = Field(description="False if the excerpts don't contain the answer")


def answer(question: str, k: int = 8, method: str = "hybrid") -> tuple[Answer, list[Hit], float]:
    hits = search(question, method, k)
    context = "\n\n".join(f"[{i + 1}] {h.title} at {h.company} ({h.url})\n{h.text}" for i, h in enumerate(hits))
    result, cost = llm.ask(SYSTEM, f"EXCERPTS\n\n{context}\n\nQUESTION\n{question}", Answer)
    # Drop citations to excerpts that weren't given, so every source shown is real.
    result.cited = [n for n in result.cited if 1 <= n <= len(hits)]
    return result, hits, cost
