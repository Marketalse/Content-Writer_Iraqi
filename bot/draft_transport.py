"""Lossless native-field rendering and transport-label adaptation.

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
    # Labeling is not acceptance: length validation and bounded shortening run next.
    if not body.strip() or SECTION.search(body):
        return text
    return 'STORY: ' + body


def writer_fields(fmt, story_mode='moment', story_intent='auto'):
    """Fixed native fields; dynamic articles/carousels/sequence retain their contracts."""
    from quality import FIELDS
    from platform_intelligence import LEGACY_FORMATS
    key = LEGACY_FORMATS.get(fmt, fmt)
    if story_mode != 'moment' or key == 'linkedin_article':
        return ()
    return ('STORY',) if is_story(key) and story_intent != 'auto' else FIELDS.get(key, ())


def writer_schema(fields):
    if not fields:
        return None
    return {'type': 'object', 'properties': {name: {'type': 'string'} for name in fields},
            'required': list(fields), 'additionalProperties': False}


def render_writer(text, fields):
    """Render validated field envelopes; legacy prose still undergoes native validation."""
    import json
    if fields and text.lstrip().startswith('{'):
        try:
            def unique(pairs):
                out = {}
                for key, value in pairs:
                    if key in out:
                        raise ValueError('duplicate writer field')
                    out[key] = value
                return out
            data = json.loads(text, object_pairs_hook=unique)
        except ValueError:
            return text
        if (isinstance(data, dict) and set(data) == set(fields)
                and all(isinstance(data[name], str) for name in fields)):
            return '\n'.join(name + ': ' + data[name] for name in fields)
    return text


def normalize_headings(text, fields):
    """Normalize only allowlisted colon headings; never reorder or infer bodies."""
    if not fields:
        return text
    names = '|'.join(re.escape(name) for name in fields)
    # Matched wrappers must be balanced; arbitrary bullets, fences and aliases stay invalid.
    pattern = re.compile(r'(?im)^[ \t]*(?:(?P<w1>\*\*|__)(?P<inside>' + names +
                         r')[ \t]*:(?P=w1)|(?P<w2>\*\*|__)(?P<outside>' + names +
                         r')(?P=w2)[ \t]*:|(?P<plain>' + names + r')[ \t]*:)')
    return pattern.sub(lambda m: (m.group('inside') or m.group('outside') or m.group('plain')).upper() + ':', text)


def field_details(text, fields):
    """Allowlisted structural metadata only; no draft bodies or unknown labels."""
    if not fields:
        return {}
    matches = list(re.finditer(r'(?m)^([A-Z][A-Z ]*(?: \d+)?)\s*:[ \t]*', text))
    observed = [m.group(1) for m in matches]
    empty = []
    for i, match in enumerate(matches):
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        if match.group(1) in fields and not text[match.end():end].strip():
            empty.append(match.group(1))
    return {'expected': list(fields), 'present': [name for name in observed if name in fields],
            'missing': [name for name in fields if name not in observed], 'empty': empty,
            'duplicates': [name for name in fields if observed.count(name) > 1],
            'order_valid': observed == list(fields),
            'unexpected_fields': any(name not in fields for name in observed)}
