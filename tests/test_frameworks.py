"""Optional framework routing, bounded planning, clarification and quota regressions."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
import bot as telegram_bot
import pilot
import postlog
from frameworks import LIBRARY, Plan, analyst_system, load_library, parse_plan
from llm import Result
from pipeline import Run, run_pipeline
from platform_intelligence import PROFILES
from prompts import build_system_prompt
from quality import Checked
from reviewer import DIMENSIONS, GATES, reviewer_system
from revision import Settings


def planning(**overrides):
    return json.dumps({'audience_need': 'useful product information', 'objection': 'unclear value',
        'purpose': 'product', 'framework': 'FAB', 'logic_chain': ['feature', 'practical value'],
        'missing_information': '', 'clarification_question': '', **overrides}, ensure_ascii=False)


def model_result(text, **kw):
    return Result(text, 'mock', cost_usd=.001, **kw)


def good_review():
    return model_result(json.dumps({'scores': dict.fromkeys(DIMENSIONS, 8),
                                   'gates': dict.fromkeys(GATES, 'pass'), 'issues': []}))


def update(text='المنتج'):
    status = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    upd = SimpleNamespace(effective_chat=SimpleNamespace(id=123),
        message=SimpleNamespace(text=text, reply_text=AsyncMock(return_value=status)))
    return upd, status


class LibraryTests(unittest.TestCase):
    def test_library_covers_all_formats_and_retains_none_option(self):
        library = load_library()
        self.assertEqual(set(library['formats']), set(PROFILES))
        for fmt in PROFILES:
            self.assertEqual(parse_plan(planning(framework='none'), fmt, library).framework, 'none')
        for fmt in ('instagram_story', 'tiktok_story', 'instagram_instants',
                    'instagram_live', 'instagram_broadcast_channel'):
            self.assertEqual(library['formats'][fmt], [])

    def test_framework_requires_both_purpose_and_format_permission(self):
        library = load_library()
        for fmt, purpose, proposed, expected in (
            ('instagram_post', 'product', 'FAB', 'FAB'),
            ('linkedin', 'case_study', 'BAB', 'BAB'),
            ('story', 'product', 'FAB', 'none'),
            ('instagram_post', 'education', 'FAB', 'none'),
            ('tiktok_video', 'product', 'AIDA', 'none'),
            ('linkedin_article', 'education', 'ACCA', 'ACCA'),
        ):
            with self.subTest(fmt=fmt, purpose=purpose, framework=proposed):
                self.assertEqual(parse_plan(planning(purpose=purpose, framework=proposed), fmt,
                                            library).framework, expected)

    def test_unknown_type_does_not_become_educational(self):
        plan = parse_plan(planning(purpose='unknown', framework='QUEST'), 'instagram_post', load_library())
        self.assertEqual(plan.purpose, 'unspecified')
        self.assertEqual(plan.framework, 'none')
        self.assertTrue(plan.fallback)

    def test_unknown_framework_does_not_become_first_choice(self):
        plan = parse_plan(planning(framework='INVENTED'), 'instagram_post', load_library())
        self.assertEqual(plan.framework, 'none')
        self.assertTrue(plan.fallback)

    def test_malformed_plan_is_safe_neutral_data(self):
        malformed = ('not JSON', '[]', '{}', planning(logic_chain='one'), planning(framework=[]),
                     planning(logic_chain=['x'] * 5), planning(audience_need='x' * 501),
                     planning(missing_information='price'), 'x' * 8001)
        for raw in malformed:
            with self.subTest(raw=raw[:40]):
                plan = parse_plan(raw, 'instagram_post', load_library())
                self.assertEqual(plan.framework, 'none')
                self.assertFalse(plan.clarification_question)
                self.assertTrue(plan.fallback)
                self.assertNotIn('not JSON', plan.writer_notes(load_library()))

    def test_moment_formats_do_not_receive_a_long_logic_chain(self):
        for fmt in ('story', 'tiktok_story', 'instagram_instants', 'instagram_broadcast_channel'):
            plan = parse_plan(planning(logic_chain=['a', 'b', 'c', 'd']), fmt, load_library())
            self.assertEqual(len(plan.logic_chain), 2)
            self.assertEqual(plan.framework, 'none')

    def test_config_rejects_dangling_refs_and_missing_profiles(self):
        original = LIBRARY.read_text()
        for text in (original.replace('instagram_story = []', ''),
                     original.replace('problem = ["PAS"]', 'problem = ["MISSING"]'),
                     original.replace('unspecified = []', 'unspecified = ["PAS"]')):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'frameworks.toml'; path.write_text(text)
                with self.assertRaises(ValueError):
                    load_library(path)

    def test_4cs_is_review_policy_not_a_writing_template(self):
        self.assertNotIn('4Cs', load_library()['frameworks'])
        self.assertIn('Apply the 4Cs across the existing dimensions', reviewer_system('story'))
        self.assertIn('never a narrative template', reviewer_system('story'))
        self.assertNotIn('"PAS":', analyst_system('story', load_library()).split('Purpose choices')[0])


class PlanningIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_selected_framework_uses_existing_three_calls(self):
        text = 'HEADLINE: شنو تحتاج من المنتج؟\nCAPTION: اختار الميزة اللي تحل مشكلتك وافهم فائدتها قبل لا تشتري.\nCTA: شنو أكثر ميزة تحتاجها؟'
        model = AsyncMock(side_effect=[model_result(planning()), model_result(text), good_review()])
        with patch('revision.generate', model):
            run = await run_pipeline('instagram_post', build_system_prompt('instagram_post'), 'منتج', 'tip')
        self.assertEqual(run.checked.status, 'accepted')
        self.assertEqual(model.await_count, 3)
        self.assertEqual(run.checked.planning['framework'], 'FAB')
        notes = json.loads(json.loads(model.call_args_list[1].args[1])['analyst_notes'])
        self.assertEqual(notes['optional_framework'], 'FAB')
        self.assertEqual(notes['optional_steps'], load_library()['frameworks']['FAB']['steps'])
        self.assertIn('never replace the selected format contract', model.call_args_list[1].args[0])

    async def test_analyst_disabled_does_not_add_a_selection_call(self):
        text = 'STORY: هسه خل نراجع شغلنا.\nINTERACTION: شنو رأيك؟'
        model = AsyncMock(side_effect=[model_result(text), good_review()])
        with patch('revision.generate', model):
            run = await run_pipeline('story', 'voice', 'topic', 'tip', settings=Settings(analyst=False))
        self.assertEqual(model.await_count, 2)
        self.assertEqual(run.checked.planning, {})
        self.assertEqual(run.checked.status, 'accepted')

    async def test_missing_essential_fact_stops_before_writer_and_reviewer(self):
        question = 'شنو السعر اللي تريد نذكره؟'
        model = AsyncMock(return_value=model_result(planning(
            missing_information='requested offer price', clarification_question=question)))
        with patch('revision.generate', model):
            run = await run_pipeline('instagram_post', 'voice', 'عرض بسعر محدد', 'offer')
        self.assertEqual(model.await_count, 1)
        self.assertEqual(run.checked.status, 'needs_clarification')
        self.assertEqual(run.checked.clarification, question)
        self.assertFalse(run.checked.text)
        self.assertEqual(run.checked.attempts, 0)
        self.assertEqual(run.cost_usd, .001)

    async def test_clarification_is_bounded_to_one_round(self):
        model = AsyncMock(return_value=model_result(planning(
            missing_information='result', clarification_question='شنو النتيجة؟')))
        with patch('revision.generate', model):
            run = await run_pipeline('linkedin', 'voice', 'case', 'tip', clarification_allowed=False)
        self.assertEqual(model.await_count, 1)
        self.assertEqual(run.checked.status, 'blocked')
        self.assertFalse(run.checked.clarification)

    async def test_truncated_or_malformed_planning_does_not_trigger_retry(self):
        text = 'STORY: هسه خل نراجع شغلنا.\nINTERACTION: شنو رأيك؟'
        for response in (model_result(planning(), truncated=True), model_result('bad'),
                         model_result('', refused=True)):
            model = AsyncMock(side_effect=[response, model_result(text), good_review()])
            with patch('revision.generate', model):
                run = await run_pipeline('story', 'voice', 'topic', 'tip')
            self.assertEqual(model.await_count, 3)
            self.assertEqual(run.checked.planning['framework'], 'none')
            self.assertTrue(run.checked.planning['fallback'])


class ClarificationTelegramTests(unittest.IsolatedAsyncioTestCase):
    async def test_question_preserves_brief_and_answer_resumes_without_repeat_question(self):
        ctx = SimpleNamespace(chat_data={'format': 'story', 'angle': 'tip'})
        upd, status = update('original topic')
        question = Checked('', 'mock', status='needs_clarification',
                           clarification='شنو المعلومة؟', attempts=0)
        first = Run(question, [model_result('plan')])
        second = Run(Checked('STORY: هسه خل نراجع شغلنا.\nINTERACTION: شنو رأيك؟',
                             'mock', status='accepted'), [model_result('draft')])
        with patch.object(telegram_bot, '_allowed_chat', return_value=True), \
             patch.object(telegram_bot, 'pilot_check', return_value=(True, '')), \
             patch.object(telegram_bot, 'run_pipeline', AsyncMock(side_effect=[first, second])) as model, \
             patch.object(telegram_bot, 'log_post', return_value='id') as record:
            await telegram_bot.on_text(upd, ctx)
            status.edit_text.assert_awaited_with('شنو المعلومة؟')
            self.assertEqual(record.call_args.kwargs['event'], 'clarification')
            self.assertEqual(ctx.chat_data['pending_clarification']['topic'], 'original topic')
            upd.message.text = 'supplied answer'
            await telegram_bot.on_text(upd, ctx)
        resumed_topic = model.call_args_list[1].args[2]
        self.assertIn('original topic', resumed_topic)
        self.assertIn('supplied answer', resumed_topic)
        self.assertFalse(model.call_args_list[1].kwargs['clarification_allowed'])
        self.assertNotIn('pending_clarification', ctx.chat_data)
        self.assertEqual(record.call_args.kwargs['event'], 'generated')

    async def test_format_change_clears_pending_question(self):
        upd, _ = update()
        ctx = SimpleNamespace(chat_data={'pending_clarification': {'topic': 'old'}})
        with patch.object(telegram_bot, '_allowed_chat', return_value=True):
            await telegram_bot.cmd_format(upd, ctx)
        self.assertNotIn('pending_clarification', ctx.chat_data)


class ClarificationQuotaTests(unittest.TestCase):
    def test_analyst_cost_counts_but_question_is_not_a_post_or_publication(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(postlog, 'LOG', Path(tmp) / 'log.jsonl'):
            pid = postlog.log_post({'chat_id': 123, 'cost_usd': .003}, event='clarification')
            self.assertEqual(pilot.usage(123), (0, .003))
            self.assertFalse(postlog.mark_published(pid))
            postlog.log_post({'chat_id': 123, 'cost_usd': .02})
            self.assertEqual(pilot.usage(123), (1, .023))
