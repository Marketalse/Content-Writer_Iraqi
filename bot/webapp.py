"""Private single-owner web preview; run separately from the Telegram worker.

WEB_DEMO=1 disables ALL model calls and uses a separate disposable job store.
"""
import asyncio
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
from content_layers import CATALOG, STRATEGIES
from web_service import generate_context, request_context
from web_store import Store, AdmissionError, public_job

log=logging.getLogger('workshop-web')


class NewJob(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    request_id: str=Field(min_length=32,max_length=36)
    topic: str=Field(default='',max_length=4000)
    strategy_id: str=Field(default='insight',max_length=30)
    parent_id: str|None=Field(default=None,pattern=r'^[a-f0-9]{32}$')
    instruction: str=Field(default='',max_length=1500)
    answer: str=Field(default='',max_length=1500)
    suggestion: int|None=Field(default=None,ge=0,le=2)


class Login(BaseModel):
    model_config=ConfigDict(extra='forbid')
    password: str=Field(max_length=200)


async def demonstration(context):
    await asyncio.sleep(.15)
    return {'state':'accepted','message':'عرض توضيحي فقط — ما استخدمنا موديل ولا سوّينا مراجعة فعلية.',
        'copy':'زبونك هو كيان؛ خلي رسالتك إله تبين إنك تعرف شنو يحتاج. رسالة باسمه وطلبه، مو نفس الكلام ينرسل للكل.',
        'score':None,'sources':[],'suggestions':[],'cost_usd':0,'calls':0,'failure_code':'','notices':[]}


def create_app(*,path=None,password=None,demo=None,generate=None):
    demo=(os.getenv('WEB_DEMO')=='1') if demo is None else demo
    password=password if password is not None else os.getenv('WEB_PREVIEW_PASSWORD','')
    if not demo and not 32<=len(password)<=200:
        raise ValueError('Configure WEB_PREVIEW_PASSWORD with 32–200 characters in secure environment settings')
    daily_limit=int(os.getenv('WEB_DAILY_LIMIT','20'))
    if not 1<=daily_limit<=100:raise ValueError('invalid web daily limit')
    filename='web-demo.sqlite3' if demo else 'web-preview.sqlite3'
    store=Store(path or Path(os.getenv('STATE_DIR',str(ROOT/'data')))/filename)
    generator=demonstration if demo else (generate or generate_context)
    tasks=set();sessions={};attempts=[]

    @asynccontextmanager
    async def lifespan(app):
        store.recover()
        yield
        for task in list(tasks):task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        store.recover()

    app=FastAPI(title='Content Workshop private preview',lifespan=lifespan,
                docs_url=None,redoc_url=None,openapi_url=None)
    app.state.store=store

    @app.middleware('http')
    async def protect(request:Request,call_next):
        # Same-origin cookie requests only. No public CORS or tokens in page source/URLs.
        if request.method not in ('GET','HEAD','OPTIONS'):
            origin=request.headers.get('origin')
            if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
                return JSONResponse({'message':'هذا الطلب يحتاج ينفتح من نفس صفحة الورشة.'},status_code=403)
            try:size=int(request.headers.get('content-length','0'))
            except ValueError:size=100001
            # Read the bounded body too; Content-Length may be missing or dishonest.
            if size>32000:return JSONResponse({'message':'الطلب أطول من الحد المسموح.'},status_code=413)
            body=bytearray()
            async for part in request.stream():
                body.extend(part)
                if len(body)>32000:return JSONResponse({'message':'الطلب أطول من الحد المسموح.'},status_code=413)
            request._body=bytes(body)
        if request.url.path.startswith('/api/') and request.url.path!='/api/session' and not demo:
            expiry=sessions.get(request.cookies.get('workshop_session',''),0)
            if expiry<time.monotonic():
                return JSONResponse({'message':'سجّل دخول للمعاينة الخاصة.'},status_code=401)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.exception_handler(HTTPException)
    async def safe_http(request,exc):
        return JSONResponse({'message':str(exc.detail)},status_code=exc.status_code)

    from fastapi.exceptions import RequestValidationError
    @app.exception_handler(RequestValidationError)
    async def invalid_request(request,exc):
        # Pydantic's default error body can echo private input; keep it out of responses.
        return JSONResponse({'message':'راجع الموضوع والاختيارات؛ بعض تفاصيل الطلب مو صالحة.'},status_code=422)

    @app.exception_handler(Exception)
    async def server_error(request,exc):
        log.error('web_request_failed type=%s',type(exc).__name__)
        return JSONResponse({'message':'تعذّر إكمال الطلب. جرّب لاحقاً أو راجع صاحب الورشة.'},status_code=500)

    @app.post('/api/session')
    async def login(body:Login,request:Request):
        now=time.monotonic()
        attempts[:]=[t for t in attempts if t>now-60]
        if len(attempts)>=5:raise HTTPException(429,'انتظر دقيقة قبل محاولة الدخول مرة ثانية.')
        if not demo and not secrets.compare_digest(body.password.encode(),password.encode()):
            attempts.append(now)
            raise HTTPException(401,'كلمة مرور المعاينة مو صحيحة.')
        # This is an owner-preview session, not a multi-creator account system.
        sessions.clear()
        session=secrets.token_urlsafe(32);sessions[session]=now+12*3600
        response=JSONResponse({'ok':True})
        response.set_cookie('workshop_session',session,max_age=12*3600,httponly=True,
                            secure=request.url.scheme=='https',samesite='strict')
        return response

    @app.delete('/api/session')
    async def logout(request:Request):
        sessions.pop(request.cookies.get('workshop_session',''),None)
        response=JSONResponse({'ok':True});response.delete_cookie('workshop_session');return response

    @app.get('/health')
    async def health():return {'status':'ok','mode':'demo' if demo else 'owner-preview'}

    @app.get('/api/config')
    async def config():
        return {'demo':demo,'voice':'صوتك المعتمد — عراقي مباشر',
            'platform':'Instagram','feature':'Story','daily_limit':daily_limit,
            'strategies':[{'id':key,'label':CATALOG[key].label} for key in STRATEGIES['story']]}

    async def work(identifier):
        try:
            store.update(identifier,'running')
            result=await generator(store.get(identifier)['context'])
            store.update(identifier,result['state'],result)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.error('web_generation_failed id=%s type=%s',identifier,type(exc).__name__)
            store.update(identifier,'error',{'state':'error','message':'صار خطأ أثناء المعالجة. احتفظ برقم الطلب وجرّب لاحقاً.',
                'copy':'','suggestions':[],'failure_code':'application_error'})

    @app.post('/api/jobs',status_code=202)
    async def start(body:NewJob):
        try:request_id=str(UUID(body.request_id))
        except ValueError:raise HTTPException(422,'معرف الطلب مو صالح.')
        if body.instruction and not body.instruction.strip() or body.answer and not body.answer.strip():
            raise HTTPException(422,'اكتب التعديل أو جواب التوضيح.')
        actions=int(bool(body.instruction))+int(bool(body.answer))+int(body.suggestion is not None)
        if (body.parent_id and actions!=1) or (not body.parent_id and actions):
            raise HTTPException(422,'اختار إجراء واحد مرتبط بالطلب السابق.')
        try:
            parent=store.get(body.parent_id) if body.parent_id else None
            context=request_context(body.topic or (parent['context']['topic'] if parent else ''),body.strategy_id,
                parent=parent,instruction=body.instruction,answer=body.answer,suggestion=body.suggestion)
            identifier,is_new=store.admit(request_id,body.model_dump(exclude={'request_id'}),
                context,body.parent_id,daily_limit)
        except KeyError:raise HTTPException(404,'ما لگينا الطلب.')
        except AdmissionError as exc:
            messages={'busy':'عدك طلب قيد المعالجة. انتظر حتى يخلص.',
                'daily_limit':'وصلت لحد طلبات المعاينة لهذا اليوم.',
                'request_conflict':'هذا المعرف مرتبط بطلب مختلف. افتح طلب جديد.'}
            raise HTTPException(429 if str(exc)!='request_conflict' else 409,messages[str(exc)])
        except ValueError:raise HTTPException(422,'الاختيارات أو الإجراء ما يناسب الطلب.')
        if is_new:
            task=asyncio.create_task(work(identifier));tasks.add(task);task.add_done_callback(tasks.discard)
        return public_job(store.get(identifier))

    @app.get('/api/jobs')
    async def recent():return [public_job(job) for job in store.recent()]

    @app.get('/api/jobs/{identifier}')
    async def job(identifier:str):
        try:return public_job(store.get(identifier))
        except KeyError:raise HTTPException(404,'ما لگينا الطلب.')

    @app.get('/')
    async def index():return FileResponse(ROOT/'web/index.html')

    app.mount('/assets',StaticFiles(directory=ROOT/'web'),name='assets')
    return app


if __name__=='__main__':
    import uvicorn
    uvicorn.run('webapp:create_app',factory=True,host=os.getenv('WEB_HOST','127.0.0.1'),
                port=int(os.getenv('PORT','8877')),workers=1)
