"""Verify audit fixes and regenerate a local progress report; optional change watcher."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'test_reports' / 'fixes'
CHECKS = [
    ('PB-01', 'Recover torn history safely', 'JournalRecoveryTests'),
    ('PB-02', 'Atomic pilot settings; corrupt settings deny access', 'PilotConfigAtomicTests'),
    ('PB-03', 'Complete facilitator integration and regressions', 'FacilitatorRegressionTests'),
    ('PB-04', 'Shorten unambiguous unlabeled Stories', 'StoryRepairTests'),
    ('PB-05', 'Distinguish factual claims from numbered preferences', 'RoutingBoundaryTests'),
    ('PB-06', 'Reserve batch costs before starting work', 'BatchBudgetTests'),
    ('PB-07', 'Reject invalid batch concurrency and budgets', 'BatchValidationTests'),
    ('PB-08', 'Gate main deployment on CI', 'DeploymentGateTests'),
    ('PB-09', 'Reject duplicate routing/research JSON keys', 'RoutingParserTests'),
    ('PB-10', 'Make publication confirmation idempotent', 'PublicationIdempotencyTests'),
]


def atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False, encoding='utf-8') as f:
        f.write(text)
        temp = Path(f.name)
    os.replace(temp, path)


def save(state):
    state['updated_at'] = datetime.now(ZoneInfo('Asia/Baghdad')).isoformat()
    atomic(OUT / 'status.json', json.dumps(state, indent=2))
    lines = ['# Audit fix progress', '', 'Updated: ' + state['updated_at'], '',
             'Run state: **' + state['state'] + '**. Local results only; not deployed.', '',
             '| Issue | Fix | Status | Tests |', '|---|---|---|---|']
    for item in state['issues']:
        result = item.get('result') or {}
        lines.append(f"| {item['id']} | {item['title']} | {item['status']} | {result.get('run', 'not run')} |")
    lines += ['', 'Full suite: ' + json.dumps(state.get('suite') or {'status': 'not run'}), '',
              'External checks pending: secure credentials and authorized live API/Telegram smoke tests; '
              'GitHub required checks and Render deployment enforcement. No paid calls are made by this runner.', '',
              'Report updates when checks run. Watch mode only operates while its process is alive.']
    atomic(OUT / 'REPORT.md', '\n'.join(lines) + '\n')
    rows = ''.join('<tr><td>' + html.escape(item['id']) + '</td><td>' + html.escape(item['title'])
                   + '</td><td>' + html.escape(item['status']) + '</td><td>'
                   + str((item.get('result') or {}).get('run', '—')) + '</td></tr>' for item in state['issues'])
    atomic(OUT / 'index.html', '<!doctype html><html lang="en"><meta charset="utf-8">'
           '<meta http-equiv="refresh" content="5"><meta name="viewport" content="width=device-width">'
           '<title>Audit fix progress</title><style>body{font:16px/1.5 system-ui;max-width:1100px;margin:30px auto;padding:15px;background:#f4f7fb;color:#17304a}'
           'table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;text-align:left;border:1px solid #d7e0eb}code{white-space:pre-wrap}</style>'
           '<h1>Audit fix progress</h1><p>Run state: <b>' + html.escape(state['state']) + '</b> · '
           + html.escape(state['updated_at']) + '</p><p>Automatically refreshes every five seconds. '
           'Local verification is separate from deployment and live-service access.</p>'
           '<table><tr><th>Issue</th><th>Correction</th><th>Status</th><th>Tests run</th></tr>' + rows + '</table>'
           '<p>Full suite:</p><code>' + html.escape(json.dumps(state.get('suite') or {'status': 'not run'}, indent=2))
           + '</code><p>Pending external checks: GitHub/Render enforcement and authorized live AI/search/Telegram tests.</p>'
           '<p>No paid API calls. Watch mode is active only while its process is running.</p></html>')


def worker(group):
    os.chdir(ROOT)
    sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'bot')]
    sys.dont_write_bytecode = True
    def deny(*args, **kwargs):
        raise RuntimeError('Verification runner: network connections disabled')
    socket.socket.connect = deny
    socket.create_connection = deny
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern='test_*.py' if group == 'ALL' else 'test_audit_fixes.py')
    def flatten(test):
        for item in test:
            if isinstance(item, unittest.TestSuite):
                yield from flatten(item)
            else:
                yield item
    selected = unittest.TestSuite(t for t in flatten(suite) if group == 'ALL' or group in t.id() or isinstance(t, unittest.loader._FailedTest))
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(selected)
    executed = result.testsRun - len(result.skipped) - len(result.expectedFailures)
    summary = {'run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
               'skipped': len(result.skipped), 'success': result.wasSuccessful() and executed > 0,
               'failed_tests': [t.id() for t, _ in result.failures + result.errors]}
    print(json.dumps(summary))
    return 0 if summary['success'] else 1


def run_check(group):
    try:
        run = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', group],
                             cwd=ROOT, text=True, capture_output=True, timeout=90)
        atomic(OUT / (group + '.log'), run.stderr + '\n' + run.stdout)
        data = json.loads(run.stdout.strip().splitlines()[-1])
        data['success'] = data['success'] and run.returncode == 0
        return data
    except (subprocess.TimeoutExpired, ValueError, IndexError):
        return {'run': 0, 'success': False, 'error': 'Verification timed out or returned no valid result'}


def verify():
    started = fingerprint()
    state = {'state': 'RUNNING', 'issues': [{'id': i, 'title': t, 'status': 'PENDING'} for i, t, _ in CHECKS],
             'live_checks': 'NOT RUN', 'deployed': False,
             'source_fingerprint': hashlib.sha256(json.dumps(started).encode()).hexdigest()}
    save(state)
    for item, (_, _, group) in zip(state['issues'], CHECKS):
        item['status'] = 'RUNNING'; save(state)
        item['result'] = result = run_check(group)
        item['status'] = ('LOCAL PASS; EXTERNAL CONFIRMATION PENDING' if item['id'] == 'PB-08' else 'VERIFIED LOCALLY') if result['success'] else 'FAILING / NOT VERIFIED'
        save(state)
        print(item['id'], item['status'], flush=True)
    state['suite'] = run_check('ALL')
    if not state['suite']['success']:
        state['issues'][2]['status'] = 'FAILING FULL SUITE'
    success = state['suite']['success'] and all(x['result']['success'] for x in state['issues'])
    state['state'] = 'LOCAL CHECKS PASSED; EXTERNAL CHECKS PENDING' if success else 'CHECKS FAILED'
    if fingerprint() != started:
        success = False
        state['state'] = 'SOURCE CHANGED DURING CHECKS; RECHECK REQUIRED'
        for item in state['issues']:
            item['status'] = 'STALE; RECHECK REQUIRED'
    save(state)
    return success


def fingerprint():
    paths = [p for folder in ('bot', 'tests', 'scripts', '.github') for p in (ROOT / folder).rglob('*')
             if p.is_file() and p.suffix in ('.py', '.yml', '.yaml') and '__pycache__' not in p.parts]
    paths += [ROOT / 'render.yaml', ROOT / 'bot/requirements.txt', ROOT / '.env.example']
    return [(str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in sorted(paths)]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--worker')
    args = parser.parse_args()
    if args.worker:
        sys.exit(worker(args.worker))
    last = fingerprint()
    success = verify()
    if args.watch:
        print('Watching source/test/config changes; Ctrl+C stops the watcher.', flush=True)
        try:
            while True:
                time.sleep(2)
                current = fingerprint()
                if current != last:
                    last = current
                    verify()
        except KeyboardInterrupt:
            pass
    else:
        sys.exit(0 if success else 1)
