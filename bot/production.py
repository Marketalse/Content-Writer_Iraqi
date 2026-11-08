"""Optional shoot-ready plan, separated from publishable copy and checked before use."""
import json
import math

PRODUCTION_INSTRUCTION = '''Production mode is enabled. Return ONLY JSON with keys content and production.
content is the complete native-format draft string (unchanged native section labels).
production has duration_seconds, scenes, caption, facts_to_confirm and checks.
Each scene has start_seconds, end_seconds, shot, action, spoken, overlay and fallback.
Scenes are contiguous from 0 to the requested duration, without gaps or overlaps (1-16 scenes).
Every nonempty spoken line must appear verbatim in the content's HOOK, SCRIPT or CTA.
Together the scenes must cover ALL spoken HOOK, SCRIPT and CTA text exactly once in order.
Respect supplied filming constraints; provide feasible fallback footage. Overlays are readable
short phrases, not the full spoken paragraph. Use only supplied facts, placeholders for unknowns.
No invented testimonials, results, urgency, links, rights clearance or automation.
checks and facts_to_confirm are lists of strings; never claim that consent/music rights were verified.
Keep production directions separate from content. The reviewer assesses both.'''


def validate_plan(plan: dict, content: str, duration: int) -> dict:
    if not isinstance(plan, dict) or set(plan) != {'duration_seconds', 'scenes', 'caption', 'facts_to_confirm', 'checks'}:
        raise ValueError('invalid production keys')
    if type(plan['duration_seconds']) is not int or plan['duration_seconds'] != duration:
        raise ValueError('production duration mismatch')
    if not isinstance(plan['scenes'], list) or not 1 <= len(plan['scenes']) <= 16:
        raise ValueError('invalid production scenes')
    from quality import _field, split_owner_note
    content, _ = split_owner_note(content)
    speech = '\n'.join(_field(content, k) for k in ('HOOK', 'SCRIPT', 'CTA'))
    previous = 0
    for scene in plan['scenes']:
        if not isinstance(scene, dict) or set(scene) != {'start_seconds', 'end_seconds', 'shot', 'action', 'spoken', 'overlay', 'fallback'}:
            raise ValueError('invalid scene')
        start, end = scene['start_seconds'], scene['end_seconds']
        if (any(type(v) not in (int, float) or not math.isfinite(v) for v in (start, end))
                or start != previous or not start < end <= duration):
            raise ValueError('scene timing must be contiguous')
        for key in ('shot', 'action', 'spoken', 'overlay', 'fallback'):
            if not isinstance(scene[key], str) or len(scene[key]) > 1000:
                raise ValueError('invalid scene text')
        if not all(scene[k].strip() for k in ('shot', 'action', 'fallback')):
            raise ValueError('missing filming directions')
        if scene['spoken'] and scene['spoken'] not in speech:
            raise ValueError('production speech differs from approved native copy')
        if len(scene['overlay'].split()) > 12:
            raise ValueError('overlay too dense (editorial bound)')
        previous = end
    spoken = ' '.join(scene['spoken'] for scene in plan['scenes'])
    if ' '.join(spoken.split()) != ' '.join(speech.split()):
        raise ValueError('production must cover the complete spoken script in order')
    if previous != duration or not isinstance(plan['caption'], str) or len(plan['caption']) > 1500:
        raise ValueError('invalid production end/caption')
    for name in ('facts_to_confirm', 'checks'):
        if (not isinstance(plan[name], list) or len(plan[name]) > 12
                or any(not isinstance(s, str) or not s.strip() or len(s) > 500 for s in plan[name])):
            raise ValueError('invalid production checklist')
    return plan


def unpack_draft(raw: str, duration: int) -> tuple[str, dict]:
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != {'content', 'production'} or not isinstance(data['content'], str):
        raise ValueError('invalid production envelope')
    return data['content'], validate_plan(data['production'], data['content'], duration)


def render_plan(plan: dict) -> str:
    lines = ['🎬 خطة التصوير — منفصلة عن نص النشر']
    for s in plan['scenes']:
        lines.extend([f"{s['start_seconds']}–{s['end_seconds']} ثانية | {s['shot']}",
                      s['action'], 'الكلام: ' + s['spoken'], 'عالشاشة: ' + s['overlay'],
                      'بديل: ' + s['fallback']])
    lines.extend(['الكابشن: ' + plan['caption'], 'قبل التصوير والنشر:',
                  *plan['facts_to_confirm'], *plan['checks']])
    return '\n'.join(lines)
