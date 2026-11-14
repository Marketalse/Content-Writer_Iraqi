"""Durable single-owner preview jobs, idempotency and bounded daily admission."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class AdmissionError(ValueError):pass


class Store:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, request_id TEXT UNIQUE, '
                       'created TEXT, state TEXT, payload TEXT, context TEXT, result TEXT, parent_id TEXT)')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=5)
        db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()

    def recover(self):
        with self.connect() as db:
            db.execute("UPDATE jobs SET state='interrupted', result=? WHERE state IN ('queued','running')",
                (json.dumps({'state':'interrupted','message':'توقف التشغيل قبل اكتمال الطلب. تگدر تعيد المحاولة؛ ما عدنا نتيجة معتمدة.',
                             'copy':'','suggestions':[]}),))

    def get(self,identifier):
        with self.connect() as db:row=db.execute('SELECT * FROM jobs WHERE id=?',(identifier,)).fetchone()
        if row is None:raise KeyError('unknown job')
        return dict(row)|{key:json.loads(row[key]) for key in ('payload','context','result')}

    def recent(self):
        with self.connect() as db:rows=db.execute('SELECT id FROM jobs ORDER BY created DESC LIMIT 30').fetchall()
        return [self.get(row['id']) for row in rows]

    def admit(self,request_id,payload,context,parent_id,limit):
        contents=json.dumps(payload,ensure_ascii=False,sort_keys=True)
        now=datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT id,payload FROM jobs WHERE request_id=?',(request_id,)).fetchone()
            if previous:
                if previous['payload']!=contents:raise AdmissionError('request_conflict')
                return previous['id'],False
            if db.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]:
                raise AdmissionError('busy')
            count=db.execute('SELECT COUNT(*) FROM jobs WHERE created>=?',(now[:10],)).fetchone()[0]
            if count>=limit:raise AdmissionError('daily_limit')
            identifier=uuid.uuid4().hex
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)',
                (identifier,request_id,now,'queued',contents,json.dumps(context,ensure_ascii=False),'{}',parent_id))
        return identifier,True

    def update(self,identifier,state,result=None):
        with self.connect() as db:
            if result is None:db.execute('UPDATE jobs SET state=? WHERE id=?',(state,identifier))
            else:db.execute('UPDATE jobs SET state=?, result=? WHERE id=?',
                            (state,json.dumps(result,ensure_ascii=False),identifier))


def public_job(job):
    # Never return internal briefs, raw model output, credentials or provider exceptions.
    return {key:job[key] for key in ('id','created','state','parent_id')}|{
        'topic':job['context']['topic'],'strategy_id':job['context']['strategy_id'],
        'result':job['result']}
