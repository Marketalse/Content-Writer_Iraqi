"""The only place that calls a model.

Writer:   Claude Sonnet 5.5 (ANTHROPIC_MODEL) through the Anthropic SDK.
Fast:     Claude Haiku 5.5 (ANTHROPIC_FAST_MODEL) for the analyst and dialect checker.
Fallback: Nous Portal (OpenAI-compatible), approved by the owner for fallback only.
          Used on Anthropic connection errors, 429 and 5xx. Other errors are not hidden.

Environment:
  ANTHROPIC_API_KEY    required
  ANTHROPIC_MODEL      optional, default claude-sonnet-5-5
  ANTHROPIC_FAST_MODEL optional, default claude-haiku-5-5
  NOUS_API_KEY         optional; without it there is no fallback
  NOUS_BASE_URL        optional, default https://inference-api.nousresearch.com/v1
  NOUS_MODEL           optional, default anthropic/claude-sonnet-5-5
"""

import logging
import os
from dataclasses import dataclass

import anthropic
import openai

log = logging.getLogger("llm")

WRITER_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
FAST_MODEL = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-5-5")
NOUS_MODEL = os.getenv("NOUS_MODEL", "anthropic/claude-sonnet-5-5")
NOUS_BASE_URL = os.getenv("NOUS_BASE_URL", "https://inference-api.nousresearch.com/v1")
MAX_TOKENS = 4000

# USD per million tokens, Anthropic list prices. Cache read = 0.1x input, cache write = 1.25x input.
PRICES = {
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


class LLMError(Exception):
    """Raised when no provider could produce an answer."""


@dataclass
class Result:
    text: str
    provider: str            # "anthropic" or "nous"
    model: str = ""
    refused: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_write: int = 0
    cost_usd: float = 0.0


def estimate_cost(model: str, inp: int, out: int, cache_read: int, cache_write: int) -> float:
    if model not in PRICES:
        return 0.0
    pin, pout = PRICES[model]
    return (inp * pin + out * pout + cache_read * pin * 0.1 + cache_write * pin * 1.25) / 1_000_000


_anthropic = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY") or None)
_nous = (
    openai.AsyncOpenAI(api_key=os.environ["NOUS_API_KEY"], base_url=NOUS_BASE_URL)
    if os.getenv("NOUS_API_KEY")
    else None
)


def _should_fallback(exc: Exception) -> bool:
    if isinstance(exc, anthropic.APIConnectionError):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code == 429 or exc.status_code >= 500
    return False


async def generate(system: str, user: str, model: str | None = None,
                   max_tokens: int = MAX_TOKENS) -> Result:
    """Return the model's answer. Falls back to Nous Portal only on allowed errors."""
    model = model or WRITER_MODEL
    try:
        resp = await _anthropic.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        u = resp.usage
        cache_read = u.cache_read_input_tokens or 0
        cache_write = u.cache_creation_input_tokens or 0
        cost = estimate_cost(model, u.input_tokens, u.output_tokens, cache_read, cache_write)
        log.info("anthropic model=%s in=%s out=%s cache_read=%s cache_write=%s cost=$%.5f",
                 model, u.input_tokens, u.output_tokens, cache_read, cache_write, cost)
        stats = dict(model=model, input_tokens=u.input_tokens, output_tokens=u.output_tokens,
                     cache_read=cache_read, cache_write=cache_write, cost_usd=cost)
        if resp.stop_reason == "refusal":
            return Result("", "anthropic", refused=True, **stats)
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return Result(text, "anthropic", **stats)
    except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
        if not _should_fallback(exc):
            raise LLMError(f"Anthropic error, no fallback for this error: {exc}") from exc
        log.warning("Anthropic failed (%s), trying Nous Portal", exc)

    if _nous is None:
        raise LLMError("Anthropic is unavailable and NOUS_API_KEY is not set")
    try:
        r = await _nous.chat.completions.create(
            model=NOUS_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
    except (openai.APIConnectionError, openai.APIStatusError) as exc:
        raise LLMError(f"Both providers failed. Nous error: {exc}") from exc
    text = (r.choices[0].message.content or "").strip()
    return Result(text, "nous", model=NOUS_MODEL)
