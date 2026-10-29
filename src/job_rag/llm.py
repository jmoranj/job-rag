"""Calls Claude for a structured (Pydantic) answer.

Two backends, like Job Radar:
- claude-code (default): runs `claude -p` and uses the Claude Code subscription, no key needed.
- api: the Anthropic SDK with ANTHROPIC_API_KEY.
"""

import json
import os
import subprocess
from typing import TypeVar

from pydantic import BaseModel

from job_rag.db import load_env

MODEL = "claude-opus-5-5"
T = TypeVar("T", bound=BaseModel)


def ask(system: str, prompt: str, schema: type[T], effort: str = "low") -> tuple[T, float]:
    """Returns the parsed answer and its cost in dollars at API list price."""
    load_env()
    if os.environ.get("LLM_BACKEND") == "api":
        return _api(system, prompt, schema, effort)
    return _claude_code(system, prompt, schema)


def _claude_code(system: str, prompt: str, schema: type[T]) -> tuple[T, float]:
    out = subprocess.run(
        [os.environ.get("CLAUDE_BIN", "claude"), "-p", "--model", MODEL, "--no-session-persistence",
         "--output-format", "json", "--tools", "", "--system-prompt", system,
         "--json-schema", json.dumps(schema.model_json_schema())],
        input=prompt, capture_output=True, text=True, timeout=600,
    )
    try:
        v = json.loads(out.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude -p failed: {out.stderr.strip() or out.stdout[:300]}")
    if v.get("is_error") or v.get("structured_output") is None:
        raise RuntimeError(f"claude -p: {v.get('result')}")
    return schema.model_validate(v["structured_output"]), float(v.get("total_cost_usd") or 0)


def _api(system: str, prompt: str, schema: type[T], effort: str) -> tuple[T, float]:
    import anthropic

    client = anthropic.Anthropic()
    resp = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": effort},
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_format=schema,
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request")
    u = resp.usage
    cost = (
        (u.input_tokens + (u.cache_creation_input_tokens or 0)) * 4
        + u.output_tokens * 20
        + (u.cache_read_input_tokens or 0) * 0.2
    ) / 1e6  # Claude Opus 5.5 list price per million tokens
    return resp.parsed_output, cost
