"""User-approved manual-review policy: never bypass critical gates or fresh review."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bot'))
import bot as app
import postlog
from briefs import Brief
from delivery_policy import artifact_fingerprint, manual_review_eligible
from llm import Result
from pipeline import Run, run_pipeline
from quality import Checked, check
from reviewer import DIMENSIONS, GATES
from revision import Settings

REEL=('HOOK: ازدحام الشارع وحده مو دليل إن المحل راح يبيع.\n'
      'SCRIPT: مرات تشوف شارع مليان ناس وتتصور هذا أحسن مكان لمحلك. بس قبل لا تختار، '
      'راقب إذا الناس اللي تمر تحتاج المنتج اللي تبيعه. سهولة الدخول ووضوح واجهة المحل '
      'هم إلها دور. قارن الخيارات حسب زبونك وإمكانياتك، مو حسب الزحمة وحدها.\n'
      'VISUALS: لقطة شارع مزدحم، بعدها واجهة محل ومدخل واضح.\n'
      'CTA: شنو أول شي تراقبه من تختار موقع؟')
SCORES={'hook':8,'storytelling':7,'platform_fit':7,'audience_relevance':8,'iraqi_dialect':6,'cta':6,'originality':6}
PLAN=json.dumps({'audience_need':'choose a shop location','objection':'traffic alone is misleading',
    'purpose':'education','framework':'none','logic_chain':['assumption','contrast','practical implication'],
    'missing_information':'','clarification_question':''})


def review(scores=None,gates=None,issues=None):
    return Result(json.dumps({'scores':scores or SCORES,'gates':gates or dict.fromkeys(GATES,'pass'),
                              'issues':issues or []}),'mock')


def ready(text=REEL):
    checked=Checked(text,'mock',status='needs_review',failure_code='creative_threshold',
                    failures=['creative thresholds not met'],manual_review_ready=True,
                    review_history=[{'score':7.133,'gates':dict.fromkeys(GATES,'pass')}])
    checked.reviewed_artifact_hash=artifact_fingerprint(checked)
    return checked


class ManualEligibilityTests(unittest.TestCase):
    def test_only_fresh_all_pass_creative_failures_are_eligible(self):
        checked=ready()
        self.assertTrue(manual_review_eligible(checked))
        for gate in GATES:
            for state in ('fail','uncertain'):
                candidate=ready();candidate.review_history[-1]['gates'][gate]=state
                self.assertFalse(manual_review_eligible(candidate))
        for code in ('invalid_structure','resource_limit','unknown_pricing','invalid_review_json','review_truncated','provider_error'):
            candidate=ready();candidate.failure_code=code
            self.assertFalse(manual_review_eligible(candidate))

    def test_unreviewed_text_or_production_changes_are_ineligible(self):
        for change in ('text','production'):
            candidate=ready()
            if change=='text':candidate.text+=' تغيير جديد'
            else:candidate.production_plan={'scenes':['unreviewed']}
            self.assertFalse(manual_review_eligible(candidate))
        for change in ('hash','history','gate','failure'):
            candidate=ready()
            if change=='hash':candidate.reviewed_artifact_hash=''
            elif change=='history':candidate.review_history=[]
            elif change=='gate':candidate.review_history[-1]['gates'].pop('safety')
            else:candidate.failures.append('verified fact missing or altered')
            self.assertFalse(manual_review_eligible(candidate))

    def test_manual_delivery_does_not_mark_record_approved_or_published(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(postlog,'LOG',Path(tmp)/'posts.jsonl'):
            pid=postlog.log_post({'quality_status':'needs_review','delivery_status':'manual_review'})
            self.assertFalse(postlog.mark_published(pid))


class ManualEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_reported_reel_scores_after_one_revision_yield_review_draft_without_lowering_threshold(self):
        scores=dict(SCORES,iraqi_dialect=7)
        issue={'section':'SCRIPT','reason':'voice needs improvement','instruction':'use natural Iraqi speech'}
        patch_text=json.dumps({'replacements':{'SCRIPT':'قبل لا تختار الموقع، شوف منو يمر من گدامه. '
            'إذا هذوله مو زباين منتجك، الزحمة وحدها ما تفيدك. قارن سهولة الدخول والإيجار '
            'ووضوح المحل حسب حاجة زبونك، وخلي قرارك مبني على ملاحظة فعلية مو انطباع سريع.'}})
        model=AsyncMock(side_effect=[Result(PLAN,'mock'),Result(REEL,'mock'),review(issues=[issue]),
                                     Result(patch_text,'mock'),review(scores=scores)])
        with patch('revision.generate',model):
            run=await run_pipeline('reel','voice','موقع المحل','myth',brief=Brief(structure_id='reversal'))
        self.assertEqual(model.await_count,5)
        self.assertEqual(run.checked.status,'needs_review')
        self.assertEqual(run.checked.review_history[0]['score'],7.0)
        self.assertEqual(run.checked.review_history[-1]['score'],7.133)
        self.assertTrue(run.checked.manual_review_ready)
        self.assertEqual(Settings().threshold,7.5)
        self.assertEqual(check('reel',run.checked.text),[])

    async def test_explicit_strict_mode_withholds_the_same_draft(self):
        model=AsyncMock(side_effect=[Result(REEL,'mock'),review()])
        with patch('revision.generate',model):
            run=await run_pipeline('reel','voice','الموقع','myth',settings=Settings(analyst=False,show_review_drafts=False))
        self.assertEqual(run.checked.status,'needs_review')
        self.assertFalse(run.checked.manual_review_ready)
        self.assertEqual(model.await_count,2)

    async def test_critical_or_incomplete_review_still_cannot_be_offered_as_draft(self):
        for response in (review(gates=dict.fromkeys(GATES,'uncertain')),Result('{}','mock'),
                         Result('', 'mock',truncated=True)):
            with patch('revision.generate',AsyncMock(side_effect=[Result(REEL,'mock'),response])):
                run=await run_pipeline('reel','voice','الموقع','myth',settings=Settings(analyst=False))
            self.assertFalse(run.checked.manual_review_ready)

    async def test_pending_revised_copy_is_not_shown_when_reassessment_hits_call_limit(self):
        issue={'section':'HOOK','reason':'generic','instruction':'be specific'}
        patch_text=json.dumps({'replacements':{'HOOK':'اختيار موقع المحل يحتاج تعرف منو زبونك قبل لا تحسب الزحمة.'}})
        model=AsyncMock(side_effect=[Result(REEL,'mock'),review(issues=[issue]),Result(patch_text,'mock')])
        with patch('revision.generate',model):
            run=await run_pipeline('reel','voice','الموقع','myth',settings=Settings(analyst=False,max_calls=3))
        self.assertEqual(run.checked.failure_code,'resource_limit')
        self.assertFalse(run.checked.manual_review_ready)
        self.assertEqual(model.await_count,3)


class ManualTelegramTests(unittest.IsolatedAsyncioTestCase):
    def context(self,fmt='reel'):
        return NS(chat_data={'format':fmt,'angle':'myth'})

    def update(self):
        status=NS(delete=AsyncMock(),edit_text=AsyncMock())
        return NS(effective_chat=NS(id=123),message=NS(text='الموقع',reply_text=AsyncMock(return_value=status))),status

    async def deliver(self,checked,fmt='reel'):
        update,status=self.update()
        with patch.object(app,'_allowed_chat',return_value=True),patch.object(app,'pilot_check',return_value=(True,'')), \
             patch.object(app,'run_pipeline',AsyncMock(return_value=Run(checked))), \
             patch.object(app,'log_post',return_value='draft-id') as record:
            await app.on_text(update,self.context(fmt))
        return update,status,record.call_args.args[0]

    async def test_labelled_copy_is_delivered_and_keeps_needs_review_status(self):
        update,status,record=await self.deliver(ready())
        texts=[call.args[0] for call in update.message.reply_text.call_args_list]
        draft=next(text for text in texts if 'HOOK:' in text)
        self.assertTrue(draft.startswith('⚠️ مسودة للمراجعة اليدوية'))
        self.assertIn('غير معتمدة',draft)
        self.assertIn('7.13/10',draft)
        self.assertFalse(any('/published' in text for text in texts))
        self.assertEqual(record['quality_status'],'needs_review')
        self.assertEqual(record['delivery_status'],'manual_review')
        self.assertTrue(record['manual_review_ready'])
        status.delete.assert_awaited_once()

    async def test_delivery_boundary_still_blocks_invalid_native_structure(self):
        update,status,record=await self.deliver(ready('HOOK: البداية\nCONTENT: نص خاطئ\nCTA: تابع'))
        self.assertEqual(record['quality_status'],'blocked')
        self.assertEqual(record['delivery_status'],'withheld')
        self.assertFalse(record['manual_review_ready'])
        status.delete.assert_not_awaited()

    async def test_every_long_copy_chunk_is_labelled_and_within_telegram_limit(self):
        text=('TITLE: تحليل اختيار الموقع\nSUMMARY: ملخص للمقارنة.\n## المقارنة\n'
              +'نقارن الخيارات ونراجع حاجة الزبون والإمكانيات المتوفرة حتى نختار موقع مناسب. '*90
              +'\n## التوصيات\n'+'نراجع كلفة الموقع وسهولة الوصول ووضوح المحل حسب طبيعة المشروع. '*50
              +'\nCONCLUSION: نبدأ بملاحظة الشارع ونقارن الخيارات حسب احتياج المشروع.')
        self.assertEqual(check('linkedin_article',text),[])
        update,status,record=await self.deliver(ready(text),fmt='linkedin_article')
        texts=[call.args[0] for call in update.message.reply_text.call_args_list]
        chunks=texts[1:-1]
        self.assertGreater(len(chunks),1)
        self.assertTrue(all(text.startswith('⚠️ مسودة للمراجعة اليدوية') for text in chunks))
        self.assertTrue(all(len(text.encode('utf-16-le'))//2<=4000 for text in chunks))
        self.assertEqual(record['delivery_status'],'manual_review')
