"""Story transport recovery preserves content and every acceptance gate."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
import bot as app
from briefs import Brief
from draft_transport import normalize_short_story
from llm import Result
from pipeline import Run, run_pipeline
from quality import Checked, check
from reviewer import DIMENSIONS, GATES
from revision import Settings
from research_fixtures import researched, routed

COPY='الشارع المزدحم مو ضمان للمبيعات. راقب إذا الناس اللي تمر تحتاج منتجك وتگدر تدخل لمحلك بسهولة.'


def review(gates=None, issues=None, score=8):
    return Result(json.dumps({'scores':dict.fromkeys(DIMENSIONS,score),
        'gates':gates or dict.fromkeys(GATES,'pass'),'issues':issues or []}), 'mock')


class TransportTests(unittest.TestCase):
    def test_plain_and_markdown_label_variants_preserve_the_exact_story_body(self):
        for fmt in ('story','instagram_story','tiktok_story'):
            for text in (COPY,'STORY: '+COPY,'story: '+COPY,'**STORY:** '+COPY,'**STORY**: '+COPY):
                with self.subTest(format=fmt, text=text[:12]):
                    normalized=normalize_short_story(text,fmt,story_intent='educational')
                    self.assertEqual(normalized,'STORY: '+COPY)
                    self.assertEqual(check(fmt,normalized,story_intent='educational'),[])
        # The validator itself is still strict; it never accepts missing transport fields.
        self.assertTrue(check('story',COPY,story_intent='educational'))

    def test_unknown_multisection_empty_or_ambiguous_outputs_are_not_repaired(self):
        cases=('', 'STORY:', 'HOOK: بداية\nCONTENT: شرح\nCTA: تابع',
               '**HOOK**: بداية\n**SCRIPT**: شرح', 'STORY: فكرة\nINTERACTION: سؤال؟',
               'STORY: فكرة\nSTORY: ثانية', '```\n'+COPY+'\n```',
               '{"STORY":"فكرة"}', '<b>STORY:</b> فكرة')
        for text in cases:
            with self.subTest(text=text[:30]):
                self.assertEqual(normalize_short_story(text,'story',story_intent='educational'),text)

    def test_overlong_unambiguous_bodies_are_labeled_but_still_fail_length_validation(self):
        for text in ('كلمة ' * 76, 'ك' * 801):
            normalized = normalize_short_story(text, 'story', story_intent='educational')
            self.assertTrue(normalized.startswith('STORY: '))
            self.assertTrue(any('short Story exceeds' in issue
                                for issue in check('story', normalized, story_intent='educational')))

    def test_no_inference_for_other_formats_auto_intent_or_story_sequences(self):
        for fmt,mode,intent in [('reel','moment','educational'),('linkedin','moment','auto'),
                ('story','moment','auto'),('story','teaching','auto')]:
            self.assertEqual(normalize_short_story(COPY,fmt,story_mode=mode,story_intent=intent),COPY)


class TransportEngineTests(unittest.IsolatedAsyncioTestCase):
    async def execute(self, text, assessment=None, **kwargs):
        model=AsyncMock(side_effect=[Result(text,'mock',**kwargs),assessment or review()])
        with patch('revision.generate',model):
            run=await run_pipeline('story','voice','اختيار موقع المحل','one insight',
                                  brief=Brief(story_intent='educational',structure_id='insight'),
                                  settings=Settings(analyst=False))
        return run,model

    async def test_plain_story_reaches_independent_review_without_extra_call(self):
        run,model=await self.execute(COPY)
        self.assertEqual(run.checked.status,'accepted',run.checked.failures)
        self.assertEqual(model.await_count,2)
        self.assertEqual(run.checked.text,'STORY: '+COPY)
        self.assertTrue(run.checked.transport_normalized)
        payload=json.loads(model.call_args_list[1].args[1])
        self.assertEqual(payload['current_draft'],'STORY: '+COPY)
        self.assertEqual(payload['original_draft'],'STORY: '+COPY)
        self.assertEqual(payload['brief']['structure_id'],'insight')

    async def test_already_canonical_story_has_no_transport_change(self):
        run,model=await self.execute('STORY: '+COPY)
        self.assertEqual(run.checked.status,'accepted')
        self.assertFalse(run.checked.transport_normalized)
        self.assertEqual(model.await_count,2)

    async def test_plain_story_cannot_bypass_any_critical_gate(self):
        for gate in GATES:
            for state in ('fail','uncertain'):
                gates=dict.fromkeys(GATES,'pass');gates[gate]=state
                with self.subTest(gate=gate,state=state):
                    run,model=await self.execute(COPY,review(gates=gates,score=10))
                    self.assertEqual(run.checked.status,'blocked')
                    self.assertEqual(model.await_count,2)

    async def test_retired_three_point_lesson_and_foreign_fields_still_stop_before_review(self):
        for text in ('اختار موقعك.\n1. عد الناس.\n2. قارن السعر.\n3. احسب الربح.',
                     'HOOK: بداية\nCONTENT: شرح\nCTA: تابعني'):
            run,model=await self.execute(text)
            self.assertEqual(run.checked.status,'blocked')
            self.assertEqual(model.await_count,1)

    async def test_truncation_and_refusal_are_never_adapted_or_reviewed(self):
        for flag in ('truncated','refused'):
            run,model=await self.execute(COPY,**{flag:True})
            self.assertEqual(run.checked.status,'blocked')
            self.assertFalse(run.checked.transport_normalized)
            self.assertEqual(model.await_count,1)

    async def test_verified_fact_not_rewritten_and_missing_fact_still_blocks(self):
        fact='إيجار المحل 500000 دينار'
        for text,expected_calls in ((fact+' حسب الأرقام اللي قدمتها. '+COPY,2),(COPY,1)):
            model=AsyncMock(side_effect=[Result(text,'mock'),review()])
            with patch('revision.generate',model):
                run=await run_pipeline('story','voice','موقع المحل','insight',
                    verified_facts=((fact,'supplied lease'),),brief=Brief(story_intent='educational'),
                    settings=Settings(analyst=False))
            self.assertEqual(model.await_count,expected_calls)
            self.assertEqual(run.checked.status,'accepted' if expected_calls==2 else 'blocked')
            if expected_calls==2:
                self.assertIn(fact,run.checked.text)


class TransportTelegramTests(unittest.IsolatedAsyncioTestCase):
    def setup_update(self):
        status=SimpleNamespace(delete=AsyncMock(),edit_text=AsyncMock())
        update=SimpleNamespace(effective_chat=SimpleNamespace(id=123),
            message=SimpleNamespace(text='اختيار موقع المحل',reply_text=AsyncMock(return_value=status)))
        context=SimpleNamespace(chat_data={'family':'story','format':'story','angle':'story_educational',
            'structure_id':'insight','menu_stage':'topic',
            'content_brief':Brief(story_intent='educational',structure_id='insight')})
        return update,context,status

    async def test_raw_writer_story_uses_real_pipeline_and_delivers_only_spoken_copy(self):
        update,context,status=self.setup_update()
        analyst=Result(json.dumps({'audience_need':'direct insight','objection':'','purpose':'education',
            'framework':'none','logic_chain':[],'missing_information':'','clarification_question':''}), 'mock')
        model=AsyncMock(side_effect=[routed(),researched(),analyst,Result(COPY,'mock'),review()])
        with patch.object(app,'_allowed_chat',return_value=True),patch.object(app,'pilot_check',return_value=(True,'')), \
             patch.object(app,'log_post',return_value='id') as record,patch('revision.generate',model):
            await app.on_text(update,context)
        self.assertEqual(model.await_count,5)
        self.assertTrue(record.call_args.args[0]['transport_normalized'])
        self.assertIn(COPY,[call.args[0] for call in update.message.reply_text.call_args_list])
        self.assertFalse(any('STORY:' in call.args[0] for call in update.message.reply_text.call_args_list))
        status.delete.assert_awaited_once()

    async def test_blocked_draft_keeps_diagnostics_internal_and_offers_next_action(self):
        update,context,status=self.setup_update()
        failures=['native sections must appear once in the required order','missing or empty STORY:',
                  'unrecognized content before native sections']
        checked=Checked('wrong output','mock',status='blocked',failures=failures)
        with patch.object(app,'_allowed_chat',return_value=True),patch.object(app,'pilot_check',return_value=(True,'')), \
             patch.object(app,'log_post',return_value='review-id') as record, \
             patch.object(app,'run_pipeline',AsyncMock(return_value=Run(checked))):
            await app.on_text(update,context)
        self.assertEqual(record.call_args.args[0]['failures'],failures)
        message=status.edit_text.call_args.args[0]
        self.assertIn('review-id',message)
        self.assertIn('/format',message)
        for failure in failures:
            self.assertNotIn(failure,message)
        status.delete.assert_not_awaited()
