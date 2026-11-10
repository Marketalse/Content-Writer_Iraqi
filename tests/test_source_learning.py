"""End-to-end source-learning features with deterministic provider/Telegram mocks."""
import json
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
import bot as telegram_bot
import editorial
import postlog
from briefs import Brief, STORY_MODES, parse_brief
from format_contracts import format_contract
from pipeline import Run, run_pipeline
from production import unpack_draft, validate_plan
from prompts import build_system_prompt
from quality import Checked, check
from reviewer import DIMENSIONS, GATES, reviewer_system
from revision import Settings
from llm import Result
from source_knowledge import catalog, scoped_lessons

STORY = 'STORY: هسه خل نشوف شنو يحتاج زبونك.\nINTERACTION: شنو رأيك؟'
SEQUENCE = ('FRAME 1: خل نشوف شنو يصير بين التسويق والمبيعات.\n'
            'FRAME 2: الاستفسار وحده مو بيع؛ لازم نعرف شصار بعده.\n'
            'INTERACTION: شنو يصير للاستفسار عندكم؟')
VIDEO = ('HOOK: شنو يصير للاستفسار؟\nSCRIPT: الاستفسار مو بيع. خل نراجع شلون يوصل لفريق المبيعات '
         'وشنو يحتاج الزبون قبل لا يقرر. تابع السؤال من بدايته لحد ما يجاوبه الشخص المناسب. '
         'هيچ نعرف وين نحتاج نحسن طريقة شغلنا.\nVISUALS: ورقة توضح انتقال الاستفسار بين الفريقين.\nCTA: شنو رأيك؟')


def production(content=VIDEO, duration=30):
    from quality import _field
    spoken = '\n'.join(_field(content, field) for field in ('HOOK', 'SCRIPT', 'CTA'))
    return {'duration_seconds': duration, 'scenes': [{'start_seconds': 0, 'end_seconds': duration,
        'shot': 'تلفون ثابت', 'action': 'أشر على الورقة', 'spoken': spoken,
        'overlay': 'الاستفسار مو بيع', 'fallback': 'صور الورقة بدون وجه'}], 'caption': 'راجع انتقال الاستفسار.',
        'facts_to_confirm': [], 'checks': ['راجع موافقة أي شخص يظهر وحقوق أي موسيقى قبل النشر.']}


def review(score=8, issues=None, gates=None):
    return Result(json.dumps({'scores': dict.fromkeys(DIMENSIONS, score),
        'gates': gates or dict.fromkeys(GATES, 'pass'), 'issues': issues or []}), 'mock')


def update(text='topic'):
    status = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    upd = SimpleNamespace(effective_chat=SimpleNamespace(id=123),
        message=SimpleNamespace(text=text, reply_text=AsyncMock(return_value=status)))
    return upd, status


class BriefTests(unittest.TestCase):
    def test_validated_optional_brief_and_repuposing(self):
        brief = parse_brief(json.dumps({'audience': 'أصحاب المحلات', 'purpose': 'trust',
            'journey_stage': 'consideration', 'source_material': 'supplied core idea',
            'evidence': [{'text': 'actual supplied fact', 'source': 'owner notes'}]}))
        self.assertEqual(brief.evidence[0]['source'], 'owner notes')
        for fmt in ('story', 'reel', 'carousel', 'linkedin'):
            brief.validate_format(fmt)
        self.assertEqual(parse_brief(json.dumps(brief.data())), brief)

    def test_invalid_values_rejected_before_spending(self):
        for raw in ({'audience': 5}, {'purpose': 'guaranteed_growth'}, {'story_mode': 'three_points'},
                    {'production': 'true'}, {'duration_seconds': True}, {'duration_seconds': 500},
                    {'unknown': 1}, {'evidence': [{'text': 'unsupported'}]}, {'source_material': 'x' * 16001}):
            with self.subTest(raw=str(raw)[:50]), self.assertRaises((ValueError, TypeError)):
                parse_brief(json.dumps(raw))
        with self.assertRaises(ValueError):
            Brief(production=True).validate_format('linkedin')
        with self.assertRaises(ValueError):
            Brief(story_mode='teaching').validate_format('reel')

    def test_source_catalog_is_scoped_and_not_official_evidence(self):
        sources = catalog()['sources']
        self.assertEqual(len(sources), 4)
        self.assertTrue(all(not source['checked_at'] for source in sources.values()))
        organic = scoped_lessons('tiktok_video')
        paid = scoped_lessons('tiktok_video', 'paid')
        self.assertNotIn('paid_copy', [r['id'] for r in organic])
        self.assertIn('paid_copy', [r['id'] for r in paid])
        self.assertNotIn('story_continuity', [r['id'] for r in scoped_lessons('linkedin')])
        self.assertTrue(all(r['provenance']['status'] != 'official_documented' for r in paid))


class StoryModeTests(unittest.TestCase):
    def test_all_treatments_have_shared_writer_reviewer_contracts(self):
        for mode in STORY_MODES:
            with self.subTest(mode=mode):
                brief = Brief(story_mode=mode)
                self.assertTrue(build_system_prompt('story', brief=brief).endswith(format_contract('story', mode)))
                self.assertIn(format_contract('story', mode), reviewer_system('story', story_mode=mode))
                text = STORY if mode == 'moment' else SEQUENCE
                self.assertEqual(check('story', text, story_mode=mode), [])
                self.assertEqual(check('tiktok_story', text, story_mode=mode), [])

    def test_variable_frame_count_without_mandatory_three_points(self):
        for count in (2, 3, 5, 8):
            text = '\n'.join([f'FRAME {i}: هسه خل نفهم فكرة مفيدة.' for i in range(1, count + 1)]
                             + ['INTERACTION: شنو رأيك؟'])
            self.assertEqual(check('story', text, story_mode='teaching'), [])

    def test_invalid_frame_order_count_empty_and_legacy_layout(self):
        for text in (SEQUENCE.replace('FRAME 2', 'FRAME 3'),
                     SEQUENCE.replace('FRAME 1: خل نشوف شنو يصير بين التسويق والمبيعات.', 'FRAME 1:'),
                     SEQUENCE + '\nCTA: تابعني', 'prefix\n' + SEQUENCE,
                     STORY, 'HOOK: سؤال\nCONTENT: ثلاث نقاط\nCTA: تابعني'):
            self.assertTrue(check('story', text, story_mode='teaching'))


class ProductionTests(unittest.TestCase):
    def test_valid_production_separate_from_copy(self):
        content, plan = unpack_draft(json.dumps({'content': VIDEO, 'production': production()}), 30)
        self.assertEqual(content, VIDEO)
        self.assertEqual(plan['duration_seconds'], 30)

    def test_rejects_bad_timings_nonfinite_invented_speech_and_dense_overlays(self):
        cases = []
        for key, value in [('start_seconds', 1), ('end_seconds', 29), ('end_seconds', float('nan')),
                           ('spoken', 'invented testimonial'), ('overlay', 'word ' * 13)]:
            plan = production(); plan['scenes'][0][key] = value; cases.append(plan)
        plan = production(); plan['duration_seconds'] = 20; cases.append(plan)
        for plan in cases:
            with self.assertRaises(ValueError):
                validate_plan(plan, VIDEO, 30)


class LearningPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_sequence_brief_and_source_survive_all_pipeline_stages(self):
        brief = Brief(audience='Iraqi founders', takeaway='inquiries differ from sales', story_mode='teaching',
                      source_material='supplied explanation', desired_action='reply with your process')
        model = AsyncMock(side_effect=[Result(SEQUENCE, 'mock'), review()])
        with patch('revision.generate', model):
            run = await run_pipeline('story', build_system_prompt('story'), 'topic', 'tip',
                                     brief=brief, settings=Settings(analyst=False))
        self.assertEqual(run.checked.status, 'accepted')
        self.assertEqual(run.checked.story_mode, 'teaching')
        self.assertEqual(model.await_count, 2)
        for call in model.call_args_list:
            self.assertEqual(json.loads(call.args[1])['brief']['source_material'], 'supplied explanation')

    async def test_production_same_call_count_and_reviewed_with_content(self):
        model = AsyncMock(side_effect=[Result(json.dumps({'content': VIDEO, 'production': production()}), 'mock'), review()])
        with patch('revision.generate', model):
            run = await run_pipeline('reel', build_system_prompt('reel'), 'topic', 'tip',
                brief=Brief(production=True, filming_constraints='phone only, no face'), settings=Settings(analyst=False))
        self.assertEqual(run.checked.status, 'accepted')
        self.assertEqual(model.await_count, 2)
        self.assertTrue(json.loads(model.call_args_list[1].args[1])['production_plan'])
        self.assertNotIn('scenes', run.checked.text)

    async def test_production_is_revalidated_and_reassessed_after_revision(self):
        issues = [{'section': 'HOOK', 'reason': 'vague opening', 'instruction': 'make specific'}]
        model = AsyncMock(side_effect=[Result(json.dumps({'content': VIDEO, 'production': production()}), 'mock'),
            review(5, issues), Result(json.dumps({'replacements': {'HOOK': 'ليش الاستفسار يضيع بين الفريقين؟'},
                                                'production': production(VIDEO.replace('شنو يصير للاستفسار؟', 'ليش الاستفسار يضيع بين الفريقين؟'))}), 'mock'), review()])
        with patch('revision.generate', model):
            run = await run_pipeline('reel', build_system_prompt('reel'), 'topic', 'tip',
                                     brief=Brief(production=True), settings=Settings(analyst=False))
        self.assertEqual(run.checked.status, 'accepted')
        self.assertEqual(model.await_count, 4)
        self.assertEqual(len(run.checked.review_history), 2)

    async def test_production_factual_failure_cannot_be_outscored(self):
        gates = dict.fromkeys(GATES, 'pass'); gates['factual_integrity'] = 'fail'
        model = AsyncMock(side_effect=[Result(json.dumps({'content': VIDEO, 'production': production()}), 'mock'),
                                      review(10, gates=gates)])
        with patch('revision.generate', model):
            run = await run_pipeline('reel', 'voice', 'topic', 'tip', brief=Brief(production=True),
                                     settings=Settings(analyst=False))
        self.assertEqual(run.checked.status, 'blocked')

    async def test_invalid_brief_makes_zero_calls(self):
        with patch('revision.generate', AsyncMock()) as model:
            with self.assertRaises(ValueError):
                await run_pipeline('linkedin', 'voice', 'topic', 'tip', brief=Brief(production=True))
            model.assert_not_awaited()


class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); root = Path(self.temp.name)
        self.patches = [patch.object(editorial, 'EVENTS', root / 'events.jsonl'),
            patch.object(editorial, 'EXAMPLES', root / 'examples.json'),
            patch.object(postlog, 'LOG', root / 'posts.jsonl'), patch.dict(os.environ, {'OWNER_CHAT_ID': '1'})]
        for p in self.patches: p.start()
        self.pid = postlog.log_post({'chat_id': 123, 'format': 'story', 'quality_status': 'accepted',
                                    'objective': 'conversation', 'cost_usd': .02, 'elapsed_ms': 100, 'attempts': 2})
    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()

    def test_human_feedback_never_overrides_engine_or_becomes_example(self):
        editorial.feedback(self.pid, 123, 'reject', 'voice too formal')
        data = editorial.report(123)
        self.assertEqual(data['human_rejected'], 1)
        self.assertEqual(data['engine_accepted'], 1)
        self.assertEqual(editorial.approved_examples('story'), [])
        self.assertEqual(data['revised_drafts'], 1)
        self.assertEqual(data['latency_p50_ms'], 100)
        self.assertEqual(data['estimated_cost_usd'], .02)

    def test_cross_chat_access_rejected_and_owner_explicitly_allowed(self):
        for actor in (124, 999):
            with self.assertRaises(ValueError): editorial.feedback(self.pid, actor, 'accept', 'good')
        editorial.feedback(self.pid, 1, 'accept', 'owner review')
        self.assertEqual(editorial.report(124)['human_reviewed'], 0)
        self.assertEqual(editorial.report(123)['human_accepted'], 1)

    def test_outcome_requires_source_window_and_correct_currency(self):
        data = {'metric': 'replies', 'value': 4, 'denominator': 200, 'window_hours': 24, 'source': 'manual_insights'}
        editorial.record_result(self.pid, 123, data)
        for changed in ({'value': -1}, {'value': float('nan')}, {'value': True},
                        {'window_hours': 0}, {'source': ''}, {'metric': []}, {'currency': 'USD'}):
            with self.assertRaises(ValueError): editorial.record_result(self.pid, 123, {**data, **changed})
        with self.assertRaises(ValueError):
            editorial.record_result(self.pid, 123, {**data, 'metric': 'ad_spend'})
        editorial.record_result(self.pid, 123, {**data, 'metric': 'ad_spend', 'currency': 'IQD'})
        self.assertEqual(editorial.report(123)['manual_result_count'], 2)

    def test_examples_require_owner_and_stay_format_and_mode_scoped(self):
        with self.assertRaises(PermissionError):
            editorial.approve_example('story', 'moment', STORY, 'natural voice', 123)
        identifier = editorial.approve_example('story', 'moment', STORY, 'natural voice', 1)
        self.assertEqual(len(editorial.approved_examples('instagram_story')), 1)
        self.assertEqual(editorial.approved_examples('story', 'teaching'), [])
        self.assertEqual(editorial.approved_examples('linkedin'), [])
        self.assertIn('natural voice', build_system_prompt('story'))
        self.assertNotIn('natural voice', build_system_prompt('linkedin'))
        self.assertTrue(editorial.remove_example(identifier, 1))
        self.assertEqual(editorial.approved_examples('story'), [])


class LearningTelegramTests(unittest.IsolatedAsyncioTestCase):
    async def test_brief_command_sets_and_resets_without_ai(self):
        upd, _ = update('/brief {"story_mode":"teaching","audience":"أصحاب المحلات"}')
        ctx = SimpleNamespace(chat_data={'format': 'story', 'angle': 'tip'})
        with patch.object(telegram_bot, '_allowed_chat', return_value=True):
            await telegram_bot.cmd_brief(upd, ctx)
            self.assertEqual(ctx.chat_data['content_brief'].story_mode, 'teaching')
            upd.message.text = '/brief reset'; await telegram_bot.cmd_brief(upd, ctx)
        self.assertNotIn('content_brief', ctx.chat_data)

    async def test_sequence_delivery_uses_selected_brief_mode(self):
        upd, status = update()
        ctx = SimpleNamespace(chat_data={'format': 'story', 'angle': 'tip', 'content_brief': Brief(story_mode='teaching')})
        run = Run(Checked(SEQUENCE, 'mock', status='accepted', story_mode='teaching'))
        with patch.object(telegram_bot, '_allowed_chat', return_value=True), \
             patch.object(telegram_bot, 'pilot_check', return_value=(True, '')), \
             patch.object(telegram_bot, 'run_pipeline', AsyncMock(return_value=run)) as model, \
             patch.object(telegram_bot, 'log_post', return_value='id') as log:
            await telegram_bot.on_text(upd, ctx)
        self.assertEqual(model.call_args.kwargs['brief'].story_mode, 'teaching')
        self.assertEqual(log.call_args.args[0]['story_mode'], 'teaching')
        status.delete.assert_awaited_once()

    async def test_production_is_delivered_separately(self):
        upd, _ = update()
        ctx = SimpleNamespace(chat_data={'format': 'reel', 'angle': 'tip', 'content_brief': Brief(production=True)})
        run = Run(Checked(VIDEO, 'mock', status='accepted', production_plan=production()))
        with patch.object(telegram_bot, '_allowed_chat', return_value=True), \
             patch.object(telegram_bot, 'pilot_check', return_value=(True, '')), \
             patch.object(telegram_bot, 'run_pipeline', AsyncMock(return_value=run)), \
             patch.object(telegram_bot, 'log_post', return_value='id'):
            await telegram_bot.on_text(upd, ctx)
        sent = [call.args[0] for call in upd.message.reply_text.call_args_list]
        from output_layout import render_creator_copy
        self.assertIn(render_creator_copy(VIDEO, "reel"), sent)
        self.assertTrue(any('خطة التصوير' in part for part in sent if part != VIDEO))

    async def test_new_commands_preserve_access_control(self):
        upd, _ = update()
        ctx = SimpleNamespace(chat_data={})
        with patch.object(telegram_bot, '_allowed_chat', return_value=False), \
             patch.object(telegram_bot, 'is_owner', return_value=False):
            for handler in (telegram_bot.cmd_brief, telegram_bot.cmd_feedback, telegram_bot.cmd_results,
                            telegram_bot.cmd_report, telegram_bot.cmd_example):
                await handler(upd, ctx)
        upd.message.reply_text.assert_not_awaited()

class ExperimentAndReportTests(unittest.TestCase):
    setUp = EditorialTests.setUp
    tearDown = EditorialTests.tearDown
    def test_experiment_requires_matching_cohorts_and_distinct_posts(self):
        variant = postlog.log_post({'chat_id': 123, 'format': 'instagram_story', 'quality_status': 'accepted',
                                   'objective': 'conversation'})
        data = {'baseline_post_id': self.pid, 'variant_post_id': variant, 'variable': 'opening',
                'hypothesis': 'A more specific opening earns relevant replies', 'window_hours': 24}
        editorial.register_experiment(123, data)
        self.assertEqual(len(editorial.report(123)['experiments']), 1)
        self.assertIn('No winner', editorial.report(123)['experiments'][0]['interpretation'])
        for changed in ({'variant_post_id': self.pid}, {'window_hours': float('nan')},
                        {'variable': 'all_changes'}, {'hypothesis': ''}):
            with self.assertRaises(ValueError): editorial.register_experiment(123, {**data, **changed})
        wrong = postlog.log_post({'chat_id': 123, 'format': 'reel', 'objective': 'conversation'})
        with self.assertRaises(ValueError): editorial.register_experiment(123, {**data, 'variant_post_id': wrong})
        paid = postlog.log_post({'chat_id': 123, 'format': 'story', 'objective': 'conversation', 'distribution': 'paid'})
        with self.assertRaises(ValueError): editorial.register_experiment(123, {**data, 'variant_post_id': paid})
        different_structure = postlog.log_post({'chat_id': 123, 'format': 'story',
            'objective': 'conversation', 'structure_id': 'insight'})
        with self.assertRaises(ValueError):
            editorial.register_experiment(123, {**data, 'variant_post_id': different_structure})
        editorial.register_experiment(123, {**data, 'variant_post_id': different_structure, 'variable': 'narrative'})
        self.assertEqual(len(editorial.report(123)['cohorts']), 4)

    def test_latest_human_feedback_and_report_cohorts_are_explicit(self):
        editorial.feedback(self.pid, 123, 'accept', 'first opinion')
        editorial.feedback(self.pid, 123, 'reject', 'after reading aloud')
        data = editorial.report(123)
        self.assertEqual(data['human_reviewed'], 1)
        self.assertEqual(data['human_engine_disagreements']['human_rejected_engine_accepted'], 1)
        self.assertIn('organic', next(iter(data['cohorts'])))
        self.assertIn('or equate subscribers', data['interpretation'])


class FinalBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_production_never_reaches_telegram_even_if_flagged_accepted(self):
        upd, status = update()
        bad = production(); bad['scenes'][0]['spoken'] = 'invented quote'
        ctx = SimpleNamespace(chat_data={'format': 'reel', 'angle': 'tip', 'content_brief': Brief(production=True)})
        run = Run(Checked(VIDEO, 'mock', status='accepted', production_plan=bad))
        with patch.object(telegram_bot, '_allowed_chat', return_value=True), \
             patch.object(telegram_bot, 'pilot_check', return_value=(True, '')), \
             patch.object(telegram_bot, 'run_pipeline', AsyncMock(return_value=run)), \
             patch.object(telegram_bot, 'log_post', return_value='id') as log:
            await telegram_bot.on_text(upd, ctx)
        self.assertEqual(log.call_args.args[0]['quality_status'], 'blocked')
        status.delete.assert_not_awaited()
        self.assertNotIn(VIDEO, [c.args[0] for c in upd.message.reply_text.call_args_list])

    async def test_wrong_story_mode_never_reaches_delivery(self):
        upd, status = update()
        ctx = SimpleNamespace(chat_data={'format': 'story', 'angle': 'tip', 'content_brief': Brief(story_mode='teaching')})
        run = Run(Checked(STORY, 'mock', status='accepted'))
        with patch.object(telegram_bot, '_allowed_chat', return_value=True), \
             patch.object(telegram_bot, 'pilot_check', return_value=(True, '')), \
             patch.object(telegram_bot, 'run_pipeline', AsyncMock(return_value=run)), \
             patch.object(telegram_bot, 'log_post', return_value='id'):
            await telegram_bot.on_text(upd, ctx)
        status.delete.assert_not_awaited()

    async def test_complete_manual_feedback_outcome_report_and_owner_example_commands(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(editorial, 'EVENTS', Path(tmp) / 'events.jsonl'), \
             patch.object(editorial, 'EXAMPLES', Path(tmp) / 'examples.json'), \
             patch.object(postlog, 'LOG', Path(tmp) / 'posts.jsonl'), \
             patch.dict(os.environ, {'OWNER_CHAT_ID': '123'}), \
             patch.object(telegram_bot, '_allowed_chat', return_value=True):
            pid = postlog.log_post({'chat_id': 123, 'format': 'story', 'quality_status': 'accepted'})
            upd, _ = update('/feedback ' + pid + ' accept natural Iraqi voice')
            ctx = SimpleNamespace(chat_data={'format': 'story'})
            await telegram_bot.cmd_feedback(upd, ctx)
            upd.message.text = '/results ' + pid + ' {"metric":"replies","value":4,"window_hours":24,"source":"manual_insights"}'
            await telegram_bot.cmd_results(upd, ctx)
            self.assertEqual(editorial.report(123)['manual_result_count'], 1)
            upd.message.text = '/example story moment | natural Iraqi voice\n' + STORY
            await telegram_bot.cmd_example(upd, ctx)
            self.assertEqual(len(editorial.approved_examples('story')), 1)
            await telegram_bot.cmd_report(upd, ctx)
            sent = '\n'.join(c.args[0] for c in upd.message.reply_text.call_args_list)
            self.assertIn('human_accepted', sent)
        # Restore cached prompts after temporary approved examples are removed.
        for fmt in telegram_bot.FORMATS:
            telegram_bot.SYSTEM_PROMPTS[fmt] = build_system_prompt(fmt)


class CrossFormatHarnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_39_shared_topic_contract_cases_and_no_false_semantic_claim(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
        from evaluate_formats import evaluate
        data = await evaluate()
        self.assertEqual(data['cases_run'], 39)
        self.assertEqual(data['contract_passes'], 39)
        self.assertFalse(data['semantic_quality_verified'])
        self.assertTrue(all(r['logical_calls'] == 3 for r in data['results']))
        self.assertEqual(len({r['format'] for r in data['results']}), 13)
        self.assertEqual(len({r['topic'] for r in data['results']}), 3)

    async def test_live_harness_does_not_fake_success_without_credentials(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
        from evaluate_formats import evaluate
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': ''}), self.assertRaises(ValueError):
            await evaluate('live', 1, .25)

class ReadableBriefTests(unittest.TestCase):
    def test_arabic_field_input_preserves_source_and_provenance(self):
        from briefs import parse_brief_input, render_brief
        brief = parse_brief_input('الجمهور: أصحاب المحلات\nالهدف: ثقة\nالمرحلة: تقييم\nالستوري: شرح\nالدليل: حقيقة مقدمة | سجل المستخدم\nالمصدر: فكرة أساسية\nتفصيل إضافي')
        self.assertEqual(brief.story_mode, 'teaching')
        self.assertEqual(brief.purpose, 'trust')
        self.assertEqual(brief.journey_stage, 'consideration')
        self.assertIn('تفصيل إضافي', brief.source_material)
        self.assertEqual(len(brief.evidence), 1)
        self.assertIn('الستوري: شرح', render_brief(brief))
        self.assertNotIn('source_material', render_brief(brief))

    def test_production_input_and_bad_fields(self):
        from briefs import parse_brief_input
        brief = parse_brief_input('خطة تصوير: نعم\nالمدة: ٣٠\nالإمكانيات: تلفون فقط')
        self.assertTrue(brief.production)
        self.assertEqual(brief.duration_seconds, 30)
        for raw in ('unrecognized', 'الهدف: تعليم\nالهدف: ثقة', 'خطة تصوير: maybe', 'الدليل: missing source'):
            with self.assertRaises(ValueError): parse_brief_input(raw)
