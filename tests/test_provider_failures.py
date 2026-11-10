"""Provider-confirmed billing failures must not be hidden as routing/content failures."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
import anthropic
import httpx
import openai
import llm
from briefs import Brief
from diagnostics import diagnostic_report, failure_message
from pipeline import run_pipeline
from research_fixtures import routed
from revision import Settings


def rejection(status=400, message='Your credit balance is too low to access the Anthropic API. PRIVATE_PROVIDER_TEXT'):
    request = httpx.Request('POST', 'https://api.anthropic.com/v1/messages')
    return anthropic.APIStatusError(message, response=httpx.Response(status, request=request),
        body={'error': {'type': 'invalid_request_error', 'message': message}})


class ProviderClassificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_confirmed_credit_failure_uses_funded_configured_fallback_once(self):
        response = NS(choices=[NS(message=NS(content='fallback'), finish_reason='stop')],
                      usage=NS(prompt_tokens=20, completion_tokens=10))
        fallback = NS(chat=NS(completions=NS(create=AsyncMock(return_value=response))))
        api = AsyncMock(side_effect=rejection())
        with patch.object(llm._anthropic.messages, 'create', api), patch.object(llm, '_nous', fallback):
            result = await llm.generate('system', 'data')
        self.assertEqual(result.provider, 'nous')
        self.assertEqual(result.fallback_reason, 'provider_credit_exhausted')
        self.assertTrue(result.usage_known)
        self.assertEqual(api.await_count, 1)
        fallback.chat.completions.create.assert_awaited_once()

    async def test_credit_failure_without_fallback_keeps_billing_reason(self):
        with patch.object(llm._anthropic.messages, 'create', AsyncMock(side_effect=rejection())), \
             patch.object(llm, '_nous', None):
            with self.assertRaises(llm.LLMError) as caught:
                await llm.generate('system', 'data')
        self.assertEqual(caught.exception.code, 'provider_credit_exhausted')
        self.assertEqual(caught.exception.fallback_status, 'not_configured')
        self.assertNotIn('PRIVATE', str(caught.exception))

    def test_other_http_errors_are_not_mislabeled_as_credit(self):
        cases = {400: 'provider_request_rejected', 401: 'provider_authentication',
                 402: 'provider_billing_required', 403: 'provider_permission',
                 404: 'provider_model_unavailable', 422: 'provider_request_rejected',
                 429: 'provider_rate_limit', 503: 'provider_unavailable'}
        for status, code in cases.items():
            with self.subTest(status=status):
                result = llm.provider_failure(rejection(status, 'PRIVATE generic rejection'), 'anthropic')
                self.assertEqual(result.code, code)
                self.assertNotIn('PRIVATE', str(result))

    def test_rejected_payload_that_mentions_credit_is_not_a_confirmed_billing_failure(self):
        result = llm.provider_failure(rejection(400, 'Invalid field description: "insufficient credits"'), 'anthropic')
        self.assertEqual(result.code, 'provider_request_rejected')

    def test_fallback_account_quota_is_a_billing_signal_not_a_temporary_rate_limit(self):
        request = httpx.Request('POST', 'https://inference-api.nousresearch.com/v1/chat/completions')
        error = openai.RateLimitError('PRIVATE', response=httpx.Response(429, request=request),
                                     body={'code': 'insufficient_quota', 'message': 'PRIVATE'})
        result = llm.provider_failure(error, 'nous')
        self.assertEqual(result.code, 'provider_credit_exhausted')
        self.assertEqual(result.provider, 'nous')

    def test_connection_and_timeout_do_not_imply_insufficient_funds(self):
        request = httpx.Request('POST', 'https://api.anthropic.com/v1/messages')
        self.assertEqual(llm.provider_failure(anthropic.APIConnectionError(request=request), 'anthropic').code,
                         'provider_connection')
        self.assertEqual(llm.provider_failure(anthropic.APITimeoutError(request=request), 'anthropic').code,
                         'provider_timeout')


class ProviderFailurePipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_facilitator_billing_error_reaches_user_and_safe_diagnostics(self):
        with patch.object(llm._anthropic.messages, 'create', AsyncMock(side_effect=rejection())), patch.object(llm, '_nous', None):
            run = await run_pipeline('story', 'voice', 'فكرة', 'tip', research=True,
                brief=Brief(story_intent='educational'), settings=Settings(analyst=False))
        self.assertEqual(run.checked.failure_stage, 'facilitator')
        self.assertEqual(run.checked.failure_code, 'provider_credit_exhausted')
        self.assertEqual(len(run.calls), 0)
        self.assertEqual(run.timings[0]['http_status'], 400)
        self.assertEqual(run.timings[0]['error_code'], 'provider_credit_exhausted')
        self.assertEqual(run.timings[0]['provider'], 'anthropic')
        self.assertFalse(run.checked.manual_review_ready)
        message = failure_message({'failure_code': run.checked.failure_code, 'stage_timings': run.timings}, 'fixture')
        self.assertIn('رصيد', message)
        self.assertIn('مشكلة فوترة', message)
        self.assertIn('NOUS_API_KEY', message)
        record = {'quality_status': run.checked.status, 'failure_code': run.checked.failure_code,
                  'stage_timings': run.timings}
        with patch('diagnostics.authorized_post', return_value=record):
            report = diagnostic_report('fixture', 123)
        self.assertEqual(report['stages'][0]['http_status'], 400)
        self.assertEqual(report['stages'][0]['error_code'], 'provider_credit_exhausted')
        self.assertNotIn('PRIVATE', json.dumps(report))

    async def test_credit_failure_survives_research_wrapper(self):
        real_generate = llm.generate
        async def transport(system, user, **kwargs):
            if system.startswith('Choose the workflow'):
                return routed('research')
            return await real_generate(system, user, **kwargs)
        with patch('revision.generate', transport), \
             patch.object(llm, '_nous', None), \
             patch.object(llm._anthropic.messages, 'create', AsyncMock(side_effect=rejection())):
            run = await run_pipeline('story', 'voice', 'سعر الصرف', 'tip', research=True,
                brief=Brief(story_intent='educational'), settings=Settings(analyst=False))
        self.assertEqual(run.checked.failure_stage, 'research')
        self.assertEqual(run.checked.failure_code, 'provider_credit_exhausted')

    async def test_generic_facilitator_rejection_is_not_called_credit_exhaustion(self):
        with patch.object(llm._anthropic.messages, 'create', AsyncMock(side_effect=rejection(400, 'Invalid request PRIVATE'))):
            run = await run_pipeline('story', 'voice', 'فكرة', 'tip', research=True,
                brief=Brief(story_intent='educational'), settings=Settings(analyst=False))
        self.assertEqual(run.checked.failure_code, 'provider_request_rejected')
        self.assertNotEqual(run.checked.failure_code, 'provider_credit_exhausted')
