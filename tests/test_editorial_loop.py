"""Editorial recovery must never accept an unreviewed or subthreshold draft."""
import json
import unittest
from unittest.mock import AsyncMock, patch
from test_revision import result, assessment, STORY
from pipeline import run_pipeline
from revision import Settings
from delivery_policy import artifact_fingerprint

class EditorialLoopTests(unittest.IsolatedAsyncioTestCase):
    async def execute(self, responses, **settings):
        model=AsyncMock(side_effect=responses)
        with patch('revision.generate', model):
            run=await run_pipeline('story','voice','التسويق','tip',
                                   settings=Settings(analyst=False, **settings))
        return run, model

    async def test_below_score_without_issues_gets_fresh_drafts_until_pass(self):
        run, model=await self.execute([result(STORY),result(assessment(5)),
            result(STORY),result(assessment(6)),result(STORY),result(assessment(8))])
        self.assertEqual(run.checked.status,'accepted')
        self.assertEqual(len(run.checked.review_history),3)
        self.assertEqual([t['stage'] for t in run.timings],
                         ['writer','review','revision','review','revision','review'])
        final_payload=json.loads(model.call_args_list[-1].args[1])
        self.assertEqual(final_payload['current_draft'],run.checked.text)
        self.assertEqual(run.checked.reviewed_artifact_hash,artifact_fingerprint(run.checked))

    async def test_exhausted_loop_withholds_subthreshold_content(self):
        run, model=await self.execute([result(STORY),result(assessment(5))]*3)
        self.assertEqual(model.await_count,6)
        self.assertNotEqual(run.checked.status,'accepted')
        self.assertFalse(run.checked.manual_review_ready)
        self.assertEqual(run.checked.failure_code,'creative_threshold')

    async def test_score_pass_cannot_bypass_final_safety_review(self):
        gates={'factual_integrity':'pass','safety':'fail','topic_preservation':'pass',
               'voice_preservation':'pass','format_identity':'pass'}
        run, model=await self.execute([result(STORY),result(assessment(5)),
                                      result(STORY),result(assessment(9,gates=gates))])
        self.assertEqual(run.checked.failure_code,'critical_gate')
        self.assertEqual(model.await_count,4)

    async def test_budget_exhaustion_before_final_review_never_delivers(self):
        run, model=await self.execute([result(STORY),result(assessment(5)),result(STORY)],max_calls=3)
        self.assertEqual(run.checked.failure_code,'resource_limit')
        self.assertFalse(run.checked.manual_review_ready)
        self.assertEqual(model.await_count,3)

    async def test_format_failure_without_section_advice_can_regenerate(self):
        gates={'factual_integrity':'pass','safety':'pass','topic_preservation':'pass',
               'voice_preservation':'pass','format_identity':'fail'}
        run, model=await self.execute([result(STORY),result(assessment(8,gates=gates)),
                                      result(STORY),result(assessment(8))])
        self.assertEqual(run.checked.status,'accepted')
        self.assertEqual(model.await_count,4)

    async def test_fresh_draft_cannot_drop_verified_facts(self):
        model=AsyncMock(side_effect=[result(STORY+' 20%'),result(assessment(5)),result(STORY)])
        with patch('revision.generate',model):
            run=await run_pipeline('story','voice','التسويق','tip',
                settings=Settings(analyst=False),verified_facts=(('20%','supplied ledger'),))
        self.assertEqual(run.checked.failure_code,'verified_fact_missing')
        self.assertFalse(run.checked.manual_review_ready)
        self.assertEqual(model.await_count,3)
