"""Mock SDK responses at the only model transport boundary; no credentials used."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
import httpx
import anthropic
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
import llm


def response(reason='end_turn'):
    return NS(stop_reason=reason, content=[NS(type='text', text='response')],
              usage=NS(input_tokens=100, output_tokens=50, cache_read_input_tokens=20,
                       cache_creation_input_tokens=10))


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_usage_and_truncation_are_preserved(self):
        for reason in ('end_turn', 'max_tokens', 'refusal'):
            with patch.object(llm._anthropic.messages, 'create', AsyncMock(return_value=response(reason))):
                result = await llm.generate('system', 'user')
            self.assertEqual(result.input_tokens, 100)
            self.assertEqual(result.cache_read, 20)
            self.assertGreater(result.cost_usd, 0)
            self.assertEqual(result.truncated, reason == 'max_tokens')
            self.assertEqual(result.refused, reason == 'refusal')

    async def test_unknown_model_price_is_not_zero_cost_assumption(self):
        with patch.object(llm._anthropic.messages, 'create', AsyncMock(return_value=response())):
            result = await llm.generate('system', 'user', model='custom-model')
        self.assertFalse(result.usage_known)

    async def test_unauthorized_never_falls_back_or_leaks_error(self):
        request = httpx.Request('POST', 'https://api.anthropic.com/v1/messages')
        exc = anthropic.AuthenticationError('SECRET_IN_PROVIDER_ERROR', response=httpx.Response(
            401, request=request), body=None)
        fallback = NS(chat=NS(completions=NS(create=AsyncMock())))
        with patch.object(llm._anthropic.messages, 'create', AsyncMock(side_effect=exc)), \
             patch.object(llm, '_nous', fallback):
            with self.assertRaises(llm.LLMError) as ctx:
                await llm.generate('system', 'user')
        fallback.chat.completions.create.assert_not_awaited()
        self.assertNotIn('SECRET', str(ctx.exception))

    async def test_connection_failure_uses_configured_fallback_once(self):
        exc = anthropic.APIConnectionError(request=httpx.Request('POST', 'https://api.anthropic.com'))
        fallback = NS(chat=NS(completions=NS(create=AsyncMock(return_value=NS(
            choices=[NS(message=NS(content='fallback'), finish_reason='length')],
            usage=NS(prompt_tokens=20, completion_tokens=30))))))
        with patch.object(llm._anthropic.messages, 'create', AsyncMock(side_effect=exc)), \
             patch.object(llm, '_nous', fallback):
            result = await llm.generate('system', 'user')
        fallback.chat.completions.create.assert_awaited_once()
        self.assertEqual(result.provider, 'nous')
        self.assertEqual(result.output_tokens, 30)
        self.assertTrue(result.truncated)
        self.assertFalse(result.usage_known)
