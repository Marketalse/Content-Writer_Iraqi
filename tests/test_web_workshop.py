"""Real ASGI routes + durable jobs; model boundary mocked, no paid/network calls."""
import asyncio
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import AsyncMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bot'))
from fastapi.testclient import TestClient
from webapp import create_app
from web_store import Store,AdmissionError
from web_service import request_context,generate_context
from delivery_policy import artifact_fingerprint
from pipeline import Run
from quality import Checked
from reviewer import GATES,DIMENSIONS
from llm import Result
from research_fixtures import routed

PASSWORD='private-test-password-not-a-provider-key-123'
COPY='STORY: زبونك هو كيان؛ خلي رسالتك تبين إنك تعرف شنو يحتاج، مو نفس الكلام ينرسل للكل.'


def checked(**changes):
    obj=Checked(COPY,'mock',status='accepted',story_intent='educational',
        review_history=[{'attempt':1,'score':8,'scores':dict.fromkeys(DIMENSIONS,8),
                         'gates':dict.fromkeys(GATES,'pass')}])
    for key,value in changes.items():setattr(obj,key,value)
    obj.reviewed_artifact_hash=artifact_fingerprint(obj)
    return obj


class WebServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_final_artifact_delivered_and_research_advice_enabled(self):
        context=request_context('رسائل الزبائن','insight');runner=AsyncMock(return_value=Run(checked()))
        result=await generate_context(context,runner=runner)
        self.assertEqual(result['state'],'accepted');self.assertTrue(result['copy'])
        call=runner.call_args
        self.assertTrue(call.kwargs['research']);self.assertTrue(call.kwargs['suggest_topics'])
        self.assertEqual(call.kwargs['brief'].strategy_id,'insight')
        self.assertNotIn('STORY:',result['copy'])

    async def test_exact_final_artifact_and_mandatory_gates_enforced(self):
        for obj in [checked(text='bad layout'),checked(refused=True),checked(failures=['failure']),
                    checked(review_history=[]),checked(story_intent='auto')]:
            result=await generate_context(request_context('موضوع','insight'),runner=AsyncMock(return_value=Run(obj)))
            self.assertEqual(result['copy'],'');self.assertEqual(result['state'],'blocked')
        obj=checked();obj.text+=' changed after review'
        result=await generate_context(request_context('موضوع','insight'),runner=AsyncMock(return_value=Run(obj)))
        self.assertEqual(result['copy'],'')
        obj=checked();obj.review_history[-1]['gates']['voice_preservation']='uncertain'
        result=await generate_context(request_context('موضوع','insight'),runner=AsyncMock(return_value=Run(obj)))
        self.assertEqual(result['copy'],'')

    async def test_below_threshold_text_is_withheld_even_if_manual_flag_set(self):
        obj=checked(status='needs_review',failure_code='creative_threshold',manual_review_ready=True)
        result=await generate_context(request_context('موضوع','insight'),runner=AsyncMock(return_value=Run(obj)))
        self.assertEqual(result['state'],'needs_review');self.assertEqual(result['copy'],'')

    async def test_real_pipeline_receives_web_brief_and_independent_review(self):
        plan={'audience_need':'one insight','objection':'','purpose':'education','framework':'none',
              'logic_chain':[],'missing_information':'','clarification_question':''}
        review={'scores':dict.fromkeys(DIMENSIONS,8),'gates':dict.fromkeys(GATES,'pass'),'issues':[]}
        model=AsyncMock(side_effect=[routed('write'),Result(json.dumps(plan),'mock'),Result(COPY,'mock'),Result(json.dumps(review),'mock')])
        with patch('revision.generate',model):
            result=await generate_context(request_context('رسالة تخص الزبون','insight'))
        self.assertEqual(result['state'],'accepted',result)
        self.assertEqual(model.await_count,4)
        for call in model.call_args_list:self.assertEqual(json.loads(call.args[1])['brief']['strategy_id'],'insight')

    async def test_clarification_and_suggestions_resume_normal_checks(self):
        obj=checked(status='blocked',clarification='شنو نوع المنتج؟')
        context=request_context('الزبون','insight')
        result=await generate_context(context,runner=AsyncMock(return_value=Run(obj)))
        parent={'context':context,'result':result}
        resumed=request_context('ignored','insight',parent=parent,answer='منتج غذائي')
        self.assertFalse(resumed['clarification_allowed']);self.assertIn('منتج غذائي',resumed['topic'])
        parent['result']={'state':'blocked','suggestions':[{'topic':'رد خاص لكل زبون'}]}
        resumed=request_context('ignored','insight',parent=parent,suggestion=0)
        self.assertEqual(resumed['topic'],'رد خاص لكل زبون')
        with self.assertRaises(ValueError):request_context('ignored','insight',parent=parent,suggestion=2)
        with self.assertRaises(ValueError):request_context('ignored','insight',parent=parent,instruction='قصّر')

    async def test_edit_keeps_original_topic_and_rechecks_updated_script(self):
        context=request_context('موضوع أصلي','insight')
        result=await generate_context(context,runner=AsyncMock(return_value=Run(checked())))
        updated=request_context('ignored','insight',parent={'context':context,'result':result},instruction='قصّر النص')
        self.assertEqual(updated['topic'],'موضوع أصلي')
        self.assertIn(result['copy'],updated['brief']['source_material'])
        self.assertIn('قصّر النص',updated['brief']['source_material'])
        runner=AsyncMock(return_value=Run(checked()))
        await generate_context(updated,runner=runner)
        self.assertTrue(runner.call_args.kwargs['research'])


class StoreTests(unittest.TestCase):
    def test_persist_recover_idempotency_conflict_and_quota(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'jobs.sqlite';store=Store(path);context=request_context('موضوع','insight')
            identifier,new=store.admit('request-1',{'topic':'موضوع'},context,None,1)
            self.assertTrue(new)
            self.assertEqual(store.admit('request-1',{'topic':'موضوع'},context,None,1),(identifier,False))
            with self.assertRaisesRegex(AdmissionError,'request_conflict'):store.admit('request-1',{'topic':'different'},context,None,1)
            with self.assertRaisesRegex(AdmissionError,'busy'):store.admit('request-2',{},context,None,1)
            Store(path).recover()
            self.assertEqual(store.get(identifier)['state'],'interrupted')
            with self.assertRaisesRegex(AdmissionError,'daily_limit'):store.admit('request-2',{},context,None,1)


class WebHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'jobs.sqlite'
        self.generator=AsyncMock(return_value={'state':'accepted','message':'test','copy':'synthetic fixture',
                    'score':None,'sources':[],'suggestions':[],'notices':[]})
        self.app=create_app(path=self.path,password=PASSWORD,demo=False,generate=self.generator)
        self.client=TestClient(self.app);self.client.__enter__()

    def tearDown(self):self.client.__exit__(None,None,None);self.temp.cleanup()

    def login(self):
        response=self.client.post('/api/session',json={'password':PASSWORD})
        self.assertEqual(response.status_code,200)
        self.assertIn('httponly',response.headers['set-cookie'].lower())

    def submit(self,**extra):
        return self.client.post('/api/jobs',json={'request_id':str(uuid4()),'topic':'رسائل زبائنك','strategy_id':'insight',**extra})

    def wait_job(self,identifier):
        for _ in range(80):
            job=self.client.get('/api/jobs/'+identifier).json()
            if job['state'] not in ('queued','running'):return job
            time.sleep(.01)
        self.fail('job did not finish')

    def test_private_api_login_logout_and_page_never_contains_secret(self):
        self.assertEqual(self.client.get('/api/jobs').status_code,401)
        page=self.client.get('/')
        self.assertEqual(page.status_code,200);self.assertNotIn(PASSWORD,page.text)
        self.assertIn("script-src 'self'",page.headers['content-security-policy'])
        self.assertEqual(self.client.post('/api/session',json={'password':'wrong'}).status_code,401)
        self.login();self.assertEqual(self.client.get('/api/config').status_code,200)
        self.client.delete('/api/session');self.assertEqual(self.client.get('/api/jobs').status_code,401)
        self.generator.assert_not_awaited()

    def test_generate_poll_history_edit_and_single_use_request_identity(self):
        self.login();request_id=str(uuid4());response=self.submit(request_id=request_id)
        self.assertEqual(response.status_code,202,response.text)
        identifier=response.json()['id'];self.assertEqual(self.wait_job(identifier)['state'],'accepted')
        replay=self.submit(request_id=request_id)
        self.assertEqual(replay.json()['id'],identifier);self.assertEqual(self.generator.await_count,1)
        self.assertEqual(self.submit(request_id=request_id,topic='different').status_code,409)
        edit=self.submit(parent_id=identifier,instruction='قصّر النص')
        self.assertEqual(edit.status_code,202,edit.text);self.wait_job(edit.json()['id'])
        context=self.generator.call_args.args[0]
        self.assertEqual(context['topic'],'رسائل زبائنك');self.assertIn('قصّر النص',context['brief']['source_material'])
        history=self.client.get('/api/jobs').json();self.assertEqual(len(history),2)
        self.assertNotIn('context',json.dumps(history));self.assertNotIn('payload',json.dumps(history))

    def test_invalid_requests_cross_origin_oversized_body_do_not_start_models(self):
        self.login()
        self.assertEqual(self.submit(strategy_id='professional').status_code,422)
        self.assertEqual(self.submit(topic='   ').status_code,422)
        self.assertEqual(self.submit(parent_id='0'*32,instruction='change').status_code,404)
        self.assertEqual(self.client.post('/api/jobs',json={'request_id':str(uuid4()),'secret':'private-value'}).status_code,422)
        response=self.client.post('/api/jobs',json={'secret':'private-value'})
        self.assertNotIn('private-value',response.text)
        self.assertEqual(self.client.post('/api/jobs',json={},headers={'Origin':'https://other.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/jobs',content=b'a'*33000).status_code,413)
        self.generator.assert_not_awaited()

    def test_provider_exception_redacted_and_no_script_exposed(self):
        self.login();self.generator.side_effect=RuntimeError('private provider payload with credentials')
        response=self.submit();job=self.wait_job(response.json()['id'])
        self.assertEqual(job['state'],'error');self.assertEqual(job['result']['copy'],'')
        self.assertNotIn('credentials',json.dumps(job))

    def test_login_attempt_limit(self):
        for _ in range(5):self.client.post('/api/session',json={'password':'bad'})
        self.assertEqual(self.client.post('/api/session',json={'password':PASSWORD}).status_code,429)

    def test_demo_is_isolated_and_never_uses_injected_live_runner(self):
        with TestClient(create_app(path=Path(self.temp.name)/'demo.sqlite',demo=True,generate=self.generator)) as client:
            response=client.post('/api/jobs',json={'request_id':str(uuid4()),'topic':'موضوع','strategy_id':'insight'})
            for _ in range(50):
                job=client.get('/api/jobs/'+response.json()['id']).json()
                if job['state']=='accepted':break
                time.sleep(.01)
            self.assertEqual(job['result']['calls'],0);self.assertIsNone(job['result']['score'])
            self.assertTrue(client.get('/api/config').json()['demo'])
        self.generator.assert_not_awaited()

    def test_live_start_requires_explicit_owner_password(self):
        with self.assertRaises(ValueError):create_app(path=self.path,password='',demo=False)


class VercelBridgeTests(unittest.TestCase):
    def test_frontend_origin_is_rejected_until_explicitly_configured(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,{'WEB_PUBLIC_ORIGIN':''}):
            with TestClient(create_app(path=Path(folder)/'jobs.sqlite',password=PASSWORD,demo=False),
                            base_url='https://backend.example') as client:
                response=client.post('/api/session',json={'password':PASSWORD},
                                     headers={'Origin':'https://workshop.vercel.app'})
                self.assertEqual(response.status_code,403)

    def test_configured_proxy_origin_login_cookie_and_generation(self):
        generator=AsyncMock(return_value={'state':'blocked','copy':'','message':'fixture','suggestions':[]})
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'WEB_PUBLIC_ORIGIN':'https://workshop.vercel.app/'}):
            with TestClient(create_app(path=Path(folder)/'jobs.sqlite',password=PASSWORD,demo=False,generate=generator),
                            base_url='https://backend.example') as client:
                origin={'Origin':'https://workshop.vercel.app'}
                response=client.post('/api/session',json={'password':PASSWORD},headers=origin)
                self.assertEqual(response.status_code,200,response.text)
                cookie=response.headers['set-cookie'].lower()
                self.assertIn('secure',cookie);self.assertIn('httponly',cookie)
                self.assertIn('samesite=strict',cookie);self.assertNotIn('domain=',cookie)
                response=client.post('/api/jobs',headers=origin,json={'request_id':str(uuid4()),'topic':'اختبار الوصلة','strategy_id':'insight'})
                self.assertEqual(response.status_code,202,response.text)
                self.assertEqual(client.get('/api/jobs').status_code,200)
                hostile={'Origin':'https://another-project.vercel.app'}
                self.assertEqual(client.post('/api/session',json={'password':PASSWORD},headers=hostile).status_code,403)
                self.assertEqual(client.delete('/api/session',headers=hostile).status_code,403)
                self.assertEqual(client.delete('/api/session',headers=origin).status_code,200)
                self.assertEqual(client.get('/api/jobs').status_code,401)

    def test_invalid_frontend_origins_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            for value in ('*','https://*.vercel.app','http://workshop.vercel.app',
                          'https://workshop.vercel.app/path','https://user:pass@workshop.vercel.app',
                          'https://workshop.vercel.app?query=1','https://workshop.vercel.app#fragment',
                          'https://workshop.vercel.app:1234','https://a.example https://b.example'):
                with self.subTest(value=value),patch.dict(os.environ,{'WEB_PUBLIC_ORIGIN':value}):
                    with self.assertRaises(ValueError):create_app(path=Path(folder)/'jobs.sqlite',password=PASSWORD,demo=False)

    def test_vercel_static_files_and_api_rewrites_match_frontend_requests(self):
        root=Path(__file__).resolve().parents[1]
        config=json.loads((root/'vercel.json').read_text())
        self.assertIsNone(config['framework']);self.assertEqual(config['outputDirectory'],'dist')
        self.assertEqual(config['buildCommand'],'node scripts/build_web.mjs')
        rules={r['source']:r['destination'] for r in config['rewrites']}
        self.assertEqual(rules['/api/:path*'],'https://content-writer-iraqi.onrender.com/api/:path*')
        self.assertEqual(rules['/health'],'https://content-writer-iraqi.onrender.com/health')
        self.assertEqual(rules['/assets/:path*'],'/:path*')
        for name in ('index.html','workshop.js','workshop.css','progress.json'):
            self.assertTrue((root/'web'/name).is_file())
        self.assertNotIn('VERCEL_TOKEN',json.dumps(config));self.assertNotIn('ANTHROPIC_API_KEY',json.dumps(config))


class StaticFrontendBuildTests(unittest.TestCase):
    def test_build_creates_only_public_assets_and_matches_vercel_output(self):
        import shutil
        import subprocess
        if not shutil.which('node'):self.skipTest('Node is required for the Vercel frontend build')
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            destination=Path(folder)/'dist'
            result=subprocess.run(['node',str(root/'scripts/build_web.mjs'),str(destination)],
                cwd=folder,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual({p.name for p in destination.iterdir()},
                             {'index.html','workshop.js','workshop.css','progress.json'})
            for item in destination.iterdir():self.assertEqual(item.read_bytes(),(root/'web'/item.name).read_bytes())
