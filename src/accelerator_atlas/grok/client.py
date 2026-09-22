"""xAI Grok client with budget tracking, idempotent caching, and retries.

Every call is logged to the `grok_usage` table with prompt/completion/reasoning
tokens and a computed USD cost. A hard cap enforced against the sum of
`usd_cost` blocks further calls once the user's project budget is exhausted.

Models used:
    - grok-4-fast-non-reasoning: cheap, for classification/extraction
    - grok-4-fast-reasoning: default synthesis model with chain-of-thought

All calls go via the OpenAI-compatible endpoint at https://api.x.ai/v1.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openai import OpenAI
from sqlalchemy import func, select
from tenacity import retry, stop_after_attempt, wait_exponential

from accelerator_atlas.schema.models import GrokUsage
from accelerator_atlas.storage.db import session_scope

log = logging.getLogger("grok.client")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Published xAI pricing (USD per 1M tokens). Update when xAI changes pricing.
# Source: https://docs.x.ai/docs/models — verified Oct 2025.
PRICING: dict[str, dict[str, float]] = {
    # grok-4-fast family: $0.20 in / $0.50 out / $0.05 cached
    "grok-4-fast-reasoning":      {"input": 0.20, "output": 0.50, "cached": 0.05},
    "grok-4-fast-non-reasoning":  {"input": 0.20, "output": 0.50, "cached": 0.05},
    # grok-4 (big): $3 in / $15 out
    "grok-4-0709":                {"input": 3.00, "output": 15.00, "cached": 0.75},
    # grok-3 family (legacy, per docs).
    "grok-3":                     {"input": 3.00, "output": 15.00, "cached": 0.75},
    "grok-3-mini":                {"input": 0.30, "output": 0.50, "cached": 0.075},
}
DEFAULT_MODEL_FAST = "grok-4-fast-non-reasoning"
DEFAULT_MODEL_REASON = "grok-4-fast-reasoning"

# Hard cap for this project. Overridable via env.
BUDGET_USD = float(os.getenv("GROK_BUDGET_USD", "50.0"))

# Cache directory for raw responses (idempotent replay, zero-cost).
CACHE_DIR = Path(".firecrawl/grok_cache")


@dataclass
class GrokResponse:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    total_tokens: int
    usd_cost: float
    latency_ms: int
    cached: bool
    usage_id: int | None


def _hash(payload: dict[str, Any]) -> str:
    s = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode()).hexdigest()


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int,
                   cached_tokens: int = 0) -> float:
    p = PRICING.get(model, {"input": 1.0, "output": 2.0, "cached": 0.25})
    fresh_input = max(0, prompt_tokens - cached_tokens)
    return (
        fresh_input * p["input"] / 1_000_000
        + cached_tokens * p["cached"] / 1_000_000
        + completion_tokens * p["output"] / 1_000_000
    )


def spent_usd() -> float:
    """Sum of usd_cost across all successful calls in grok_usage."""
    with session_scope() as s:
        val = s.execute(
            select(func.coalesce(func.sum(GrokUsage.usd_cost), 0.0))
            .where(GrokUsage.success.is_(True))
        ).scalar_one()
    return float(val)


def budget_ok(needed_usd_headroom: float = 0.0) -> tuple[bool, float, float]:
    spent = spent_usd()
    remaining = BUDGET_USD - spent
    ok = remaining >= needed_usd_headroom
    return ok, spent, remaining


def _log_usage(model: str, purpose: str, resp_obj: Any, latency_ms: int,
               input_hash: str, success: bool, error: str | None = None,
               cost_override: float | None = None) -> int:
    usage = getattr(resp_obj, "usage", None) if resp_obj else None
    pt = getattr(usage, "prompt_tokens", 0) or 0
    ct = getattr(usage, "completion_tokens", 0) or 0
    rt = 0
    cached = 0
    details = getattr(usage, "completion_tokens_details", None)
    if details is not None:
        rt = getattr(details, "reasoning_tokens", 0) or 0
    pdetails = getattr(usage, "prompt_tokens_details", None)
    if pdetails is not None:
        cached = getattr(pdetails, "cached_tokens", 0) or 0
    tt = getattr(usage, "total_tokens", pt + ct) or (pt + ct)

    usd = cost_override if cost_override is not None else _estimate_cost(model, pt, ct, cached)

    with session_scope() as s:
        row = GrokUsage(
            model=model, purpose=purpose,
            prompt_tokens=pt, completion_tokens=ct, reasoning_tokens=rt,
            total_tokens=tt, usd_cost=usd,
            latency_ms=latency_ms, input_hash=input_hash,
            success=success, error_message=error,
        )
        s.add(row)
        s.flush()
        return row.id


def _client() -> OpenAI:
    key = os.environ.get("XAI_API_KEY")
    if not key:
        raise RuntimeError("XAI_API_KEY not set in environment")
    return OpenAI(api_key=key, base_url="https://api.x.ai/v1")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
def _call_raw(model: str, messages: list[dict], response_format: dict | None,
              temperature: float, max_tokens: int | None):
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return _client().chat.completions.create(**kwargs)


def chat(
    purpose: str,
    messages: list[dict],
    model: str = DEFAULT_MODEL_FAST,
    response_format: dict | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    max_usd_this_call: float = 1.0,
    use_cache: bool = True,
) -> GrokResponse:
    """Call Grok once. Enforces budget, caches by input hash, logs to grok_usage.

    If the same (model, messages, temperature, response_format) was previously
    called and cached, returns the cached result with usd_cost=0.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key_payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": response_format,
    }
    input_hash = _hash(key_payload)
    cache_path = CACHE_DIR / f"{input_hash}.json"

    if use_cache and cache_path.exists():
        cached = json.loads(cache_path.read_text())
        return GrokResponse(
            text=cached["text"],
            model=cached["model"],
            prompt_tokens=cached["prompt_tokens"],
            completion_tokens=cached["completion_tokens"],
            reasoning_tokens=cached.get("reasoning_tokens", 0),
            total_tokens=cached["total_tokens"],
            usd_cost=0.0,
            latency_ms=cached.get("latency_ms", 0),
            cached=True,
            usage_id=None,
        )

    ok, spent, remaining = budget_ok(max_usd_this_call)
    if not ok:
        raise RuntimeError(
            f"Grok budget exhausted: spent=${spent:.2f} remaining=${remaining:.2f} "
            f"headroom needed=${max_usd_this_call:.2f}. Set GROK_BUDGET_USD to raise."
        )

    t0 = time.time()
    error: str | None = None
    try:
        resp = _call_raw(model, messages, response_format, temperature, max_tokens)
    except Exception as e:
        error = f"{type(e).__name__}: {str(e)[:200]}"
        _log_usage(model, purpose, None, int((time.time() - t0) * 1000),
                   input_hash, success=False, error=error, cost_override=0.0)
        raise

    latency_ms = int((time.time() - t0) * 1000)
    content = resp.choices[0].message.content or ""
    usage_id = _log_usage(model, purpose, resp, latency_ms, input_hash, success=True)

    u = resp.usage
    pt = u.prompt_tokens or 0
    ct = u.completion_tokens or 0
    rt = 0
    cached_tokens = 0
    if u.completion_tokens_details:
        rt = u.completion_tokens_details.reasoning_tokens or 0
    if u.prompt_tokens_details:
        cached_tokens = u.prompt_tokens_details.cached_tokens or 0
    tt = u.total_tokens or (pt + ct)
    usd = _estimate_cost(model, pt, ct, cached_tokens)

    out = GrokResponse(
        text=content, model=model,
        prompt_tokens=pt, completion_tokens=ct, reasoning_tokens=rt,
        total_tokens=tt, usd_cost=usd, latency_ms=latency_ms,
        cached=False, usage_id=usage_id,
    )
    if use_cache:
        cache_path.write_text(json.dumps({
            "text": content, "model": model,
            "prompt_tokens": pt, "completion_tokens": ct,
            "reasoning_tokens": rt, "total_tokens": tt,
            "latency_ms": latency_ms,
        }))
    return out


def print_budget() -> None:
    spent = spent_usd()
    remaining = BUDGET_USD - spent
    print(f"Grok budget: ${BUDGET_USD:.2f} cap | ${spent:.4f} spent | ${remaining:.4f} remaining")
    # Top 5 spend by purpose
    with session_scope() as s:
        rows = s.execute(
            select(GrokUsage.purpose, func.count(), func.sum(GrokUsage.usd_cost),
                   func.sum(GrokUsage.prompt_tokens), func.sum(GrokUsage.completion_tokens))
            .where(GrokUsage.success.is_(True))
            .group_by(GrokUsage.purpose)
            .order_by(func.sum(GrokUsage.usd_cost).desc())
        ).all()
    if rows:
        print(f"  {'purpose':<30s} {'calls':>6s} {'cost':>10s} {'in_tok':>10s} {'out_tok':>10s}")
        for purpose, calls, cost, pt, ct in rows:
            print(f"  {purpose:<30s} {calls:>6d} ${cost or 0:>8.4f} {pt or 0:>10d} {ct or 0:>10d}")
