"""Deterministic creator-facing layout; never rewrite reviewed script content."""
import re
from platform_intelligence import LEGACY_FORMATS
from quality import render_story_copy
from story_styles import is_story

VIDEO_FIELDS = ('HOOK', 'SCRIPT', 'VISUALS', 'CTA')
VIDEO_HEADER = re.compile(r'(?m)^(HOOK|SCRIPT|VISUALS|CTA):[ \t]*')


def _numbered(body: str) -> str:
    # These are independent text blocks and shot suggestions, not inferred scene pairs.
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return '\n\n'.join(f'{i}. {line}' for i, line in enumerate(lines, 1))


def render_creator_copy(text: str, fmt: str, story_mode: str = 'moment') -> str:
    key = LEGACY_FORMATS.get(fmt, fmt)
    if is_story(key) and story_mode == 'moment':
        return render_story_copy(text)
    if key not in ('tiktok_video', 'instagram_reel'):
        return text
    matches = list(VIDEO_HEADER.finditer(text))
    if tuple(m.group(1) for m in matches) != VIDEO_FIELDS:
        raise ValueError('invalid video delivery fields')
    bodies = [text[m.end():matches[i+1].start() if i+1 < len(matches) else len(text)].strip()
              for i, m in enumerate(matches)]
    return '\n\n━━━━━━━━━━\n\n'.join((
        '🎯 الافتتاحية\n\n' + bodies[0],
        '🎙 النص المنطوق — مقاطع للقراءة\n\n' + _numbered(bodies[1]),
        '🎬 المشاهد المقترحة — تعليمات التصوير\n\n' + _numbered(bodies[2]),
        '💬 دعوة التفاعل\n\n' + bodies[3],
    ))
