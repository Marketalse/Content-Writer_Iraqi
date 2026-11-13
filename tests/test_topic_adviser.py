"""Senior-model suggestions are budgeted, private, optional and never approvals."""
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
from test_revision import result, assessment, STORY
from pipeline import run_pipeline, Run
from revision import Settings
from llm import WRITER_MODEL
from reviewer import GATES
from quality import Checked
from topic_adviser import parse, render
from diagnostics import diagnostic_report
from briefs import Brief
import bot as app

SUGGESTION={'topic':'شلون تكتب رد خاص لكل زبون؟','reason':'زاوية عملية تحافظ على الفكرة الأصلية وتقلل الكلام العام.','needs_research':False}
ADVICE=json.dumps({'suggestions':[SUGGESTION]},ensure_ascii=False)

def voice_review():
    gates=dict.fromkeys(GATES,'pass');gates['voice_preservation']='fail'
    return result(assessment(8,gates=gates))

class AdviserTests(unittest.IsolatedAsyncioTestCase):
    async def execute(self,tail,**settings):
        model=AsyncMock(side_effect=[result(STORY),voice_review(),*tail])
        with patch('revision.generate',model):
            run=await run_pipeline('story','voice','التواصل الفردي ويا الزبائن','',
                settings=Settings(analyst=False,**settings),suggest_topics=True)
        return run,model

    async def test_voice_rejection_calls_senior_model_without_approving_draft(self):
        run,model=await self.execute([result(ADVICE)])
        self.assertEqual([t['stage'] for t in run.timings],['writer','review','adviser'])
        self.assertEqual(model.call_args_list[-1].kwargs['model'],WRITER_MODEL)
        payload=json.loads(model.call_args_list[-1].args[1])
        self.assertEqual(payload['topic'],'التواصل الفردي ويا الزبائن')
        self.assertEqual(payload['reviews'][-1]['gates']['voice_preservation'],'fail')
        self.assertEqual(run.checked.topic_advice['status'],'ready')
        self.assertEqual(run.checked.failure_code,'critical_gate')
        self.assertNotEqual(run.checked.status,'accepted')
        self.assertFalse(run.checked.manual_review_ready)
        self.assertEqual(len(run.calls),3)
        self.assertAlmostEqual(run.cost_usd,.003)
        self.assertIn('تغيير الزاوية وحده ما يحلها',render(run.checked.topic_advice))

    async def test_budget_stop_explained_without_hiding_original_failure(self):
        run,model=await self.execute([],max_calls=2)
        self.assertEqual(model.await_count,2)
        self.assertEqual(run.checked.failure_code,'critical_gate')
        self.assertEqual(run.checked.topic_advice['reason'],'resource_limit')
        self.assertIn('ما گدر',render(run.checked.topic_advice))

    async def test_invalid_advice_never_displayed_as_real_suggestions(self):
        run,_=await self.execute([result('PRIVATE_MODEL_GARBAGE')])
        self.assertEqual(run.checked.topic_advice['status'],'unavailable')
        self.assertNotIn('PRIVATE_MODEL_GARBAGE',render(run.checked.topic_advice))
        self.assertEqual(run.checked.failure_code,'critical_gate')

    async def test_safety_rejection_never_triggers_circumventing_suggestions(self):
        gates=dict.fromkeys(GATES,'pass');gates['safety']='fail'
        model=AsyncMock(side_effect=[result(STORY),result(assessment(10,gates=gates))])
        with patch('revision.generate',model):
            run=await run_pipeline('story','voice','موضوع','',settings=Settings(analyst=False),suggest_topics=True)
        self.assertEqual(model.await_count,2)
        self.assertFalse(run.checked.topic_advice)

    async def test_unknown_adviser_usage_is_reported_not_shown_as_ready(self):
        run,_=await self.execute([result(ADVICE,usage_known=False)])
        self.assertEqual(run.checked.topic_advice['reason'],'unknown_pricing')
        self.assertEqual(run.checked.topic_advice['status'],'unavailable')

class AdviceValidationTests(unittest.TestCase):
    def test_strict_limits_duplicates_and_research_requirement(self):
        for raw in ('{}','{"suggestions":[]}','{"suggestions":[],"suggestions":[]}',
                    json.dumps({'suggestions':[SUGGESTION]*4}),
                    json.dumps({'suggestions':[dict(SUGGESTION,needs_research=1)]})):
            with self.assertRaises((ValueError,TypeError)):
                parse(raw)
        self.assertTrue(parse(ADVICE,requires_research=True)[0]['needs_research'])

    def test_diagnostic_projection_excludes_suggested_topics_and_reasons(self):
        record={'failure_code':'critical_gate','topic_advice':{'status':'ready','provider':'anthropic',
                 'model':WRITER_MODEL,'suggestions':[dict(SUGGESTION,topic='PRIVATE_TOPIC',reason='PRIVATE_REASON')]}}
        with patch('diagnostics.authorized_post',return_value=record):
            report=diagnostic_report('id',123)
        self.assertNotIn('PRIVATE',json.dumps(report))
        self.assertEqual(report['topic_adviser']['suggestion_count'],1)

class AdviceButtonTests(unittest.IsolatedAsyncioTestCase):
    async def setup_choice(self):
        ctx=NS(chat_data={'format':'story','angle':'story_educational',
                          'content_brief':Brief(story_intent='educational')})
        message=NS(reply_text=AsyncMock())
        await app._show_topic_advice(message,ctx.chat_data,{'status':'ready','suggestions':[SUGGESTION]})
        callback=message.reply_text.call_args.kwargs['reply_markup'].inline_keyboard[0][0].callback_data
        return ctx,callback

    async def test_only_user_selection_restarts_full_generation_and_is_single_use(self):
        ctx,callback=await self.setup_choice()
        query=NS(data=callback,answer=AsyncMock(),message=NS(reply_text=AsyncMock(return_value=NS(edit_text=AsyncMock(),delete=AsyncMock()))))
        upd=NS(message=None,callback_query=query,effective_chat=NS(id=123))
        checked=Checked('STORY: شنو يحتاج زبونك حتى تكتبله رد واضح؟','mock',status='accepted',story_intent='educational')
        model=AsyncMock(return_value=Run(checked))
        with patch.object(app,'_allowed_chat',return_value=True),patch.object(app,'pilot_check',return_value=(True,'')),patch.object(app,'log_post',return_value='id'),patch.object(app,'run_pipeline',model):
            await app.on_advice_chosen(upd,ctx)
            self.assertEqual(model.await_count,1)
            self.assertEqual(model.call_args.args[2],SUGGESTION['topic'])
            self.assertTrue(model.call_args.kwargs['research'])
            self.assertTrue(model.call_args.kwargs['suggest_topics'])
            await app.on_advice_chosen(upd,ctx)
            self.assertEqual(model.await_count,1)
        self.assertNotIn('topic_advice',ctx.chat_data)

    async def test_changed_selection_or_other_nonce_cannot_start_a_run(self):
        ctx,callback=await self.setup_choice()
        ctx.chat_data['format']='tiktok_story'
        query=NS(data=callback,answer=AsyncMock(),message=NS(reply_text=AsyncMock()))
        upd=NS(message=None,callback_query=query,effective_chat=NS(id=123))
        with patch.object(app,'_allowed_chat',return_value=True),patch.object(app,'run_pipeline',AsyncMock()) as model:
            await app.on_advice_chosen(upd,ctx)
        model.assert_not_awaited()
        self.assertIn('انتهى',query.message.reply_text.call_args.args[0])

    async def test_failure_message_is_followed_by_real_adviser_options(self):
        ctx=NS(chat_data={'format':'story','angle':'story_educational',
                          'content_brief':Brief(story_intent='educational')})
        status=NS(edit_text=AsyncMock(),delete=AsyncMock())
        message=NS(text='شلون أتواصل ويا الزبائن؟',reply_text=AsyncMock(return_value=status))
        upd=NS(message=message,effective_chat=NS(id=123))
        gates=dict.fromkeys(GATES,'pass');gates['voice_preservation']='fail'
        model=AsyncMock(side_effect=[result('STORY: شلون أتواصل ويا زبوني؟'),
                                    result(assessment(8,gates=gates)),result(ADVICE)])
        # The real Telegram path enables suggestions. Route/analyst are mocked through
        # a rewrite route so this test focuses on writer/review/adviser delivery.
        from research_fixtures import routed
        model.side_effect=[routed('rewrite'),result('STORY: شلون أتواصل ويا زبوني؟'),
                           result(assessment(8,gates=gates)),result(ADVICE)]
        with patch.object(app,'_allowed_chat',return_value=True),patch.object(app,'pilot_check',return_value=(True,'')),patch.object(app,'log_post',return_value='id'),patch('revision.generate',model):
            await app.on_text(upd,ctx)
        self.assertEqual(model.await_count,4)
        self.assertIn('الحفاظ على النبرة',status.edit_text.call_args.args[0])
        sent=[call.args[0] for call in message.reply_text.call_args_list]
        self.assertTrue(any(SUGGESTION['topic'] in text for text in sent))
        self.assertIn('topic_advice',ctx.chat_data)
