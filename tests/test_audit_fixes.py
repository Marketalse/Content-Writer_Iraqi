"""Regression evidence for the ten PROJECT BREAKER findings; no live integrations."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
import bot as app
import pilot
import postlog
import topics_batch
from briefs import Brief
from llm import Result
from pipeline import Run, run_pipeline
from quality import Checked
from research import parse_route, parse_research
from revision import Settings
from research_fixtures import researched, routed
from reviewer import DIMENSIONS, GATES


def reviewed(**overrides):
    gates = dict.fromkeys(GATES, 'pass')
    gates.update(overrides)
    return Result(json.dumps({'scores': dict.fromkeys(DIMENSIONS, 8), 'gates': gates, 'issues': []}), 'mock')


class RoutingParserTests(unittest.TestCase):
    def test_duplicate_routing_keys_use_conservative_fallback(self):
        for field, first, second in (('factual_claims', 'true', 'false'),
                                     ('action', '"research"', '"write"')):
            data = routed('write').text
            original = '"' + field + '": ' + ('false' if field == 'factual_claims' else '"write"')
            duplicate = f'"{field}": {first}, "{field}": {second}'
            route = parse_route(Result(data.replace(original, duplicate), 'mock'), 'فكرة', Brief())
            self.assertTrue(route['fallback'])
            self.assertEqual(route['action'], 'research')

    def test_research_duplicate_keys_are_rejected(self):
        response = researched()
        response.text = response.text.replace('"status": "ready"', '"status": "unsupported", "status": "ready"')
        with self.assertRaises(ValueError): parse_research(response)

    def test_invalid_booleans_do_not_disable_verification(self):
        result = parse_route(routed('write', factual_claims='false'), 'فكرة', Brief())
        self.assertTrue(result['fallback'])


class RoutingBoundaryTests(unittest.TestCase):
    def test_preference_options_and_word_counts_are_not_rate_claims(self):
        for topic in ('شنو تفضّل: 1 الدولار لو 2 الدينار؟',
                      'شنو تفضّل: ١ الدولار لو ٢ الدينار؟',
                      'اكتب سؤال عن تفضيل الدولار لو الدينار بطول 20 كلمة',
                      'اكتب سؤال عن تفضيل الدولار لو الدينار بطول ٢٠ كلمة',
                      'تفضّل ورقة 500 دينار لو 1000 دينار؟'):
            with self.subTest(topic=topic):
                result = parse_route(routed('write'), topic, Brief())
                self.assertEqual(result['action'], 'write')
                self.assertFalse(result['official_sources_required'])

    def test_actual_rates_percentages_and_numbered_policies_require_evidence(self):
        for topic in ('السعر الرسمي للدولار 1520 دينار', 'السعر الرسمي للدولار ١٥٢٠ دينار',
                      '1520 دينار للدولار', 'الدولار يساوي 1520 دينار',
                      'انخفض الدينار بنسبة 15%', 'قانون رقم ٣ لسنة ٢٠٢٦'):
            with self.subTest(topic=topic):
                result = parse_route(routed('rewrite'), topic, Brief())
                self.assertEqual(result['action'], 'research')
                self.assertTrue(result['official_sources_required'])

    def test_factual_premise_in_source_text_cannot_hide_behind_style_request(self):
        result = parse_route(routed('rewrite'), 'غيّر الأسلوب',
                             Brief(source_material='السعر الرسمي للدولار 1520 دينار'))
        self.assertEqual(result['action'], 'research')

    def test_facilitator_prompt_does_not_predeclare_neutral_currency_topic_as_official(self):
        from research import research_prompt
        data = json.loads(research_prompt('شنو تفضل الدولار لو الدينار؟', 'question', 'story', Brief()))
        self.assertFalse(data['official_sources_required'])


class FacilitatorRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_neutral_question_and_style_rewrite_skip_search_but_keep_review(self):
        for action in ('write', 'rewrite'):
            response = 'STORY: شنو لونك المفضل؟'
            replies = [routed(action), Result(response, 'mock'), reviewed()]
            model = AsyncMock(side_effect=replies)
            with patch('revision.generate', model):
                run = await run_pipeline('story', 'voice', 'شنو لونك المفضل؟', 'question',
                    research=True, brief=Brief(story_intent='ask_audience', source_material='شنو لونك المفضل؟'),
                    settings=Settings(analyst=False))
            self.assertEqual(run.checked.status, 'accepted')
            self.assertEqual([t['stage'] for t in run.timings], ['facilitator', 'writer', 'review'])
            self.assertFalse(any(c.kwargs.get('web_search') for c in model.call_args_list))
            self.assertEqual(run.checked.research['status'], 'not_needed')

    async def test_no_search_does_not_bypass_uncertain_review(self):
        model = AsyncMock(side_effect=[routed('write'), Result('STORY: شنو لونك المفضل؟', 'mock'),
                                       reviewed(factual_integrity='uncertain')])
        with patch('revision.generate', model):
            run = await run_pipeline('story', 'voice', 'فكرة', 'question', research=True,
                brief=Brief(story_intent='ask_audience'), settings=Settings(analyst=False))
        self.assertEqual(run.checked.status, 'blocked')
        self.assertEqual(run.checked.failure_code, 'critical_gate')

    async def test_missing_context_asks_once_without_writing(self):
        model = AsyncMock(return_value=routed('clarify', reason='missing_context', clarification='شنو النص؟'))
        with patch('revision.generate', model):
            run = await run_pipeline('story', 'voice', 'اعد الصياغة', 'question', research=True,
                brief=Brief(story_intent='ask_audience'), settings=Settings(analyst=False))
        self.assertEqual(run.checked.status, 'needs_clarification')
        self.assertEqual(model.await_count, 1)

    async def test_bad_router_falls_back_to_cited_research(self):
        model = AsyncMock(side_effect=[Result('not JSON', 'mock'), researched(),
            Result('STORY: شنو لونك المفضل؟', 'mock'), reviewed()])
        with patch('revision.generate', model):
            run = await run_pipeline('story', 'voice', 'فكرة', 'question', research=True,
                brief=Brief(story_intent='ask_audience'), settings=Settings(analyst=False))
        self.assertEqual(run.checked.status, 'accepted')
        self.assertTrue(run.checked.routing['fallback'])
        self.assertTrue(model.call_args_list[1].kwargs['web_search'])


class StoryRepairTests(unittest.IsolatedAsyncioTestCase):
    async def test_labeled_and_unlabeled_word_and_character_overflows_are_reassessed(self):
        for body in ('كلمة ' * 76, 'ك' * 801):
            for label in ('', 'STORY: '):
                model = AsyncMock(side_effect=[Result(label + body, 'mock'),
                    Result('STORY: فكرة بسيطة ومفيدة نوصلها بوضوح.', 'mock'), reviewed()])
                with patch('revision.generate', model):
                    run = await run_pipeline('story', 'voice', 'فكرة', 'tip',
                        brief=Brief(story_intent='educational'), settings=Settings(analyst=False))
                self.assertEqual(run.checked.status, 'accepted')
                self.assertEqual([t['stage'] for t in run.timings], ['writer', 'revision', 'review'])

    async def test_no_allowance_or_ambiguous_structure_stays_blocked(self):
        for body in ('كلمة ' * 76, 'HOOK: بداية\nCONTENT: شرح\nCTA: تابع'):
            model = AsyncMock(return_value=Result(body, 'mock'))
            with patch('revision.generate', model):
                run = await run_pipeline('story', 'voice', 'فكرة', 'tip',
                    brief=Brief(story_intent='educational'), settings=Settings(analyst=False, max_revisions=0))
            self.assertEqual(run.checked.status, 'blocked')
            self.assertEqual(model.await_count, 1)

    async def test_shortening_cannot_remove_a_required_fact(self):
        model = AsyncMock(side_effect=[Result('كلمة ' * 76 + 'حقيقة موثقة', 'mock'),
                                       Result('STORY: فكرة بسيطة ومفيدة.', 'mock')])
        with patch('revision.generate', model):
            run = await run_pipeline('story', 'voice', 'فكرة', 'tip',
                brief=Brief(story_intent='educational'), verified_facts=(('حقيقة موثقة', 'fixture'),),
                settings=Settings(analyst=False))
        self.assertEqual(run.checked.failure_code, 'verified_fact_missing')
        self.assertEqual(run.checked.status, 'blocked')


class JournalRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / 'posts.jsonl'
        self.patches = [patch.object(postlog, 'LOG', self.log),
                        patch.object(pilot, 'CONFIG', Path(self.tmp.name) / 'pilots.json'),
                        patch.dict(os.environ, {'ALLOWED_CHAT_IDS': '', 'OWNER_CHAT_ID': ''})]
        for p in self.patches: p.start()
        self.pid = postlog.log_post({'chat_id': 123, 'cost_usd': .001, 'quality_status': 'accepted'})

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def test_incomplete_tail_is_preserved_and_valid_history_remains_usable(self):
        with self.log.open('ab') as file: file.write(b'{"event":')
        with self.assertLogs('postlog', level='WARNING'):
            rows = postlog.read_all()
        self.assertEqual([row['id'] for row in rows], [self.pid])
        tails = list(self.log.parent.glob('posts.jsonl.torn-*'))
        self.assertEqual(len(tails), 1)
        self.assertEqual(tails[0].read_bytes(), b'{"event":')
        postlog.log_post({'chat_id': 123, 'cost_usd': .002})
        self.assertEqual(pilot.usage(123)[0], 2)
        self.assertTrue(postlog.mark_published(self.pid))

    def test_interior_or_terminated_corruption_is_not_silently_removed(self):
        valid = self.log.read_bytes()
        for contents in (valid + b'bad\n' + valid, valid + b'{"event":\n', valid + b'[]\n'):
            self.log.write_bytes(contents)
            with self.assertRaises(OSError): postlog.read_all()
            self.assertEqual(self.log.read_bytes(), contents)

    def test_complete_final_record_without_newline_can_be_appended(self):
        self.log.write_bytes(self.log.read_bytes().rstrip(b'\n'))
        postlog.log_post({'chat_id': 123, 'cost_usd': .002})
        self.assertEqual(len(postlog.read_all()), 2)

    async def test_trial_storage_failure_returns_a_message_without_model_calls(self):
        pilot.add(123, 'fixture', max_usd=10)
        with self.log.open('ab') as file: file.write(b'bad\n')
        upd = SimpleNamespace(effective_chat=SimpleNamespace(id=123),
            message=SimpleNamespace(text='شنو لونك المفضل؟', reply_text=AsyncMock()))
        ctx = SimpleNamespace(chat_data={'format': 'story', 'family': 'story',
            'angle': 'story_ask_audience', 'structure_id': 'question'})
        with patch.object(app, '_allowed_chat', return_value=True), patch.object(app, 'run_pipeline', AsyncMock()) as model:
            await app.on_text(upd, ctx)
        model.assert_not_awaited()
        self.assertIn('بيانات', upd.message.reply_text.call_args.args[0])

    async def test_failed_save_withholds_content_and_explains_the_storage_problem(self):
        status = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
        upd = SimpleNamespace(effective_chat=SimpleNamespace(id=123),
            message=SimpleNamespace(text='شنو لونك المفضل؟', reply_text=AsyncMock(return_value=status)))
        ctx = SimpleNamespace(chat_data={'format': 'story', 'family': 'story',
            'angle': 'story_ask_audience', 'structure_id': 'question'})
        checked = Checked('STORY: شنو لونك المفضل؟', 'mock', status='accepted', story_intent='ask_audience')
        with patch.object(app, '_allowed_chat', return_value=True), patch.object(app, 'pilot_check', return_value=(True, '')), \
             patch.object(app, 'run_pipeline', AsyncMock(return_value=Run(checked))), \
             patch.object(app, 'log_post', side_effect=OSError('synthetic disk failure')):
            await app.on_text(upd, ctx)
        self.assertIn('حفظ', status.edit_text.call_args.args[0])
        status.delete.assert_not_awaited()
        self.assertFalse(any(call.args[0] == 'شنو لونك المفضل؟' for call in upd.message.reply_text.call_args_list))

    async def test_storage_error_handler_explains_failure_without_private_error_text(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        with self.assertLogs('iraqi-content-bot', level='ERROR') as logs:
            await app.on_handler_error(SimpleNamespace(message=message),
                                       SimpleNamespace(error=OSError('PRIVATE_DISK_LOCATION')))
        self.assertIn('البيانات', message.reply_text.call_args.args[0])
        self.assertNotIn('PRIVATE_DISK_LOCATION', str(logs.output))
        self.assertNotIn('PRIVATE_DISK_LOCATION', message.reply_text.call_args.args[0])


class PilotConfigAtomicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = Path(self.tmp.name) / 'pilots.json'
        self.patches = [patch.object(pilot, 'CONFIG', self.config),
                        patch.dict(os.environ, {'ALLOWED_CHAT_IDS': '', 'OWNER_CHAT_ID': ''})]
        for p in self.patches: p.start()
        pilot.add(123, 'fixture', max_usd=10)

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def test_replace_failure_preserves_the_previous_settings(self):
        old = self.config.read_bytes()
        with patch('os.replace', side_effect=OSError('synthetic replacement failure')):
            with self.assertRaises(OSError): pilot.add(456, 'new fixture')
        self.assertEqual(self.config.read_bytes(), old)
        self.assertEqual(list(self.config.parent.glob('*.tmp')), [])

    def test_previous_valid_settings_are_backed_up(self):
        old = self.config.read_bytes()
        pilot.add(456, 'new fixture')
        self.assertEqual(self.config.with_suffix('.json.bak').read_bytes(), old)
        self.assertIn('456', json.loads(self.config.read_text())['pilots'])

    def test_corruption_fails_closed_even_if_an_old_backup_granted_access(self):
        self.config.write_text('{"pilots":')
        allowed, message = pilot.check(123)
        self.assertFalse(allowed)
        self.assertIn('بيانات', message)
        self.assertEqual(self.config.read_text(), '{"pilots":')

    def test_invalid_schema_is_an_operational_error(self):
        self.config.write_text('{"pilots": []}')
        with self.assertRaises(OSError): pilot._load()


class PublicationIdempotencyTests(unittest.TestCase):
    def test_repeat_confirmation_keeps_one_event_and_the_original_date(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(postlog, 'LOG', Path(tmp) / 'posts.jsonl'):
            pid = postlog.log_post({'quality_status': 'accepted'})
            with patch.object(postlog, '_now', return_value='first-publication'):
                self.assertTrue(postlog.mark_published(pid))
            with patch.object(postlog, '_now', return_value='later-confirmation'):
                self.assertTrue(postlog.mark_published(pid))
            events = [r for r in postlog.read_all() if r['event'] == 'published']
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]['date'], 'first-publication')


class BatchValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_concurrency_fails_before_preparing_work(self):
        for value in (0, -1, 17, True, 1.5, '4'):
            with patch.object(topics_batch, 'build_system_prompt', side_effect=AssertionError('work started')):
                with self.assertRaises(ValueError):
                    await topics_batch.write_all([{'format': 'story'}], .25, value)

    async def test_invalid_budgets_fail_before_preparing_work(self):
        for value in (0, -1, float('nan'), float('inf'), True, '1'):
            with patch.object(topics_batch, 'build_system_prompt', side_effect=AssertionError('work started')):
                with self.assertRaises(ValueError):
                    await topics_batch.write_all([{'format': 'story'}], value, 1)


class BatchBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def batch(self, budget, costs, *, known=True, fail=False, concurrency=4):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = []
            async def fake(*args, **kwargs):
                index = len(calls)
                calls.append(index)
                await asyncio.sleep(.001)
                if fail:
                    raise RuntimeError('PRIVATE_PROVIDER_TEXT')
                cost = costs[min(index, len(costs) - 1)]
                return Run(Checked('STORY: محتوى تجريبي\nINTERACTION: شنو رأيك؟', 'mock', status='accepted'),
                           [Result('', 'mock', cost_usd=cost, usage_known=known)])
            rows = [{'id': str(i), 'name': 'Synthetic topic', 'format': 'story'} for i in range(4)]
            with patch.object(topics_batch, 'ROOT', root), patch.object(topics_batch, 'SCRIPTS', root / 'scripts'), \
                 patch.object(topics_batch, 'INDEX', root / 'index.csv'), \
                 patch.object(topics_batch.Settings, 'from_env', return_value=Settings(max_cost_usd=.1)), \
                 patch.object(topics_batch, 'run_pipeline', fake):
                await asyncio.wait_for(topics_batch.write_all(rows, budget, concurrency), 2)
            saved = list((root / 'scripts').glob('*.md'))
            index_text = (root / 'index.csv').read_text() if (root / 'index.csv').exists() else ''
            return len(calls), len(saved), index_text

    async def test_concurrent_jobs_reserve_budget_before_starting(self):
        calls, saved, _ = await self.batch(.1, [.1])
        self.assertEqual(calls, 1)
        self.assertEqual(saved, 1)

    async def test_unused_allowance_is_released_for_later_work(self):
        calls, saved, _ = await self.batch(.15, [.05])
        self.assertEqual(calls, 2)
        self.assertEqual(saved, 2)

    async def test_too_small_budget_starts_no_work(self):
        calls, _, _ = await self.batch(.05, [.05])
        self.assertEqual(calls, 0)

    async def test_unknown_pricing_and_attempt_failure_stop_more_work(self):
        calls, _, _ = await self.batch(.1, [.01], known=False)
        self.assertEqual(calls, 1)
        calls, _, index_text = await self.batch(.1, [.01], fail=True)
        self.assertEqual(calls, 1)
        self.assertNotIn('PRIVATE_PROVIDER_TEXT', index_text)

    async def test_observed_overshoot_stops_new_work(self):
        calls, _, _ = await self.batch(.5, [.2], concurrency=1)
        self.assertEqual(calls, 1)

    async def test_cancellation_does_not_leave_workers_waiting(self):
        entered = asyncio.Event()
        async def pending(*args, **kwargs):
            entered.set()
            await asyncio.Event().wait()
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(topics_batch, 'SCRIPTS', Path(tmp) / 'scripts'), \
             patch.object(topics_batch, 'run_pipeline', pending):
            rows = [{'id': str(i), 'name': 'Synthetic topic', 'format': 'story'} for i in range(4)]
            task = asyncio.create_task(topics_batch.write_all(rows, .25, 4))
            await asyncio.wait_for(entered.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 1)


class DeploymentGateTests(unittest.TestCase):
    def test_main_and_all_pull_requests_have_ci_coverage(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / '.github/workflows/platform-intelligence.yml').read_text()
        self.assertIn('branches: [main,', workflow)
        self.assertIn('  pull_request:\n', workflow)
        self.assertNotIn('    paths:', workflow)
        self.assertIn('python scripts/verify_fixes.py', workflow)
        self.assertIn('actions/upload-artifact@v4', workflow)
        self.assertIn('if: always()', workflow)

    def test_render_waits_for_ci_checks_instead_of_every_commit(self):
        root = Path(__file__).resolve().parents[1]
        blueprint = (root / 'render.yaml').read_text()
        self.assertIn('branch: main', blueprint)
        self.assertIn('autoDeployTrigger: checksPass', blueprint)
        self.assertNotIn('autoDeploy: true', blueprint)
