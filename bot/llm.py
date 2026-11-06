"""The only place that calls a model.

Main:     Claude Sonnet 5.5 through the Anthropic SDK.
Fallback: Nous Portal (OpenAI-compatible API), approved by the owner for
          fallback use only. Used when Anthropic has a connection error,
          a rate limit (429), or a server error (5xx). Other errors
          (for example a bad key, 401/403) are not hidden by the fallback.

Environment:
  ANTHROPIC_API_KEY   required
  ANTHROPIC_MODEL     optional, default claude-sonnet-5-5
  NOUS_API_KEY        optional; without it there is no fallback
  NOUS_BASE_URL       optional, default https://inference-api.nousresearch.com/v1
  NOUS_MODEL          optional, default anthropic/claude-sonnet-5-5
"""

import logging
import os
from dataclasses import dataclass

import anthropic
import openai

log = logging.getLogger("llm")

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
NOUS_MODEL = os.getenv("NOUS_MODEL", "anthropic/claude-sonnet-5-5")
NOUS_BASE_URL = os.getenv("NOUS_BASE_URL", "https://inference-api.nousresearch.com/v1")
MAX_TOKENS = 4000


class LLMError(Exception):
    """Raised when no provider could produce an answer."""


@dataclass
class Result:
    text: str
    provider: str  # "anthropic" or "nous"
    refused: bool = False


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


async def generate(system: str, user: str) -> Result:
    """Return the model's answer, falling back to Nous Portal if allowed."""
    try:
        resp = await _anthropic.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS,
            system=[
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ],
            messages=[{"role": "user", "content": user}],
        )
        u = resp.usage
        log.info(
            "anthropic in=%s out=%s cache_read=%s cache_write=%s",
            u.input_tokens, u.output_tokens,
            u.cache_read_input_tokens, u.cache_creation_input_tokens,
        )
        if resp.stop_reason == "refusal":
            return Result("", "anthropic", refused=True)
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return Result(text, "anthropic")
    except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
        if not _should_fallback(exc):
            raise LLMError(f"Anthropic error, no fallback for this error: {exc}") from exc
        log.warning("Anthropic failed (%s), trying Nous Portal", exc)

    if _nous is None:
        raise LLMError("Anthropic is unavailable and NOUS_API_KEY is not set")

    try:
        r = await _nous.chat.completions.create(
            model=NOUS_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
    except (openai.APIConnectionError, openai.APIStatusError) as exc:
        raise LLMError(f"Both providers failed. Nous error: {exc}") from exc

    text = (r.choices[0].message.content or "").strip()
    return Result(text, "nous")
