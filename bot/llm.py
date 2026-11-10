"""The only place that calls a model.

Writer:   Claude Sonnet 5.5 (ANTHROPIC_MODEL) through the Anthropic SDK.
Fast:     Claude Haiku 5.5 (ANTHROPIC_FAST_MODEL) for the analyst and dialect checker.
Fallback: Nous Portal (OpenAI-compatible), approved by the owner for fallback only.
          Used on connection errors, 429, 5xx and confirmed exhausted Anthropic credit.

Environment:
  ANTHROPIC_API_KEY    required
  ANTHROPIC_MODEL      optional, default claude-sonnet-5-5
  ANTHROPIC_FAST_MODEL optional, default claude-haiku-5-5
  NOUS_API_KEY         optional; without it there is no fallback
  NOUS_BASE_URL        optional, default https://inference-api.nousresearch.com/v1
  NOUS_MODEL           optional, default anthropic/claude-sonnet-5.5
"""

import logging
import json
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import anthropic
import openai

log = logging.getLogger("llm")

WRITER_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
FAST_MODEL = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-5-5")
NOUS_MODEL = os.getenv("NOUS_MODEL", "anthropic/claude-sonnet-5.5")
# Correct the legacy spelling shipped in this repository's .env.example.
if NOUS_MODEL == 'anthropic/claude-sonnet-5-5':
    NOUS_MODEL = 'anthropic/claude-sonnet-5.5'
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
# Nous's public /v1/models catalog, verified 2026-11-10. USD per million tokens;
# no cache options are requested below. Unknown models still fail the budget guard.
NOUS_PRICES = {'anthropic/claude-sonnet-5.5': (2.00, 10.00)}


PROVIDER_ERROR_CODES = frozenset({
    'provider_error', 'provider_credit_exhausted', 'provider_billing_required',
    'provider_authentication', 'provider_permission', 'provider_model_unavailable',
    'provider_rate_limit', 'provider_request_rejected', 'provider_connection',
    'provider_timeout', 'provider_unavailable', 'provider_search_unavailable',
    'provider_fallback_unconfigured',
})


class LLMError(Exception):
    """Fixed diagnostic metadata; never retain provider error bodies in user records."""
    def __init__(self, message='Provider request failed', *, code='provider_error',
                 provider='unknown', http_status=None, fallback_status=None):
        super().__init__(message)
        self.code = code if code in PROVIDER_ERROR_CODES else 'provider_error'
        self.provider = provider if provider in ('anthropic', 'nous') else 'unknown'
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        self.fallback_status = fallback_status if fallback_status in ('not_configured', 'unsupported_search') else None


def provider_failure(exc, provider):
    """Recognize explicit billing signals privately; export only fixed safe codes."""
    status = getattr(exc, 'status_code', None)
    body = getattr(exc, 'body', None)
    error = body.get('error', body) if isinstance(body, dict) else {}
    error = error if isinstance(error, dict) else {}
    message = error.get('message', '')
    message = message.casefold()[:4000] if isinstance(message, str) else ''
    reason = error.get('code') or error.get('type')
    credit = reason in ('insufficient_quota', 'insufficient_credit', 'insufficient_credits', 'credit_balance_too_low') or message.startswith((
        'your credit balance is too low', 'insufficient credits', 'insufficient credit',
        'your account has insufficient credits'))
    if status in (400, 402, 403, 429) and credit:
        code = 'provider_credit_exhausted'
    elif isinstance(exc, (anthropic.APITimeoutError, openai.APITimeoutError)):
        code = 'provider_timeout'
    elif status is None:
        code = 'provider_connection'
    else:
        code = {400: 'provider_request_rejected', 401: 'provider_authentication',
                402: 'provider_billing_required', 403: 'provider_permission',
                404: 'provider_model_unavailable', 429: 'provider_rate_limit'}.get(
                    status, 'provider_request_rejected' if status < 500 else 'provider_unavailable')
    return LLMError(code=code, provider=provider, http_status=status)


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
    fallback_reason: str = ''


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
        return (exc.status_code == 429 or exc.status_code >= 500
                or provider_failure(exc, 'anthropic').code == 'provider_credit_exhausted')
    return False


async def generate(system: str, user: str, model: str | None = None,
                   max_tokens: int = MAX_TOKENS, *, output_schema: dict | None = None,
                   effort: str | None = None, web_search: bool = False,
                   provider: str | None = None) -> Result:
    """Return the model's answer. Falls back to Nous Portal only on allowed errors."""
    model = model or WRITER_MODEL
    if effort not in (None, 'low', 'medium', 'high'):
        raise ValueError('invalid model effort')
    if provider not in (None, 'nous'):
        raise ValueError('invalid provider override')
    if provider == 'nous':
        if web_search:
            raise LLMError(code='provider_search_unavailable', provider='nous', fallback_status='unsupported_search')
        return await _generate_nous(system, user, max_tokens, output_schema, effort)
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
        failure = provider_failure(exc, 'anthropic')
        if not _should_fallback(exc):
            raise failure from exc
        if web_search:
            if _nous is None:
                failure.fallback_status = 'not_configured'
                raise failure from exc
            raise LLMError(code='provider_search_unavailable', provider='anthropic',
                           http_status=failure.http_status, fallback_status='unsupported_search') from exc
        log.warning('Anthropic failed code=%s; trying configured Nous fallback', failure.code)

    if _nous is None:
        failure.fallback_status = 'not_configured'
        raise failure
    return await _generate_nous(system, user, max_tokens, output_schema, effort,
                                fallback_reason=failure.code)


async def _generate_nous(system, user, max_tokens, output_schema, effort, fallback_reason=''):
    if _nous is None:
        raise LLMError(code='provider_fallback_unconfigured', provider='nous', fallback_status='not_configured')
    options = {}
    if output_schema is not None:
        system += '\nReturn ONLY JSON matching this schema:\n' + json.dumps(output_schema)
        if NOUS_MODEL in NOUS_PRICES:
            options['response_format'] = {'type': 'json_schema', 'json_schema': {
                'name': 'content_workflow', 'strict': True, 'schema': output_schema}}
    if effort is not None and NOUS_MODEL in NOUS_PRICES:
        options['reasoning_effort'] = effort
    try:
        r = await _nous.chat.completions.create(
            model=NOUS_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            **options,
        )
    except (openai.APIConnectionError, openai.APIStatusError) as exc:
        raise provider_failure(exc, 'nous') from exc
    text = (r.choices[0].message.content or "").strip()
    usage = r.usage
    raw_inp = usage.prompt_tokens if usage else None
    raw_out = usage.completion_tokens if usage else None
    inp = raw_inp if type(raw_inp) is int and raw_inp >= 0 else 0
    out = raw_out if type(raw_out) is int and raw_out >= 0 else 0
    known = (usage is not None and NOUS_MODEL in NOUS_PRICES
             and urlsplit(NOUS_BASE_URL).hostname == 'inference-api.nousresearch.com'
             and type(raw_inp) is int and raw_inp >= 0 and type(raw_out) is int and raw_out >= 0)
    price = NOUS_PRICES.get(NOUS_MODEL, (0, 0))
    cost = (inp * price[0] + out * price[1]) / 1_000_000 if known else 0
    return Result(text, "nous", model=NOUS_MODEL, stop_reason=r.choices[0].finish_reason,
                  truncated=r.choices[0].finish_reason == "length",
                  refused=r.choices[0].finish_reason == 'content_filter',
                  input_tokens=inp, output_tokens=out, cost_usd=cost, usage_known=known,
                  structured_output='response_format' in options, effort=options.get('reasoning_effort', ''),
                  fallback_reason=fallback_reason)
