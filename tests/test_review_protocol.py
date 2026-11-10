"""Provider-side review JSON and fast-model effort, with strict local gates.

Transport responses below are synthetic, not evidence of a live provider success.
"""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
import anthropic
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bot'))
import llm
from briefs import Brief
from pipeline import run_pipeline
from prompts import build_system_prompt
from reviewer import DIMENSIONS, GATES, ReviewResponseError, parse_review, review_schema
from revision import Settings, Session, LimitReached

STORY='STORY: قبل لا تختار موقع محلك، شوف إذا الناس اللي تمر تحتاج منتجك وتگدر تدخل بسهولة.'


def assessment(gates=None):
    return json.dumps({'scores':dict.fromkeys(DIMENSIONS,8),
                       'gates':gates or dict.fromkeys(GATES,'pass'),'issues':[]})


def sdk_response(text='', reason='end_turn', thinking=False):
    content=[]
    if thinking:
        content.append(NS(type='thinking',signature='PRIVATE_SIGNATURE',thinking='PRIVATE_THINKING'))
    if text:
        content.append(NS(type='text',text=text))
    return NS(stop_reason=reason,content=content,usage=NS(input_tokens=100,output_tokens=50,
        cache_read_input_tokens=0,cache_creation_input_tokens=0))


class SchemaTests(unittest.TestCase):
    def test_schema_requires_every_dimension_and_gate_without_unsupported_bounds(self):
        schema=review_schema()
        self.assertEqual(set(schema['required']),{'scores','gates','issues'})
        for key,names in (('scores',DIMENSIONS),('gates',GATES)):
            self.assertEqual(set(schema['properties'][key]['required']),set(names))
            self.assertFalse(schema['properties'][key]['additionalProperties'])
        self.assertFalse(schema['additionalProperties'])
        self.assertNotIn('minimum',json.dumps(schema))
        self.assertNotIn('maxLength',json.dumps(schema))
        schema['required'].clear()
        self.assertEqual(len(review_schema()['required']),3)  # no shared mutable request state

    def test_schema_never_replaces_local_gates_bounds_or_section_validation(self):
        for mutate,code in (
            (lambda d:d['gates'].pop('safety'),'invalid_review_gates'),
            (lambda d:d['scores'].update(hook=11),'invalid_review_scores'),
            (lambda d:d['issues'].append({'section':'ALIEN','reason':'x','instruction':'x'}),'invalid_review_section_issue')):
            data=json.loads(assessment());mutate(data)
            with self.assertRaises(ReviewResponseError) as caught:
                parse_review(json.dumps(data),{'STORY'})
            self.assertEqual(caught.exception.code,code)
        for raw in ('not json','```json\n'+assessment()+'\n```'):
            with self.assertRaises(ReviewResponseError) as caught:parse_review(raw,{'STORY'})
            self.assertEqual(caught.exception.code,'invalid_review_json')

    def test_duplicate_keys_cannot_override_a_critical_gate(self):
        raw=assessment().replace('"safety": "pass"','"safety": "fail", "safety": "pass"')
        with self.assertRaises(ReviewResponseError) as caught:parse_review(raw,{'STORY'})
        self.assertEqual(caught.exception.code,'duplicate_review_key')

    def test_structured_review_setting_is_validated(self):
        with self.assertRaises(ValueError):Settings(structured_review='false')
        with patch.dict('os.environ',{'QUALITY_STRUCTURED_REVIEW':'false'}):
            self.assertFalse(Settings.from_env().structured_review)


class SDKProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_review_request_carries_json_schema_and_low_effort_to_sdk(self):
        api=AsyncMock(return_value=sdk_response(assessment(),thinking=True))
        with patch.object(llm._anthropic.messages,'create',api):
            result=await llm.generate('review','data',model='claude-haiku-5-5',
                                      output_schema=review_schema(),effort='low',max_tokens=1800)
        config=api.call_args.kwargs['extra_body']['output_config']
        self.assertEqual(config,{'format':{'type':'json_schema','schema':review_schema()},'effort':'low'})
        self.assertTrue(result.structured_output)
        self.assertEqual(result.effort,'low')
        self.assertEqual(result.thinking_blocks,1)
        self.assertEqual(result.text,assessment())
        self.assertNotIn('PRIVATE',result.text)
        self.assertEqual(api.await_count,1)

    async def test_plain_writer_and_unsupported_override_do_not_get_speculative_options(self):
        for model in ('claude-sonnet-5-5','custom-model'):
            api=AsyncMock(return_value=sdk_response('copy'))
            with patch.object(llm._anthropic.messages,'create',api):
                result=await llm.generate('writer','data',model=model)
            self.assertNotIn('extra_body',api.call_args.kwargs)
            self.assertFalse(result.structured_output)
        api=AsyncMock(return_value=sdk_response(assessment()))
        with patch.object(llm._anthropic.messages,'create',api):
            result=await llm.generate('review','data',model='custom-model',
                                      output_schema=review_schema(),effort='low')
        self.assertNotIn('extra_body',api.call_args.kwargs)
        self.assertFalse(result.structured_output)

    async def test_schema_rejection_is_not_retried_without_schema(self):
        exc=anthropic.BadRequestError('PRIVATE_PROVIDER_ERROR',response=httpx.Response(400,
            request=httpx.Request('POST','https://api.anthropic.com/v1/messages')),body=None)
        api=AsyncMock(side_effect=exc)
        with patch.object(llm._anthropic.messages,'create',api),self.assertRaises(llm.LLMError) as caught:
            await llm.generate('review','data',model='claude-haiku-5-5',output_schema=review_schema(),effort='low')
        self.assertEqual(api.await_count,1)
        self.assertNotIn('PRIVATE',str(caught.exception))

    async def test_thinking_only_truncation_is_explicit_without_leaking_thinking(self):
        with patch.object(llm._anthropic.messages,'create',AsyncMock(return_value=sdk_response(reason='max_tokens',thinking=True))):
            result=await llm.generate('review','data',model='claude-haiku-5-5')
        self.assertTrue(result.truncated)
        self.assertEqual(result.stop_reason,'max_tokens')
        self.assertEqual(result.thinking_blocks,1)
        self.assertEqual(result.text,'')


class PipelineProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_sdk_boundary_replay_uses_three_calls_and_requires_all_gates(self):
        async def provider(**kwargs):
            system=kwargs['system'][0]['text']
            if system.startswith('Analyze the brief'):
                self.assertEqual(kwargs['extra_body']['output_config']['effort'],'low')
                self.assertIn('format',kwargs['extra_body']['output_config'])
                text=json.dumps({'audience_need':'one observation','objection':'','purpose':'conversation',
                    'framework':'none','logic_chain':[],'missing_information':'','clarification_question':''})
            elif system.startswith('You are an independent'):
                config=kwargs.get('extra_body',{}).get('output_config',{})
                if config.get('effort')!='low' or 'format' not in config:
                    return sdk_response(reason='max_tokens',thinking=True)
                text=assessment()
            else:
                self.assertIn('format', kwargs['extra_body']['output_config'])
                text=STORY
            return sdk_response(text)
        api=AsyncMock(side_effect=provider)
        brief=Brief(story_intent='educational',structure_id='insight')
        with patch.object(llm._anthropic.messages,'create',api):
            run=await run_pipeline('story',build_system_prompt('story',brief=brief),'موقع المحل','educational',brief=brief)
        self.assertEqual(run.checked.status,'accepted',run.checked.failures)
        self.assertEqual(api.await_count,3)
        self.assertEqual(len(run.calls),3)
        self.assertEqual(run.checked.text,STORY)
        self.assertEqual(run.timings[-1]['structured_output'],True)
        self.assertEqual(run.timings[-1]['stop_reason'],'end_turn')
        self.assertEqual(run.timings[-1]['effort'],'low')
        self.assertNotIn('PRIVATE',json.dumps(run.timings))

    async def test_truncated_review_still_stops_and_diagnostics_identify_it(self):
        responses=[llm.Result(STORY,'mock'),llm.Result('', 'mock',truncated=True,
                    stop_reason='max_tokens',thinking_blocks=1,structured_output=True,effort='low')]
        model=AsyncMock(side_effect=responses)
        with patch('revision.generate',model):
            run=await run_pipeline('story','voice','موقع المحل','tip',
                brief=Brief(story_intent='educational'),settings=Settings(analyst=False))
        self.assertNotEqual(run.checked.status,'accepted')
        self.assertEqual(run.checked.failure_code,'review_truncated')
        self.assertEqual(run.timings[-1]['thinking_blocks'],1)
        self.assertEqual(model.await_count,2)

    async def test_schema_is_counted_in_input_budget_and_no_extra_repair_call_is_made(self):
        session=Session(Settings(analyst=False,max_input_chars=1000))
        model=AsyncMock()
        with patch('revision.generate',model),self.assertRaises(LimitReached):
            await session.call('review','voice','data',output_schema=review_schema())
        model.assert_not_awaited()

    async def test_explicit_compatibility_mode_keeps_strict_review_validation(self):
        model=AsyncMock(side_effect=[llm.Result(STORY,'mock'),llm.Result('{}','mock')])
        with patch('revision.generate',model):
            run=await run_pipeline('story','voice','موقع المحل','tip',
                brief=Brief(story_intent='educational'),settings=Settings(analyst=False,structured_review=False))
        self.assertEqual(run.checked.failure_code,'invalid_review_keys')
        self.assertNotEqual(run.checked.status,'accepted')
        self.assertNotIn('output_schema',model.call_args_list[1].kwargs)
        self.assertEqual(model.await_count,2)
