"""Story-first intent UX, short copy, independent scoring and retired-template guards."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
import bot as app
import editorial
from briefs import Brief
from prompts import ANGLE_BUTTONS, angle_options, build_system_prompt
from quality import Checked, check, render_story_copy
from reviewer import DIMENSIONS, GATES, parse_review, reviewer_system
from revision import Settings
from pipeline import Run, run_pipeline
from llm import Result
from research_fixtures import researched, routed
from story_styles import STORY_STYLES, STORY_ANGLE_KEYS

COPIES = {
    'entertain': 'المحل فاتح، بس صاحب المحل بعده ينتظر القهوة حتى يفتح وياه.',
    'educational': 'قبل لا تختار موقع محلك، راقب إذا الناس اللي تمر تحتاج فعلاً المنتج اللي تبيعه.',
    'everyday': 'مرات تشوف شارع مزدحم وتتصور المحل هناك مضمون. بس مرور الناس وحده ما يكفي حتى تعرف إذا الموقع يناسب شغلك.',
    'ask_audience': 'من تختار موقع لمشروعك، شنو أول شي تراقبه؟',
    'answer_question': 'الموقع المزدحم مو ضمان للمبيعات. المهم إذا الزبون اللي يحتاج منتجك يگدر يوصل للمحل ويدخل بسهولة.',
}


def assessment(cta=8, issues=None, score=8):
    scores = dict.fromkeys(DIMENSIONS, score); scores['cta'] = cta
    return Result(json.dumps({'scores': scores, 'gates': dict.fromkeys(GATES, 'pass'), 'issues': issues or []}), 'mock')


def update(data='fmt:story', text='اختيار موقع المحل'):
    status = SimpleNamespace(delete=AsyncMock(), edit_text=AsyncMock())
    return SimpleNamespace(effective_chat=SimpleNamespace(id=123),
        callback_query=SimpleNamespace(data=data, answer=AsyncMock(), edit_message_text=AsyncMock()),
        message=SimpleNamespace(text=text, reply_text=AsyncMock(return_value=status))), status


class StoryPolicyTests(unittest.TestCase):
    def test_five_story_specific_choices_and_unchanged_other_format_menu(self):
        self.assertEqual(set(angle_options('story')), set(STORY_ANGLE_KEYS))
        self.assertEqual(angle_options('tiktok_story'), angle_options('story'))
        self.assertEqual(angle_options('reel'), ANGLE_BUTTONS)
        self.assertEqual(angle_options('linkedin'), ANGLE_BUTTONS)
        self.assertEqual(len(STORY_STYLES), 5)

    def test_distinct_intent_in_writer_and_reviewer_no_forced_question_or_cta(self):
        for intent in STORY_STYLES:
            brief = Brief(story_intent=intent)
            writer = build_system_prompt('story', brief=brief)
            reviewer = reviewer_system('story', story_intent=intent)
            self.assertIn(STORY_STYLES[intent]['instruction'], writer)
            self.assertIn(STORY_STYLES[intent]['instruction'], reviewer)
            self.assertIn('STORY: the complete short spoken script only', writer)
            self.assertNotIn('Preferred CTA:', writer)
            self.assertEqual(check('story', 'STORY: ' + COPIES[intent], story_intent=intent), [])

    def test_short_limits_and_retired_stack_are_deterministic_gates(self):
        for text in ('STORY: ' + 'كلمة ' * 76, 'STORY: ' + 'ك' * 801,
            'STORY: معلومة\n**1.** خطوة\n**2.** خطوة\n**3.** خطوة',
            'STORY: معلومة\n📊 أول شي: خطوة\n🔥 ثاني شي: خطوة\n💡 بس انتبه: خطوة',
            'HOOK: البداية\nCONTENT: الدرس\nCTA: تابعني'):
            self.assertTrue(check('story', text, story_intent='educational'))
        self.assertTrue(check('story', 'STORY: هذا شرح بدون سؤال.', story_intent='ask_audience'))
        self.assertEqual(check('story', 'STORY: شنو رأيكم؟', story_intent='ask_audience'), [])

    def test_optional_cta_is_not_a_score_penalty_for_direct_information(self):
        raw = assessment(cta=0).text
        review = parse_review(raw, {'STORY'})
        for intent in ('educational', 'entertain', 'everyday', 'answer_question'):
            self.assertTrue(review.acceptable('story', 7.5, 6, intent))
        self.assertFalse(review.acceptable('story', 7.5, 6, 'ask_audience'))
        self.assertFalse(review.acceptable('reel', 7.5, 6))

    def test_delivery_strips_transport_labels_without_inserting_a_template(self):
        self.assertEqual(render_story_copy('STORY: ' + COPIES['educational']), COPIES['educational'])
        self.assertEqual(render_story_copy('STORY: هسه نشوف.\nINTERACTION: شنو رأيك؟'), 'هسه نشوف.\n\nشنو رأيك؟')

    def test_intent_cannot_leak_to_non_story_or_advanced_sequence(self):
        with self.assertRaises(ValueError): Brief(story_intent='educational').validate_format('reel')
        with self.assertRaises(ValueError): Brief(story_intent='educational', story_mode='teaching')
        with self.assertRaises(ValueError): Brief(story_intent='unknown')

    def test_approved_examples_stay_intent_scoped(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(editorial, 'EXAMPLES', Path(tmp) / 'examples.json'), \
             patch.dict(os.environ, {'OWNER_CHAT_ID': '1'}):
            editorial.approve_example('story', 'moment', 'STORY: ' + COPIES['educational'], 'direct useful information', 1,
                                     story_intent='educational')
            self.assertEqual(len(editorial.approved_examples('story', story_intent='educational')), 1)
            self.assertEqual(editorial.approved_examples('story', story_intent='entertain'), [])
            self.assertEqual(editorial.approved_examples('story'), [])


class StoryIntentPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_five_intents_keep_two_calls_without_analyst_and_no_forced_closing(self):
        for intent in STORY_STYLES:
            model = AsyncMock(side_effect=[Result('STORY: ' + COPIES[intent], 'mock'), assessment()])
            with patch('revision.generate', model):
                run = await run_pipeline('story', build_system_prompt('story', brief=Brief(story_intent=intent)),
                    'اختيار موقع المحل', 'selected intent', brief=Brief(story_intent=intent), settings=Settings(analyst=False))
            self.assertEqual(run.checked.status, 'accepted')
            self.assertEqual(run.checked.story_intent, intent)
            self.assertEqual(model.await_count, 2)
            self.assertEqual(json.loads(model.call_args_list[1].args[1])['brief']['story_intent'], intent)

    async def test_plain_three_point_output_stops_before_reviewer(self):
        text = 'STORY: اختار الموقع.\n1. عد المارة.\n2. قارن الإيجار.\n3. احسب المبيعات.'
        model = AsyncMock(return_value=Result(text, 'mock'))
        with patch('revision.generate', model):
            run = await run_pipeline('story', 'voice', 'الموقع', 'education',
                brief=Brief(story_intent='educational'), settings=Settings(analyst=False))
        self.assertEqual(run.checked.status, 'blocked')
        self.assertEqual(model.await_count, 1)

    async def test_revision_preserves_intent_and_is_reassessed(self):
        issues = [{'section':'STORY','reason':'too generic','instruction':'make the one insight specific'}]
        model = AsyncMock(side_effect=[Result('STORY: خل نفهم اختيار الموقع.', 'mock'), assessment(5, issues, 5),
            Result(json.dumps({'replacements': {'STORY': COPIES['educational']}}), 'mock'), assessment()])
        with patch('revision.generate', model):
            run = await run_pipeline('story', 'voice', 'الموقع', 'education',
                brief=Brief(story_intent='educational'), settings=Settings(analyst=False))
        self.assertEqual(run.checked.status, 'accepted')
        self.assertEqual(model.await_count, 4)
        self.assertEqual(len(run.checked.review_history), 2)
        self.assertIn('Deliver one useful fact', model.call_args_list[2].args[0])


class StoryMenuTests(unittest.IsolatedAsyncioTestCase):
    async def test_story_button_opens_intent_menu_before_topic(self):
        upd, _ = update()
        ctx = SimpleNamespace(chat_data={'family':'story','menu_stage':'platform'})
        with patch.object(app, '_allowed_chat', return_value=True):
            await app.on_format_chosen(upd, ctx)
        call = upd.callback_query.edit_message_text.call_args
        self.assertIn('٣٠ ثانية', call.args[0])
        callbacks = [button.callback_data for row in call.kwargs['reply_markup'].inline_keyboard for button in row]
        self.assertEqual(set(callbacks), {'pick:story:' + key for key in STORY_ANGLE_KEYS} | {'back:angle'})
        self.assertNotIn('angle', ctx.chat_data)

    async def test_style_selection_sets_purpose_and_asks_for_topic_or_question(self):
        for key, intent in STORY_ANGLE_KEYS.items():
            upd, _ = update('pick:story:' + key)
            ctx = SimpleNamespace(chat_data={'family':'story','menu_stage':'angle','format': 'story', 'pending_clarification': {'topic':'old'}})
            with patch.object(app, '_allowed_chat', return_value=True):
                await app.on_angle_chosen(upd, ctx)
            brief = ctx.chat_data['content_brief']
            self.assertEqual(brief.story_intent, intent)
            self.assertEqual(brief.duration_seconds, 30)
            self.assertEqual(brief.purpose, STORY_STYLES[intent]['purpose'])
            self.assertNotIn('pending_clarification', ctx.chat_data)
            self.assertEqual(ctx.chat_data['menu_stage'],'structure')
            upd.callback_query.data='str:story:insight'
            with patch.object(app, '_allowed_chat', return_value=True):
                await app.on_structure_chosen(upd,ctx)
            self.assertIn(STORY_STYLES[intent]['topic_prompt'], upd.callback_query.edit_message_text.call_args.args[0])

    async def test_stale_story_button_is_ignored_for_reel(self):
        upd, _ = update('ang:story_entertain')
        ctx = SimpleNamespace(chat_data={'format': 'reel'})
        with patch.object(app, '_allowed_chat', return_value=True):
            await app.on_angle_chosen(upd, ctx)
        self.assertNotIn('angle', ctx.chat_data)
        upd.callback_query.edit_message_text.assert_not_awaited()

    async def test_legacy_angle_callback_migrates_to_platform_selection(self):
        upd, _ = update('ang:tip')
        ctx = SimpleNamespace(chat_data={'format': 'story'})
        with patch.object(app, '_allowed_chat', return_value=True):
            await app.on_angle_chosen(upd, ctx)
        self.assertNotIn('angle',ctx.chat_data)
        self.assertEqual(ctx.chat_data['family'],'story')
        self.assertEqual(ctx.chat_data['menu_stage'],'platform')

    async def test_selected_style_reaches_pipeline_and_plain_copy_delivery(self):
        upd, status = update()
        ctx = SimpleNamespace(chat_data={'format':'story','angle':'story_educational',
                                        'content_brief':Brief(story_intent='educational')})
        run = Run(Checked('STORY: ' + COPIES['educational'], 'mock', status='accepted', story_intent='educational'))
        with patch.object(app, '_allowed_chat', return_value=True), patch.object(app, 'pilot_check', return_value=(True,'')), \
             patch.object(app, 'run_pipeline', AsyncMock(return_value=run)) as pipeline, \
             patch.object(app, 'log_post', return_value='id') as log:
            await app.on_text(upd, ctx)
        self.assertEqual(pipeline.call_args.kwargs['brief'].story_intent, 'educational')
        self.assertEqual(log.call_args.args[0]['story_intent'], 'educational')
        texts = [c.args[0] for c in upd.message.reply_text.call_args_list]
        self.assertIn(COPIES['educational'], texts)
        self.assertFalse(any('STORY:' in text or 'Hook' in text for text in texts))
        status.delete.assert_awaited_once()

class FullStoryFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_format_style_topic_real_pipeline_and_plain_delivery_three_calls(self):
        upd, status = update()
        ctx = SimpleNamespace(chat_data={})
        analyst = Result(json.dumps({'audience_need':'one useful insight', 'objection':'', 'purpose':'education',
            'framework':'none', 'logic_chain':['explain one idea'], 'missing_information':'', 'clarification_question':''}), 'mock')
        model = AsyncMock(side_effect=[routed(), researched(), analyst, Result('STORY: ' + COPIES['educational'], 'mock'), assessment(cta=0)])
        with patch.object(app, '_allowed_chat', return_value=True), patch.object(app, 'pilot_check', return_value=(True,'')), \
             patch.object(app, 'log_post', return_value='id'), patch('revision.generate', model):
            await app.on_format_chosen(upd, ctx)  # old format button migrates to platform
            await app.on_format_chosen(upd, ctx)  # explicit Instagram platform choice
            upd.callback_query.data = 'pick:story:story_educational'
            await app.on_angle_chosen(upd, ctx)
            upd.callback_query.data='str:story:insight'
            await app.on_structure_chosen(upd,ctx)
            await app.on_text(upd, ctx)
        self.assertEqual(model.await_count, 5)
        self.assertIn(COPIES['educational'], [c.args[0] for c in upd.message.reply_text.call_args_list])
        self.assertIn('Deliver one useful fact', model.call_args_list[2].args[0])
        self.assertIn('Deliver one useful fact', model.call_args_list[3].args[0])
        status.delete.assert_awaited_once()


class BriefStyleOverrideTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_brief_style_updates_the_selected_button_intent(self):
        upd, _ = update(text='/brief\nستايل الستوري: جواب سؤال')
        ctx = SimpleNamespace(chat_data={'format': 'story', 'angle': 'story_entertain'})
        with patch.object(app, '_allowed_chat', return_value=True):
            await app.cmd_brief(upd, ctx)
        self.assertEqual(ctx.chat_data['angle'], 'story_answer_question')
        self.assertEqual(ctx.chat_data['content_brief'].story_intent, 'answer_question')
