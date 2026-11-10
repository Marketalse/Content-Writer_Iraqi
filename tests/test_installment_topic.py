"""Exact requested topic: repair isolated format failures without bypassing gates."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'bot'))
from scripts.test_topic import evaluate, FIXTURE
from briefs import Brief
from llm import Result
from pipeline import run_pipeline
from quality import check
from reviewer import DIMENSIONS, GATES, can_repair_format, parse_review
from revision import Settings, sections

CASE=json.loads(FIXTURE.read_text())


def assessment(gates=None,score=8,issues=None):
    return Result(json.dumps({'scores':dict.fromkeys(DIMENSIONS,score),
        'gates':gates or dict.fromkeys(GATES,'pass'),'issues':CASE['issues'] if issues is None else issues}), 'mock')


def failed_format(**overrides):
    gates=dict.fromkeys(GATES,'pass');gates['format_identity']='fail';gates.update(overrides)
    return gates


class TopicReplayTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_topic_before_after_protocol_without_semantic_overclaim(self):
        before=await evaluate(repair_format=False)
        after=await evaluate(repair_format=True)
        self.assertEqual(before['topic'],'شلون تبيع بالأقساط بدون ما تضيع فلوسك')
        self.assertEqual((before['status'],before['calls']),('blocked',3))
        self.assertEqual((after['status'],after['calls']),('accepted',5))
        self.assertEqual(after['copy'],CASE['revised_draft'])
        self.assertEqual(after['structural_issues'],[])
        self.assertFalse(before['semantic_quality_verified'])
        self.assertFalse(after['semantic_quality_verified'])
        for field in ('HOOK','CTA'):
            self.assertEqual(sections(after['copy'])[field],sections(before['copy'])[field])
        self.assertEqual(after['review_history'][0]['gates']['format_identity'],'fail')
        self.assertEqual(after['review_history'][1]['gates']['format_identity'],'pass')

    async def test_live_mode_without_secret_never_calls_provider(self):
        model=AsyncMock()
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':''}),patch('revision.generate',model),self.assertRaises(ValueError):
            await evaluate(mode='live')
        model.assert_not_awaited()


class FormatRepairTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self,responses,settings=None,verified_facts=()):
        model=AsyncMock(side_effect=responses)
        with patch('revision.generate',model):
            run=await run_pipeline('reel','voice',CASE['topic'],'educational illustration',
                brief=Brief(structure_id='demo',source_material=CASE['source_material']),
                settings=settings or Settings(analyst=False,max_revisions=1,show_review_drafts=True),verified_facts=verified_facts)
        return run,model

    async def test_format_alone_is_repairable_and_all_original_context_reaches_patch_and_review(self):
        run,model=await self.run_case([Result(CASE['initial_draft'],'mock'),assessment(failed_format()),
                                      Result(json.dumps(CASE['patch']),'mock'),assessment(issues=[])])
        self.assertEqual(run.checked.status,'accepted')
        self.assertEqual(model.await_count,4)
        data=json.loads(model.call_args_list[2].args[1])
        self.assertEqual(data['revision_goal'],'format_repair')
        self.assertEqual(data['topic'],CASE['topic'])
        self.assertEqual(data['brief']['structure_id'],'demo')
        self.assertEqual(json.loads(model.call_args_list[3].args[1])['current_draft'],CASE['revised_draft'])
        self.assertEqual(check('reel',run.checked.text),[])

    async def test_other_failed_or_uncertain_gates_cannot_trigger_format_repair(self):
        for gate in GATES:
            for state in ('fail','uncertain'):
                if gate=='format_identity' and state=='fail':continue
                with self.subTest(gate=gate,state=state):
                    gates=failed_format(**{gate:state})
                    run,model=await self.run_case([Result(CASE['initial_draft'],'mock'),assessment(gates)])
                    self.assertEqual(run.checked.status,'blocked')
                    self.assertFalse(run.checked.manual_review_ready)
                    self.assertEqual(model.await_count,2)

    async def test_no_issues_no_revision_or_disabled_policy_stays_blocked(self):
        cases=[(Settings(analyst=False,max_revisions=0),CASE['issues']),
               (Settings(analyst=False,repair_format=False),CASE['issues'])]
        for cfg,issues in cases:
            run,model=await self.run_case([Result(CASE['initial_draft'],'mock'),assessment(failed_format(),issues=issues)],cfg)
            self.assertEqual(run.checked.status,'blocked')
            self.assertEqual(model.await_count,2)

    async def test_failed_reassessment_still_blocks_even_with_high_score(self):
        run,model=await self.run_case([Result(CASE['initial_draft'],'mock'),assessment(failed_format()),
            Result(json.dumps(CASE['patch']),'mock'),assessment(failed_format(),score=10)])
        self.assertEqual(run.checked.status,'blocked')
        self.assertFalse(run.checked.manual_review_ready)
        self.assertEqual(model.await_count,4)

    async def test_successful_gate_repair_below_creative_threshold_is_only_manual_review(self):
        run,model=await self.run_case([Result(CASE['initial_draft'],'mock'),assessment(failed_format(),score=10),
            Result(json.dumps(CASE['patch']),'mock'),assessment(score=6,issues=[])])
        self.assertEqual(run.checked.status,'needs_review')
        self.assertEqual(run.checked.failure_code,'creative_threshold')
        self.assertTrue(run.checked.manual_review_ready)
        self.assertEqual(model.await_count,4)

    async def test_budget_stop_before_reassessment_cannot_expose_repaired_copy(self):
        run,model=await self.run_case([Result(CASE['initial_draft'],'mock'),assessment(failed_format()),
            Result(json.dumps(CASE['patch']),'mock')],Settings(analyst=False,max_calls=3))
        self.assertEqual(run.checked.failure_code,'resource_limit')
        self.assertFalse(run.checked.manual_review_ready)
        self.assertEqual(model.await_count,3)

    async def test_patch_cannot_drop_a_verified_fact_to_repair_format(self):
        fact='التقسيط مو ضمان للتحصيل'
        initial=CASE['initial_draft'].replace('SCRIPT: ','SCRIPT: '+fact+'. ')
        run,model=await self.run_case([Result(initial,'mock'),assessment(failed_format()),
            Result(json.dumps(CASE['patch']),'mock')],verified_facts=((fact,'supplied policy'),))
        self.assertEqual(run.checked.status,'blocked')
        self.assertEqual(run.checked.failure_code,'verified_fact_missing')
        self.assertFalse(run.checked.manual_review_ready)
        self.assertEqual(model.await_count,3)

    async def test_repaired_gates_can_improve_before_creative_score_in_a_two_revision_budget(self):
        second_patch={'replacements':{'CTA':'شنو أول خانة راح تضيفها لسجل أقساطك؟'}}
        run,model=await self.run_case([Result(CASE['initial_draft'],'mock'),assessment(failed_format(),score=9),
            Result(json.dumps(CASE['patch']),'mock'),assessment(score=6,issues=[{'section':'CTA','reason':'generic','instruction':'make it specific'}]),
            Result(CASE['revised_draft'],'mock'),assessment(score=8,issues=[])],
            Settings(analyst=False,max_revisions=2,max_calls=6,max_total_output_tokens=20000))
        self.assertEqual(run.checked.status,'accepted')
        self.assertEqual(model.await_count,6)
