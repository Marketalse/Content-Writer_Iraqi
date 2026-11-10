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
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import anthropic
import openai

log = logging.getLogger("llm")

WRITER_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
FAST_MODEL = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-5-5")
NOUS_MODEL = os.getenv("NOUS_MODEL", "anthropic/claude-sonnet-5-5")
NOUS_BASE_URL = os.getenv("NOUS_BASE_URL", "https://inference-api.nousresearch.com/v1")
MAX_TOKENS = 4000
# Documented Claude API structured-output models used by this project. Unknown
# model overrides retain strict local validation without speculative API options.
STRUCTURED_MODELS = frozenset(('claude-haiku-5-5', 'claude-sonnet-5-5'))

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
    truncated: bool = False
    usage_known: bool = True
    stop_reason: str = ''
    thinking_blocks: int = 0
    structured_output: bool = False
    effort: str = ''
    sources: list[dict] = field(default_factory=list)
    search_requests: int = 0
    search_failed: bool = False


def estimate_cost(model: str, inp: int, out: int, cache_read: int, cache_write: int) -> float:
    if model not in PRICES:
        return 0.0
    pin, pout = PRICES[model]
    return (inp * pin + out * pout + cache_read * pin * 0.1 + cache_write * pin * 1.25) / 1_000_000


_anthropic = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY") or "not-configured", max_retries=0, timeout=40.0)
_nous = (
    openai.AsyncOpenAI(api_key=os.environ["NOUS_API_KEY"], base_url=NOUS_BASE_URL, max_retries=0, timeout=40.0)
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
                   max_tokens: int = MAX_TOKENS, *, output_schema: dict | None = None,
                   effort: str | None = None, web_search: bool = False) -> Result:
    """Return the model's answer. Falls back to Nous Portal only on allowed errors."""
    model = model or WRITER_MODEL
    if effort not in (None, 'low', 'medium', 'high'):
        raise ValueError('invalid model effort')
    output_config = {}
    if output_schema is not None and model in STRUCTURED_MODELS:
        output_config['format'] = {'type':'json_schema', 'schema':output_schema}
    if effort is not None and model == 'claude-haiku-5-5':
        output_config['effort'] = effort
    # extra_body keeps compatibility with SDK versions predating output_config.
    options = {'extra_body':{'output_config':output_config}} if output_config else {}
    if web_search:
        options['tools'] = [{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': 2}]
    try:
        resp = await _anthropic.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            **options,
        )
        u = resp.usage
        cache_read = u.cache_read_input_tokens or 0
        cache_write = u.cache_creation_input_tokens or 0
        cost = estimate_cost(model, u.input_tokens, u.output_tokens, cache_read, cache_write)
        searches = 0
        sources = []
        search_failed = False
        if web_search:
            tool_usage = getattr(u, 'server_tool_use', None)
            searches = getattr(tool_usage, 'web_search_requests', 0) or 0
            search_failed = type(searches) is not int or not 0 <= searches <= 2
            searches = searches if type(searches) is int and searches >= 0 else 0
            cost += searches * 0.01  # Anthropic web search: $10 per 1,000 searches.
            result_urls = set()
            for block in resp.content:
                if block.type == 'web_search_tool_result':
                    content = getattr(block, 'content', None)
                    if not isinstance(content, list):
                        search_failed = True
                    else:
                        result_urls.update(item.url for item in content
                                           if getattr(item, 'type', '') == 'web_search_result')
            for block in resp.content:
                if block.type != 'text':
                    continue
                for citation in getattr(block, 'citations', None) or []:
                    if getattr(citation, 'type', '') != 'web_search_result_location':
                        continue
                    url = citation.url
                    parsed = urlsplit(url)
                    quote = getattr(citation, 'cited_text', '')
                    if (url in result_urls and parsed.scheme == 'https' and parsed.hostname
                            and not parsed.username and not parsed.password
                            and isinstance(quote, str) and quote.strip() and len(url) <= 2000):
                        source = {'url': url, 'title': str(getattr(citation, 'title', ''))[:300],
                                  'excerpt': quote[:2000]}
                        if source not in sources and len(sources) < 6:
                            sources.append(source)
        log.info("anthropic model=%s in=%s out=%s cache_read=%s cache_write=%s cost=$%.5f",
                 model, u.input_tokens, u.output_tokens, cache_read, cache_write, cost)
        stats = dict(stop_reason=resp.stop_reason,
                     thinking_blocks=sum(b.type in ('thinking', 'redacted_thinking') for b in resp.content),
                     structured_output='format' in output_config, effort=output_config.get('effort',''),
                     sources=sources, search_requests=searches, search_failed=search_failed,
                     truncated=resp.stop_reason == "max_tokens", usage_known=model in PRICES, model=model, input_tokens=u.input_tokens, output_tokens=u.output_tokens,
                     cache_read=cache_read, cache_write=cache_write, cost_usd=cost)
        if resp.stop_reason == "refusal":
            return Result("", "anthropic", refused=True, **stats)
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return Result(text, "anthropic", **stats)
    except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
        if not _should_fallback(exc):
            raise LLMError("Anthropic request rejected") from exc
        if web_search:
            raise LLMError("Web research unavailable") from exc
        log.warning("Anthropic unavailable; trying configured fallback")

    if _nous is None:
        raise LLMError("Anthropic is unavailable and NOUS_API_KEY is not set")
    try:
        r = await _nous.chat.completions.create(
            model=NOUS_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
    except (openai.APIConnectionError, openai.APIStatusError) as exc:
        raise LLMError("Both providers unavailable") from exc
    text = (r.choices[0].message.content or "").strip()
    usage = r.usage
    return Result(text, "nous", model=NOUS_MODEL, stop_reason=r.choices[0].finish_reason,
                  truncated=r.choices[0].finish_reason == "length",
                  input_tokens=usage.prompt_tokens if usage else 0,
                  output_tokens=usage.completion_tokens if usage else 0,
                  usage_known=False)  # configured fallback pricing is unknown; stop further calls
