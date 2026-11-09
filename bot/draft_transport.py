"""Lossless transport-label adaptation for explicit single-Story scripts.

A short Story has one body, so adding its transport key is deterministic. This
never repairs content, infers missing multi-section fields, or accepts a draft.
Native validation and independent review must still run on the resulting text.
"""
import re
from story_styles import STORY_STYLES, is_story

# Known single-key markdown variants; strip only the transport label's decoration.
STORY_LABEL = re.compile(r'\A(?:\*\*STORY[ \t]*:\*\*|\*\*STORY\*\*[ \t]*:|STORY[ \t]*:)[ \t]*', re.I)
SECTION = re.compile(r'(?im)^[ \t]*(?:[*_`#]+[ \t]*)?[A-Z][A-Z0-9 _-]{1,40}(?:[*_`]+)?[ \t]*:')


def normalize_short_story(text: str, fmt: str, *, story_mode: str = 'moment',
                          story_intent: str = 'auto') -> str:
    """Add/canonicalize only STORY:, leaving ambiguous or multi-section output invalid."""
    if not is_story(fmt) or story_mode != 'moment' or story_intent not in STORY_STYLES:
        return text
    source = text.strip()
    if not source or source.startswith(('```', '{', '[', '<', '#')):
        return text
    label = STORY_LABEL.match(source)
    body = source[label.end():] if label else source
    # A second/other section cannot be flattened into the spoken script.
    if (not body.strip() or SECTION.search(body) or len(body) > 800
            or len(body.split()) > 75):
        return text
    return 'STORY: ' + body
