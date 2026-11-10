"""Offline search transport, evidence provenance, budget and format-repair regressions."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
import llm
from briefs import Brief
from pipeline import run_pipeline
from research import parse_research, requires_official
from research_fixtures import researched, routed
from reviewer import DIMENSIONS, GATES, reviewer_system
from revision import Settings
from test_review_protocol import sdk_response

STORY = 'STORY: شلون ترتب أسعار بضاعتك إذا تغيّرت كلفة الشراء؟'


def review(gates=None, issues=None):
    return llm.Result(json.dumps({'scores': dict.fromkeys(DIMENSIONS, 8),
        'gates': gates or dict.fromkeys(GATES, 'pass'), 'issues': issues or []}), 'mock')


class SearchTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_uses_bounded_tool_and_keeps_only_actual_result_citations(self):
        response = sdk_response(researched().text)
        response.usage.server_tool_use = NS(web_search_requests=2)
        citation = NS(type='web_search_result_location', url='https://cbi.iq/example',
                      title='Decision', cited_text='Dated official excerpt')
        fake = NS(type='web_search_result_location', url='https://cbi.iq/invented',
                  title='Invented', cited_text='Not a retrieved result')
        response.content[0].citations = [citation, fake]
        response.content.insert(0, NS(type='web_search_tool_result', content=[
            NS(type='web_search_result', url=citation.url)]))
        api = AsyncMock(return_value=response)
        with patch.object(llm._anthropic.messages, 'create', api):
            result = await llm.generate('research', 'topic', model=llm.FAST_MODEL, web_search=True)
        self.assertEqual(api.call_args.kwargs['tools'][0]['max_uses'], 2)
        self.assertEqual(result.sources, [{'url': citation.url, 'title': 'Decision',
                                         'excerpt': 'Dated official excerpt'}])
        self.assertEqual(result.search_requests, 2)
        self.assertAlmostEqual(result.cost_usd, .02 + llm.estimate_cost(llm.FAST_MODEL, 100, 50, 0, 0))

    async def test_tool_failure_is_not_treated_as_success(self):
        response = sdk_response(researched().text)
        response.usage.server_tool_use = NS(web_search_requests=1)
        response.content.append(NS(type='web_search_tool_result',
                                   content=NS(type='web_search_tool_result_error', error_code='unavailable')))
        with patch.object(llm._anthropic.messages, 'create', AsyncMock(return_value=response)):
            result = await llm.generate('research', 'topic', web_search=True)
        self.assertTrue(result.search_failed)
        with self.assertRaises(ValueError):
            parse_research(result)

    async def test_search_never_falls_back_to_a_provider_without_search(self):
        import anthropic
        import httpx
        error = anthropic.APIConnectionError(request=httpx.Request('POST', 'https://api.anthropic.com'))
        fallback = NS(chat=NS(completions=NS(create=AsyncMock())))
        with patch.object(llm._anthropic.messages, 'create', AsyncMock(side_effect=error)), \
             patch.object(llm, '_nous', fallback):
            with self.assertRaises(llm.LLMError):
                await llm.generate('research', 'topic', web_search=True)
        fallback.chat.completions.create.assert_not_awaited()


class ResearchPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, responses, topic='سعر صرف الدولار', **kwargs):
        model = AsyncMock(side_effect=[routed(), *responses])
        with patch('revision.generate', model):
            run = await run_pipeline('story', 'voice', topic, 'question', research=True,
                brief=Brief(story_intent='ask_audience', structure_id='question'),
                settings=kwargs.pop('settings', Settings(analyst=False)), **kwargs)
        return run, model

    async def test_research_precedes_writer_and_evidence_reaches_independent_review(self):
        finding = researched()
        run, model = await self.run_case([finding, llm.Result(STORY, 'mock'), review()])
        self.assertEqual(run.checked.status, 'accepted')
        self.assertEqual([t['stage'] for t in run.timings], ['facilitator', 'research', 'writer', 'review'])
        self.assertTrue(model.call_args_list[1].kwargs['web_search'])
        for call in model.call_args_list[2:]:
            evidence = json.loads(call.args[1])['research']
            self.assertEqual(evidence['sources'], finding.sources)
        self.assertEqual(run.checked.research['status'], 'ready')

    async def test_topic_clarification_stops_before_writing(self):
        clarification = llm.Result(json.dumps({'status': 'needs_clarification',
            'clarification': 'تقصد السعر الرسمي لو سعر السوق؟', 'summary': ''}), 'mock')
        run, model = await self.run_case([clarification])
        self.assertEqual(model.await_count, 2)
        self.assertEqual(run.checked.status, 'needs_clarification')
        self.assertIn('الرسمي', run.checked.clarification)
        run, _ = await self.run_case([clarification], clarification_allowed=False)
        self.assertEqual(run.checked.status, 'blocked')
        self.assertEqual(run.checked.clarification, '')

    async def test_absent_fabricated_or_non_official_evidence_stops_writing(self):
        no_sources = researched(); no_sources.sources = []
        secondary = researched(); secondary.sources[0]['url'] = 'https://news.example/article'
        spoof = researched(); spoof.sources[0]['url'] = 'https://cbi.iq.attacker.example/article'
        for response, code in ((no_sources, 'research_unavailable'),
                               (secondary, 'research_unsupported'), (spoof, 'research_unsupported')):
            run, model = await self.run_case([response])
            self.assertEqual(model.await_count, 2)
            self.assertNotEqual(run.checked.status, 'accepted')
            self.assertEqual(run.checked.failure_code, code)
            self.assertEqual(run.checked.text, '')

    async def test_search_cost_reservation_respects_existing_budget(self):
        run, model = await self.run_case([], settings=Settings(analyst=False, max_cost_usd=.01))
        self.assertEqual(model.await_count, 1)
        self.assertNotIn('web_search', model.call_args.kwargs)
        self.assertEqual(run.checked.failure_code, 'resource_limit')

    async def test_incomplete_research_never_reaches_writer(self):
        for response in (llm.Result('', 'mock', truncated=True),
                         llm.Result('', 'mock', stop_reason='pause_turn'),
                         llm.Result('', 'mock', refused=True),
                         llm.Result('not json', 'mock')):
            run, model = await self.run_case([response])
            self.assertEqual(model.await_count, 2)
            self.assertEqual(run.checked.failure_code, 'research_unavailable')
            self.assertEqual(run.checked.research['status'], 'unavailable')
            self.assertEqual(run.checked.text, '')

    async def test_full_research_analyst_rewrite_and_review_fit_default_budget(self):
        gates = {**dict.fromkeys(GATES, 'pass'), 'format_identity': 'fail'}
        issue = {'section': 'STORY', 'reason': 'Needs a single question',
                 'instruction': 'Ask one neutral audience question'}
        run, model = await self.run_case([researched(), llm.Result('{}', 'mock'),
            llm.Result(STORY, 'mock'), review(gates, [issue]),
            llm.Result(json.dumps({'replacements': {'STORY': 'شنو الطريقة اللي تناسبك بتسعير بضاعتك؟'}}), 'mock'),
            review()], settings=Settings())
        self.assertEqual(run.checked.status, 'accepted')
        self.assertEqual(model.await_count, 7)

    async def test_format_only_failure_is_rewritten_then_reviewed(self):
        gates = {**dict.fromkeys(GATES, 'pass'), 'format_identity': 'fail'}
        issue = {'section': 'STORY', 'reason': 'Answers instead of asking',
                 'instruction': 'Ask one neutral audience question'}
        run, model = await self.run_case([researched(), llm.Result(STORY, 'mock'),
            review(gates, [issue]), llm.Result(json.dumps({'replacements': {'STORY':
                'شنو الطريقة اللي تناسبك بتسعير بضاعتك؟'}}), 'mock'), review()])
        self.assertEqual(run.checked.status, 'accepted')
        self.assertEqual(run.checked.attempts, 2)
        self.assertEqual([t['stage'] for t in run.timings],
                         ['facilitator', 'research', 'writer', 'review', 'revision', 'review'])
        self.assertIn('research', json.loads(model.call_args_list[4].args[1]))

    async def test_research_does_not_bypass_uncertain_factual_gate(self):
        gates = {**dict.fromkeys(GATES, 'pass'), 'factual_integrity': 'uncertain', 'format_identity': 'fail'}
        run, model = await self.run_case([researched(), llm.Result(STORY, 'mock'), review(gates,
            [{'section': 'STORY', 'reason': 'Unsupported premise', 'instruction': 'Verify premise'}])])
        self.assertEqual(model.await_count, 4)
        self.assertEqual(run.checked.status, 'blocked')
        self.assertEqual(run.checked.failure_code, 'critical_gate')

    def test_official_policy_and_question_contract_are_explicit(self):
        self.assertTrue(requires_official('قرار البنك المركزي عن سعر الصرف'))
        self.assertFalse(requires_official('شنو لونك المفضل؟'))
        system = reviewer_system('story', story_intent='ask_audience', structure_id='question')
        self.assertIn('preference', system)
        self.assertIn('official primary source', system)
