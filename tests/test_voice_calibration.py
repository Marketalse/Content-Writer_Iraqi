"""Explicit creator calibration reaches both writer and independent voice gate."""
import unittest
from unittest.mock import AsyncMock, patch
from test_revision import draft, result, assessment
from prompts import FORMATS, build_system_prompt
from reviewer import reviewer_system, GATES
from revision import Settings
from pipeline import run_pipeline

APPROVED='زبونك هو كيان لا تعاملة معاملة جوبة الطليان'

class VoiceCalibrationTests(unittest.TestCase):
    def test_latest_positive_and_negative_examples_reach_every_format(self):
        for fmt in FORMATS:
            for prompt in (build_system_prompt(fmt),reviewer_system(fmt)):
                self.assertIn(APPROVED,prompt)
                self.assertIn('explicitly rejected',prompt)
                self.assertIn('takes precedence',prompt)
                self.assertNotIn('**Credibility:** one line that says the experience',prompt)
                self.assertNotIn('**Opening:** a challenge or a reset',prompt)

class VoiceGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_voice_fail_or_uncertain_never_delivered_as_approved_or_manual(self):
        for state in ('fail','uncertain'):
            gates=dict.fromkeys(GATES,'pass');gates['voice_preservation']=state
            model=AsyncMock(side_effect=[result(draft('instagram_post')),result(assessment(10,gates=gates))])
            with patch('revision.generate',model):
                run=await run_pipeline('instagram_post',build_system_prompt('instagram_post'),'التواصل ويا الزبائن','',
                                       settings=Settings(analyst=False,show_review_drafts=True))
            self.assertEqual(run.checked.failure_code,'critical_gate')
            self.assertFalse(run.checked.manual_review_ready)
            self.assertNotEqual(run.checked.status,'accepted')
            self.assertEqual(model.await_count,2)
