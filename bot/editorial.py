"""Explicit human feedback and manual outcomes. No automatic learning or publication."""
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from uuid import uuid4

from platform_intelligence import LEGACY_FORMATS, get_profile
from postlog import read_all
from pilot import is_owner
from quality import check

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.getenv('STATE_DIR') or ROOT)
EVENTS = STATE / 'data/editorial_events.jsonl'
EXAMPLES = STATE / 'data/reviewed_examples.json'
COMMON_METRICS = {'reach', 'views', 'qualified_inquiries', 'bookings', 'sales', 'subscribers',
                  'profile_visits', 'ad_spend', 'attributed_revenue'}
MONEY = {'ad_spend', 'attributed_revenue'}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _events():
    if not EVENTS.exists():
        return []
    return [json.loads(line) for line in EVENTS.read_text(encoding='utf-8').splitlines() if line.strip()]


def _append(record):
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS.open('a', encoding='utf-8') as file:
        file.write(json.dumps({**record, 'recorded_at': _now()}, ensure_ascii=False) + '\n')


def authorized_post(pid: str, actor: int) -> dict:
    for record in reversed(read_all()):
        if record.get('event') == 'generated' and record.get('id') == pid:
            if str(record.get('chat_id')) == str(actor) or is_owner(actor):
                return record
            break
    raise ValueError('post unavailable for this chat')


def feedback(pid: str, actor: int, decision: str, reason: str):
    authorized_post(pid, actor)
    if decision not in ('accept', 'reject') or not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValueError('feedback needs accept/reject and a short reason')
    _append({'event': 'feedback', 'post_id': pid, 'actor': actor, 'decision': decision, 'reason': reason})


def record_result(pid: str, actor: int, data: dict):
    post = authorized_post(pid, actor)
    required = {'metric', 'value', 'window_hours', 'source'}
    if not isinstance(data, dict) or not required <= set(data) or set(data) - required - {'denominator', 'currency'}:
        raise ValueError('outcome schema')
    profile = get_profile(post['format'])
    if not isinstance(data['metric'], str) or data['metric'] not in set(profile.metrics) | COMMON_METRICS:
        raise ValueError('unsupported metric for selected format')
    for name in ('value', 'window_hours', 'denominator'):
        if name not in data:
            continue
        value = data[name]
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('outcome numbers must be finite and nonnegative')
    if not 0 < data['window_hours'] <= 8760 or not isinstance(data['source'], str) or not 1 <= len(data['source'].strip()) <= 300:
        raise ValueError('outcome needs measurement window and source')
    if data['metric'] in MONEY:
        currency = data.get('currency', '')
        if not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isupper():
            raise ValueError('monetary outcomes need a three-letter currency')
    elif 'currency' in data:
        raise ValueError('currency is only valid for monetary outcomes')
    _append({'event': 'result', 'post_id': pid, 'actor': actor, 'platform': profile.platform,
             'format': LEGACY_FORMATS.get(post['format'], post['format']),
             'objective': post.get('objective', profile.objective),
             'story_mode': post.get('story_mode', 'moment'), 'story_intent': post.get('story_intent', 'auto'),
             'journey_stage': post.get('journey_stage', 'unspecified'),
             'distribution': post.get('distribution', 'organic'), **data})


def register_experiment(actor: int, data: dict):
    required = {'baseline_post_id', 'variant_post_id', 'variable', 'hypothesis', 'window_hours'}
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError('experiment schema')
    baseline = authorized_post(data['baseline_post_id'], actor)
    variant = authorized_post(data['variant_post_id'], actor)
    if baseline['id'] == variant['id'] or data['variable'] not in ('opening', 'cta', 'visuals', 'narrative'):
        raise ValueError('experiment needs distinct drafts and one supported variable')
    for name in ('format', 'objective', 'story_mode', 'story_intent', 'journey_stage', 'distribution'):
        left, right = baseline.get(name), variant.get(name)
        if name == 'format':
            left, right = LEGACY_FORMATS.get(left, left), LEGACY_FORMATS.get(right, right)
        if left != right:
            raise ValueError('experiment cohorts must match')
    if (not isinstance(data['hypothesis'], str) or not 1 <= len(data['hypothesis'].strip()) <= 1000
            or type(data['window_hours']) not in (int, float)
            or not math.isfinite(data['window_hours']) or not 0 < data['window_hours'] <= 8760):
        raise ValueError('experiment needs hypothesis and measurement window')
    _append({'event': 'experiment', 'post_id': baseline['id'], 'actor': actor, **data,
             'status': 'registered_uncontrolled_observation',
             'interpretation': 'No winner or causal conclusion is inferred automatically.'})


def approved_examples(fmt: str, mode: str = 'moment', story_intent: str = 'auto') -> list[dict]:
    if not EXAMPLES.exists():
        return []
    key = LEGACY_FORMATS.get(fmt, fmt)
    rows = json.loads(EXAMPLES.read_text(encoding='utf-8'))
    return [row for row in rows if row['format'] == key and row.get('story_mode', 'moment') == mode
            and row.get('story_intent', 'auto') == story_intent][-2:]


def approve_example(fmt: str, mode: str, text: str, reason: str, actor: int, *, story_intent: str = 'auto') -> str:
    if not is_owner(actor):
        raise PermissionError('only owner can approve examples')
    get_profile(fmt)
    if not isinstance(text, str) or not text.strip() or len(text) > 18000 or not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValueError('example needs text and review reason')
    failures = check(fmt, text, story_mode=mode, story_intent=story_intent)
    if failures:
        raise ValueError('example fails native structure')
    rows = json.loads(EXAMPLES.read_text(encoding='utf-8')) if EXAMPLES.exists() else []
    identifier = uuid4().hex[:12]
    rows.append({'id': identifier, 'format': LEGACY_FORMATS.get(fmt, fmt), 'story_mode': mode, 'story_intent': story_intent,
                 'text': text, 'reason': reason, 'approved_by': actor, 'approved_at': _now()})
    EXAMPLES.parent.mkdir(parents=True, exist_ok=True)
    temporary = EXAMPLES.with_suffix('.tmp')
    temporary.write_text(json.dumps(rows[-240:], ensure_ascii=False), encoding='utf-8')
    temporary.replace(EXAMPLES)
    return identifier


def remove_example(identifier: str, actor: int) -> bool:
    if not is_owner(actor):
        raise PermissionError('only owner can remove examples')
    rows = json.loads(EXAMPLES.read_text(encoding='utf-8')) if EXAMPLES.exists() else []
    kept = [r for r in rows if r['id'] != identifier]
    if len(kept) == len(rows):
        return False
    temporary = EXAMPLES.with_suffix('.tmp')
    temporary.write_text(json.dumps(kept, ensure_ascii=False), encoding='utf-8')
    temporary.replace(EXAMPLES)
    return True


def report(actor: int) -> dict:
    rows = [r for r in read_all() if str(r.get('chat_id')) == str(actor)
            and r.get('event') in ('generated', 'clarification')]
    drafts = [r for r in rows if r['event'] == 'generated']
    ids = {r['id'] for r in drafts}
    events = [r for r in _events() if r['post_id'] in ids]
    latest = {r['post_id']: r for r in events if r['event'] == 'feedback'}
    cohorts = {}
    for row in drafts:
        key = LEGACY_FORMATS.get(row['format'], row['format'])
        cohort = '|'.join((key, row.get('story_mode', 'moment'), row.get('story_intent', 'auto'), row.get('objective', 'unspecified'),
                           row.get('journey_stage', 'unspecified'), row.get('distribution', 'organic')))
        group = cohorts.setdefault(cohort, {'drafts': 0, 'accepted_by_engine': 0})
        group['drafts'] += 1
        group['accepted_by_engine'] += row.get('quality_status') == 'accepted'
    latencies = sorted(r['elapsed_ms'] for r in drafts if type(r.get('elapsed_ms')) in (int, float))
    by_id = {r['id']: r for r in drafts}
    return {
        'human_engine_disagreements': {
            'human_rejected_engine_accepted': sum(r['decision'] == 'reject' and by_id[pid].get('quality_status') == 'accepted' for pid, r in latest.items()),
            'human_accepted_engine_not_accepted': sum(r['decision'] == 'accept' and by_id[pid].get('quality_status') != 'accepted' for pid, r in latest.items())},
        'drafts': len(drafts), 'clarifications': len(rows) - len(drafts),
        'engine_accepted': sum(r.get('quality_status') == 'accepted' for r in drafts),
        'human_reviewed': len(latest),
        'human_accepted': sum(r['decision'] == 'accept' for r in latest.values()),
        'human_rejected': sum(r['decision'] == 'reject' for r in latest.values()),
        'revised_drafts': sum(r.get('attempts', 1) > 1 for r in drafts),
        'estimated_cost_usd': round(sum(r.get('cost_usd', 0) for r in rows), 6),
        'unknown_usage_runs': sum(not r.get('usage_known', True) for r in rows),
        'latency_p50_ms': median(latencies) if latencies else None,
        'latency_p95_ms': latencies[max(0, math.ceil(len(latencies) * .95) - 1)] if latencies else None,
        'cohorts': cohorts, 'manual_result_count': sum(r['event'] == 'result' for r in events),
        'manual_results': [r for r in events if r['event'] == 'result'][-30:],
        'experiments': [r for r in events if r['event'] == 'experiment'][-20:],
        'interpretation': 'Descriptive self-reported observations; no causal attribution. '
                          'Do not compare incompatible windows/currencies or equate subscribers with qualified inquiries.',
    }
