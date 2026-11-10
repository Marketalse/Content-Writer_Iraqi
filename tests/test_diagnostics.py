"""Diagnose persisted attempts without model calls, raw responses or cross-chat leaks."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bot'))
import bot as app
import editorial
import postlog
from briefs import Brief
from diagnostics import diagnostic_report, failure_code, failure_message
from llm import Result, LLMError
from pipeline import run_pipeline
from reviewer import DIMENSIONS, GATES
from revision import Settings

STORY='STORY: قبل لا تختار موقع محلك، شوف إذا الناس اللي تمر تحتاج منتجك فعلاً.'


def review(score=8, gates=None, issues=None):
    return Result(json.dumps({'scores':dict.fromkeys(DIMENSIONS,score),
        'gates':gates or dict.fromkeys(GATES,'pass'),'issues':issues or []}), 'mock')


class StoredDiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.log=patch.object(postlog,'LOG',Path(self.tmp.name)/'posts.jsonl')
        self.owner=patch.object(editorial,'is_owner',side_effect=lambda actor:actor==999)
        self.log.start();self.owner.start()
        self.pid=postlog.log_post({'chat_id':123,'format':'story','quality_status':'needs_review',
            'topic':'PRIVATE_TOPIC','failures':['quality assessment incomplete: ValueError'],
            'failure_code':'invalid_response','failure_stage':'review_parse','calls':2,
            'build':{'commit':'a'*40,'source':'safe-hash','SECRET':'PRIVATE_BUILD'},
            'stage_timings':[{'stage':'review','status':'ok','output_chars':25,
                              'truncated':False,'raw_response':'PRIVATE_RESPONSE','error':'PRIVATE_KEY'}],
            'review_history':[{'attempt':1,'score':5,'scores':dict.fromkeys(DIMENSIONS,5),
                              'gates':dict.fromkeys(GATES,'pass'),'issues':[{'reason':'PRIVATE_ISSUE'}]}]})

    def tearDown(self):
        self.owner.stop();self.log.stop();self.tmp.cleanup()

    def test_own_chat_and_owner_can_read_summary_but_other_chats_cannot(self):
        self.assertEqual(diagnostic_report(self.pid,123)['failure_stage'],'review_parse')
        self.assertEqual(diagnostic_report(self.pid,999)['failure_code'],'invalid_response')
        for pid,actor in ((self.pid,124),('missing',123)):
            with self.assertRaises(ValueError):diagnostic_report(pid,actor)

    def test_safe_projection_excludes_raw_payloads_topics_issue_reasons_and_credentials(self):
        report=diagnostic_report(self.pid,123)
        text=json.dumps(report)
        self.assertNotIn('PRIVATE_',text)
        self.assertNotIn('raw_response',text)
        self.assertNotIn('failures',report)
        self.assertEqual(report['stages'][0]['output_chars'],25)
        self.assertEqual(report['reviews'][0]['gates'],dict.fromkeys(GATES,'pass'))

    def test_legacy_records_are_classified_conservatively(self):
        self.assertEqual(failure_code({'failures':['native sections must appear once in the required order']}),'invalid_structure')
        self.assertEqual(failure_code({'failures':['safety: uncertain']}),'critical_gate')
        self.assertEqual(failure_code({'failures':['creative thresholds not met']}),'creative_threshold')
        self.assertEqual(failure_code({'failures':['quality assessment incomplete: LimitReached']}),'unknown')
        self.assertEqual(failure_code({'quality_status':'accepted','failures':[]}),'accepted')
        self.assertEqual(failure_code({'failures':['short Story exceeds the 30-second editorial ceiling']}),'invalid_structure')

    def test_user_message_does_not_suggest_blind_resubmission_for_configuration_failures(self):
        message=failure_message({'failure_code':'unknown_pricing'},self.pid)
        self.assertIn('/diagnose '+self.pid,message)
        self.assertNotIn('أعد إرسال',message)
        self.assertNotIn('unknown_pricing',message)

    def test_block_warning_explains_uncertainty_without_exposing_reviewer_payload(self):
        record = {'failure_code': 'critical_gate', 'review_history': [{
            'gates': {**dict.fromkeys(GATES, 'pass'), 'factual_integrity': 'uncertain'},
            'issues': [{'reason': 'PRIVATE_ISSUE'}]}]}
        message = failure_message(record, self.pid)
        self.assertIn('دقة المعلومات', message)
        self.assertIn('مو إثبات إن المعلومات غلط', message)
        self.assertNotIn('PRIVATE_ISSUE', message)
        self.assertNotIn('سلامة المحتوى', message)
        with patch('diagnostics.authorized_post', return_value=record):
            report = diagnostic_report(self.pid, 123)
        self.assertIn('دقة المعلومات', report['next_action'])
        self.assertNotIn('PRIVATE_ISSUE', json.dumps(report))

    def test_legacy_block_warning_names_failed_gate(self):
        message = failure_message({'failures': ['safety: fail']}, self.pid)
        self.assertIn('سلامة المحتوى: ما اجتازت الفحص', message)


class FailureStageTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self,responses,settings=None):
        model=AsyncMock(side_effect=responses)
        with patch('revision.generate',model):
            run=await run_pipeline('story','voice','موقع المحل','tip',settings=settings or Settings(analyst=False), brief=Brief(story_intent='educational'))
        return run,model

    async def test_writer_validation_review_parse_and_critical_gate_are_distinct(self):
        gates=dict.fromkeys(GATES,'pass');gates['factual_integrity']='uncertain'
        for responses,stage,code in (
            ([LLMError('PRIVATE_SDK_ERROR')],'writer','provider_error'),
            ([Result('HOOK: خاطئ','mock'), Result('HOOK: خاطئ','mock')],'validation','invalid_structure'),
            ([Result(STORY,'mock'),Result('PRIVATE_INVALID_RESPONSE','mock')],'review_parse','invalid_review_json'),
            ([Result(STORY,'mock'),review(gates=gates)],'review','critical_gate'),
            ([Result(STORY,'mock'),Result('', 'mock', truncated=True)],'review','review_truncated'),
            ([Result(STORY,'mock'),review(score=5)],'review','creative_threshold')):
            with self.subTest(code=code):
                run,model=await self.run_case(responses)
                self.assertNotEqual(run.checked.status,'accepted')
                self.assertEqual((run.checked.failure_stage,run.checked.failure_code),(stage,code))
                self.assertNotIn('PRIVATE',json.dumps(run.checked.failures))

    async def test_pricing_stop_and_call_limit_identify_the_attempted_next_stage(self):
        for result,cfg,code in (
            (Result(STORY,'mock',usage_known=False),Settings(analyst=False),'unknown_pricing'),
            (Result(STORY,'mock'),Settings(analyst=False,max_calls=1),'resource_limit')):
            run,model=await self.run_case([result],cfg)
            self.assertEqual(model.await_count,1)
            self.assertEqual(run.checked.failure_stage,'review')
            self.assertEqual(run.checked.failure_code,code)
            self.assertEqual(len(run.timings),1)

    async def test_revision_response_failure_records_revision_phase(self):
        issues=[{'section':'STORY','reason':'generic','instruction':'clarify'}]
        run,model=await self.run_case([Result(STORY,'mock'),review(score=5,issues=issues),
                                      Result('PRIVATE_INVALID_PATCH','mock')])
        self.assertEqual((run.checked.failure_stage,run.checked.failure_code),('revision_parse','invalid_response'))
        self.assertEqual(model.await_count,3)

    async def test_success_clears_failure_fields_and_keeps_only_safe_stage_metadata(self):
        run,model=await self.run_case([Result(STORY,'mock',model='test-model'),review()])
        self.assertEqual(run.checked.status,'accepted')
        self.assertEqual(run.checked.failure_code,'')
        self.assertEqual(run.checked.failure_stage,'')
        self.assertEqual(model.await_count,2)
        self.assertEqual(run.timings[0]['output_chars'],len(STORY))
        self.assertNotIn(STORY,json.dumps(run.timings))
        self.assertEqual(run.timings[0]['model'],'test-model')


class DiagnosisCommandTests(unittest.IsolatedAsyncioTestCase):
    def update(self,text):
        return SimpleNamespace(effective_chat=SimpleNamespace(id=123),
            message=SimpleNamespace(text=text,reply_text=AsyncMock()))

    async def test_command_is_read_only_and_requires_authorized_chat(self):
        update=self.update('/diagnose example-id')
        with patch.object(app,'_allowed_chat',return_value=True), \
             patch.object(app,'diagnostic_report',return_value={'failure_code':'invalid_structure'}) as report, \
             patch.object(app,'run_pipeline',AsyncMock()) as model:
            await app.cmd_diagnose(update,SimpleNamespace(chat_data={}))
        report.assert_called_once_with('example-id',123)
        model.assert_not_awaited()
        self.assertIn('invalid_structure',update.message.reply_text.call_args.args[0])
        update=self.update('/diagnose example-id')
        with patch.object(app,'_allowed_chat',return_value=False),patch.object(app,'diagnostic_report') as report:
            await app.cmd_diagnose(update,SimpleNamespace(chat_data={}))
        report.assert_not_called();update.message.reply_text.assert_not_awaited()

    async def test_bad_or_unavailable_id_does_not_expose_another_record(self):
        for text in ('/diagnose','/diagnose ../secrets','/diagnose unknown-id'):
            update=self.update(text)
            with patch.object(app,'_allowed_chat',return_value=True), \
                 patch.object(app,'diagnostic_report',side_effect=ValueError('PRIVATE_OTHER_CHAT')):
                await app.cmd_diagnose(update,SimpleNamespace(chat_data={}))
            self.assertNotIn('PRIVATE',update.message.reply_text.call_args.args[0])
