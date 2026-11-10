"""Funded fallback orchestration with synthetic responses and known catalog pricing."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
import bot as app
import llm
import postlog
from briefs import Brief
from pipeline import run_pipeline
from research import facilitator_schema
from research_fixtures import routed
from reviewer import DIMENSIONS, GATES, review_schema
from revision import Settings
from test_provider_failures import rejection


def response(text):
    return NS(choices=[NS(message=NS(content=text), finish_reason='stop')],
              usage=NS(prompt_tokens=200, completion_tokens=50))


REVIEW = json.dumps({'scores': dict.fromkeys(DIMENSIONS, 8), 'gates': dict.fromkeys(GATES, 'pass'), 'issues': []})
STORY = 'STORY: شنو لونك المفضل للمحل؟'


class NousFailoverTests(unittest.IsolatedAsyncioTestCase):
    async def test_credit_failure_uses_nous_for_routing_writing_and_independent_review(self):
        primary = AsyncMock(side_effect=rejection())
        api = AsyncMock(side_effect=[response(routed('write').text), response(STORY), response(REVIEW)])
        fallback = NS(chat=NS(completions=NS(create=api)))
        with patch.object(llm._anthropic.messages, 'create', primary), patch.object(llm, '_nous', fallback):
            run = await run_pipeline('story', 'voice', 'شنو لونك المفضل؟', 'question', research=True,
                brief=Brief(story_intent='ask_audience'), settings=Settings(analyst=False))
        self.assertEqual(run.checked.status, 'accepted')
        self.assertEqual(primary.await_count, 1)
        self.assertEqual(api.await_count, 3)
        self.assertEqual([call.provider for call in run.calls], ['nous'] * 3)
        self.assertTrue(all(call.usage_known for call in run.calls))
        self.assertGreater(run.cost_usd, 0)
        self.assertEqual(run.timings[0]['fallback_reason'], 'provider_credit_exhausted')
        self.assertEqual(api.call_args_list[0].kwargs['response_format']['json_schema']['schema'], facilitator_schema())
        self.assertEqual(api.call_args_list[2].kwargs['response_format']['json_schema']['schema'], review_schema())
        self.assertIn('official_sources_required', api.call_args_list[0].kwargs['messages'][0]['content'])
        self.assertEqual(api.call_args_list[0].kwargs['reasoning_effort'], 'low')
        self.assertEqual(api.call_args_list[0].kwargs['model'], 'anthropic/claude-sonnet-5.5')

    async def test_unknown_fallback_pricing_still_blocks_further_calls(self):
        primary = AsyncMock(side_effect=rejection())
        api = AsyncMock(return_value=response(routed('write').text))
        with patch.object(llm._anthropic.messages, 'create', primary), \
             patch.object(llm, '_nous', NS(chat=NS(completions=NS(create=api)))), \
             patch.object(llm, 'NOUS_MODEL', 'custom/unpriced'):
            run = await run_pipeline('story', 'voice', 'شنو لونك المفضل؟', 'question', research=True,
                brief=Brief(story_intent='ask_audience'), settings=Settings(analyst=False))
        self.assertEqual(run.checked.failure_code, 'unknown_pricing')
        self.assertFalse(run.calls[0].usage_known)
        self.assertEqual(api.await_count, 1)

    async def test_missing_usage_stops_safely_without_breaking_token_totals(self):
        reply = response(routed('write').text)
        reply.usage = NS(prompt_tokens=None, completion_tokens=20)
        api = AsyncMock(return_value=reply)
        with patch.object(llm._anthropic.messages, 'create', AsyncMock(side_effect=rejection())), \
             patch.object(llm, '_nous', NS(chat=NS(completions=NS(create=api)))):
            run = await run_pipeline('story', 'voice', 'فكرة', 'question', research=True,
                brief=Brief(story_intent='ask_audience'), settings=Settings(analyst=False))
        self.assertEqual(run.checked.failure_code, 'unknown_pricing')
        self.assertEqual(run.input_tokens, 0)
        self.assertEqual(run.output_tokens, 20)
        self.assertEqual(api.await_count, 1)

    async def test_research_route_does_not_fake_nous_hosted_web_search(self):
        primary = AsyncMock(side_effect=rejection())
        api = AsyncMock(return_value=response(routed('research').text))
        with patch.object(llm._anthropic.messages, 'create', primary), \
             patch.object(llm, '_nous', NS(chat=NS(completions=NS(create=api)))):
            run = await run_pipeline('story', 'voice', 'سعر الصرف الرسمي', 'question', research=True,
                brief=Brief(story_intent='educational'), settings=Settings(analyst=False))
        self.assertEqual(run.checked.failure_code, 'provider_search_unavailable')
        self.assertEqual(run.checked.text, '')
        self.assertEqual(api.await_count, 1)
        self.assertEqual(primary.await_count, 1)

    async def test_telegram_reports_credit_failover_once_and_delivers_approved_script(self):
        primary = AsyncMock(side_effect=rejection())
        plan = json.dumps({'audience_need': 'neutral question', 'objection': '', 'purpose': 'conversation',
            'framework': 'none', 'logic_chain': [], 'missing_information': '', 'clarification_question': ''})
        api = AsyncMock(side_effect=[response(routed('write').text), response(plan), response(STORY), response(REVIEW)])
        status = NS(edit_text=AsyncMock(), delete=AsyncMock())
        update = NS(effective_chat=NS(id=123), message=NS(text='شنو لونك المفضل؟', reply_text=AsyncMock(return_value=status)))
        context = NS(chat_data={'family': 'story', 'format': 'story', 'angle': 'story_ask_audience', 'structure_id': 'question'})
        with tempfile.TemporaryDirectory() as tmp, patch.object(postlog, 'LOG', Path(tmp) / 'posts.jsonl'), \
             patch.object(app, '_allowed_chat', return_value=True), patch.object(app, 'pilot_check', return_value=(True, '')), \
             patch.object(llm._anthropic.messages, 'create', primary), \
             patch.object(llm, '_nous', NS(chat=NS(completions=NS(create=api)))):
            await app.on_text(update, context)
            record = postlog.read_all()[0]
        messages = [call.args[0] for call in update.message.reply_text.call_args_list]
        self.assertEqual(sum('انتقلت المحاولة إلى Nous' in text for text in messages), 1)
        self.assertIn('شنو لونك المفضل للمحل؟', messages)
        self.assertEqual(record['quality_status'], 'accepted')
        self.assertTrue(record['usage_known'])
        self.assertEqual(primary.await_count, 1)
