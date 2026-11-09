"""Constrain planner responses within the existing 600-token optional stage."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bot'))
import llm
from briefs import Brief
from frameworks import analyst_schema, load_library, parse_plan
from pipeline import run_pipeline
from reviewer import DIMENSIONS, GATES
from revision import Settings
from test_review_protocol import sdk_response

PLAN={'audience_need':'choose a shop location','objection':'traffic alone is misleading',
      'purpose':'education','framework':'none','logic_chain':['assumption','counterexample','meaning'],
      'missing_information':'','clarification_question':''}
STORY='STORY: راقب إذا الناس اللي تمر تحتاج منتجك قبل لا تختار الموقع.'
REVIEW=json.dumps({'scores':dict.fromkeys(DIMENSIONS,8),'gates':dict.fromkeys(GATES,'pass'),'issues':[]})


class AnalystSchemaTests(unittest.TestCase):
    def test_exact_fields_and_stable_schema_keep_permissions_local(self):
        library=load_library()
        schema=analyst_schema(library)
        self.assertEqual(set(schema['required']),set(PLAN))
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(set(schema['properties']['purpose']['enum']),set(library['purposes']))
        candidate={**PLAN,'framework':'PAS','purpose':'problem'}
        self.assertEqual(parse_plan(json.dumps(candidate),'reel',library).framework,'PAS')
        self.assertEqual(parse_plan(json.dumps(candidate),'story',library).framework,'none')
        schema['required'].clear()
        self.assertEqual(len(analyst_schema(library)['required']),7)

    def test_configuration_flags_require_boolean_values(self):
        for key in ('structured_analyst','show_review_drafts'):
            with self.assertRaises(ValueError):Settings(**{key:'true'})
        with patch.dict('os.environ',{'QUALITY_STRUCTURED_ANALYST':'false','QUALITY_SHOW_REVIEW_DRAFTS':'false'}):
            cfg=Settings.from_env()
        self.assertFalse(cfg.structured_analyst)
        self.assertFalse(cfg.show_review_drafts)


class AnalystPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_sdk_boundary_returns_constrained_plan_in_same_three_call_pipeline(self):
        async def provider(**kwargs):
            system=kwargs['system'][0]['text']
            if system.startswith('Analyze the brief'):
                config=kwargs['extra_body']['output_config']
                self.assertEqual(kwargs['max_tokens'],600)
                self.assertEqual(config['effort'],'low')
                self.assertEqual(config['format']['schema'],analyst_schema(load_library()))
                return sdk_response(json.dumps(PLAN))
            if system.startswith('You are an independent'):
                return sdk_response(REVIEW)
            return sdk_response(STORY)
        api=AsyncMock(side_effect=provider)
        with patch.object(llm._anthropic.messages,'create',api):
            run=await run_pipeline('story','voice','الموقع','tip',brief=Brief(story_intent='educational'))
        self.assertEqual(api.await_count,3)
        self.assertEqual(run.checked.status,'accepted')
        self.assertFalse(run.checked.planning['fallback'])
        self.assertEqual(run.timings[0]['structured_output'],True)
        self.assertEqual(run.timings[0]['output_token_limit'],600)

    async def test_truncated_analyst_is_neutral_with_explicit_reason_and_no_hidden_retry(self):
        model=AsyncMock(side_effect=[llm.Result('', 'mock',truncated=True,output_tokens=600,
            stop_reason='max_tokens',thinking_blocks=1),llm.Result(STORY,'mock'),llm.Result(REVIEW,'mock')])
        with patch('revision.generate',model):
            run=await run_pipeline('story','voice','الموقع','tip',brief=Brief(story_intent='educational'))
        self.assertEqual(model.await_count,3)
        self.assertTrue(run.checked.planning['fallback'])
        self.assertEqual(run.checked.planning['fallback_reason'],'truncated')
        self.assertEqual(run.output_tokens,600)
        self.assertEqual(run.checked.status,'accepted')

    async def test_essential_clarification_remains_one_call_and_draft_is_not_shown(self):
        plan={**PLAN,'missing_information':'سعر المنتج','clarification_question':'شكد سعر المنتج؟'}
        model=AsyncMock(return_value=llm.Result(json.dumps(plan),'mock'))
        with patch('revision.generate',model):
            run=await run_pipeline('story','voice','عرض على المنتج','offer')
        self.assertEqual(model.await_count,1)
        self.assertEqual(run.checked.status,'needs_clarification')
        self.assertFalse(run.checked.manual_review_ready)
        self.assertEqual(run.checked.clarification,'شكد سعر المنتج؟')

    async def test_explicit_compatibility_mode_sends_no_analyst_schema(self):
        model=AsyncMock(side_effect=[llm.Result(json.dumps(PLAN),'mock'),llm.Result(STORY,'mock'),llm.Result(REVIEW,'mock')])
        with patch('revision.generate',model):
            run=await run_pipeline('story','voice','الموقع','tip',brief=Brief(story_intent='educational'),
                settings=Settings(structured_analyst=False))
        self.assertEqual(run.checked.status,'accepted')
        self.assertNotIn('output_schema',model.call_args_list[0].kwargs)
        self.assertIn('output_schema',model.call_args_list[2].kwargs)
