"""Provider transport regressions; fixtures contain no live model responses or secrets."""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch
from test_revision import result, assessment, draft
from draft_transport import writer_fields, render_writer, normalize_headings, field_details
from diagnostics import failure_summary, safe_structure
from revision import Settings
from pipeline import run_pipeline

FIELDS = writer_fields('tiktok_video')
GOOD = draft('tiktok_video')

class WriterTransportTests(unittest.TestCase):
    def test_structured_fields_render_in_contract_order_for_both_providers(self):
        values = {name: 'نص ثابت ؟' for name in reversed(FIELDS)}
        rendered = render_writer(json.dumps(values), FIELDS)
        self.assertEqual(rendered.splitlines(), [name + ': نص ثابت ؟' for name in FIELDS])

    def test_heading_decoration_and_case_preserve_bodies(self):
        for label in ('hook:', '**hook:**', '**Hook**:', '__HOOK__:', '  Hook :'):
            self.assertEqual(normalize_headings(label + ' body **untouched**', FIELDS),
                             'HOOK: body **untouched**')
        for raw in ('- Hook: body', '```\nhook: body\n```', 'Content: body'):
            self.assertNotEqual(normalize_headings(raw, FIELDS), 'SCRIPT: body')

    def test_malformed_nous_json_not_silently_flattened(self):
        for raw in ('{"HOOK":"one","HOOK":"two"}', '{"HOOK":42}', '```json\n{}\n```'):
            self.assertEqual(render_writer(raw, FIELDS), raw)

    def test_safe_diagnostics_show_exact_missing_and_order_without_text(self):
        details = field_details('CTA: PRIVATE\nHOOK: secret', FIELDS)
        record = {'failure_code': 'invalid_structure', 'structure_details': details}
        message = failure_summary(record)
        self.assertIn('SCRIPT, VISUALS', message)
        self.assertNotIn('PRIVATE', json.dumps(safe_structure(record)) + message)
        self.assertFalse(details['order_valid'])
        self.assertNotIn('secret', message)
        self.assertEqual(safe_structure({'structure_details': {'missing': ['SECRET', 'CTA']}}),
                         {'missing': ['CTA']})

class WriterRepairTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, responses, **settings):
        model = AsyncMock(side_effect=responses)
        with patch('revision.generate', model):
            run = await run_pipeline('tiktok_video', 'voice', 'التسويق', '',
                                     settings=Settings(analyst=False, **settings))
        return run, model

    async def test_nous_missing_fields_repaired_then_independently_reviewed(self):
        for provider in ('nous', 'anthropic'):
            responses = [result('HOOK: بداية\nCTA: شنو رأيك؟'), result(GOOD), result(assessment())]
            responses[0].provider = provider
            run, model = await self.run_case(responses)
            self.assertEqual(run.checked.status, 'accepted', run.checked.failures)
            self.assertEqual([t['stage'] for t in run.timings], ['writer', 'revision', 'review'])
            data = json.loads(model.call_args_list[1].args[1])
            self.assertEqual(data['structure']['missing'], ['SCRIPT', 'VISUALS'])
            self.assertIsNotNone(model.call_args_list[0].kwargs['output_schema'])

    async def test_repair_cannot_bypass_factual_review(self):
        gates = {'factual_integrity': 'uncertain', 'safety': 'pass', 'topic_preservation': 'pass',
                 'voice_preservation': 'pass', 'format_identity': 'pass'}
        run, _ = await self.run_case([result('HOOK: wrong'), result(GOOD), result(assessment(gates=gates))])
        self.assertEqual(run.checked.failure_code, 'critical_gate')

    async def test_one_repair_only_even_with_two_revision_slots(self):
        run, model = await self.run_case([result('HOOK: wrong'), result('HOOK: still wrong')], max_revisions=2)
        self.assertEqual(model.await_count, 2)
        self.assertEqual(run.checked.failure_code, 'invalid_structure')
        self.assertFalse(run.checked.review_history)

    async def test_no_budget_no_repair_no_review(self):
        for settings in ({'max_calls': 1}, {'max_revisions': 0}, {'repair_format': False}):
            run, model = await self.run_case([result('HOOK: wrong')], **settings)
            self.assertEqual(model.await_count, 1)
            self.assertNotEqual(run.checked.status, 'accepted')
