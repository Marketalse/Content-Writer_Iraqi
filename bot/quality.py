"""Format-native structural quality gates for platform-specific social publishing formats.

These are local editorial checks, not official ranking rules or fact verification.
The checker never treats a creative heuristic as a platform API limit.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from llm import Result
from platform_intelligence import get_profile, LEGACY_FORMATS
from story_styles import STORY_STYLES, is_story

ROOT = Path(__file__).resolve().parent.parent
OWNER_NOTE = re.compile(r"\*{0,2}NOTE FOR OWNER:?\*{0,2}", re.I)
AI_PHRASES = ROOT / "knowledge" / "copywriting" / "ai_phrases_ar.yaml"
SLIDE = re.compile(r"(?im)^SLIDE[ \t]+(\d+)[ \t]*:[ \t]*(.*)$")
HEADING = re.compile(r"(?im)^#{2,3}\s+\S")
HASHTAG = re.compile(r"(?<!\w)#[\w\u0600-\u06ff]+")
FIELDS = {
    "instagram_story": ("STORY", "INTERACTION"),
    "instagram_reel": ("HOOK", "SCRIPT", "VISUALS", "CTA"),
    "instagram_post": ("HEADLINE", "CAPTION", "CTA"),
    "instagram_instants": ("CAPTION",),
    "instagram_live": ("OPENING", "TALKING POINTS", "AUDIENCE QUESTIONS", "CLOSING"),
    "instagram_broadcast_channel": ("UPDATE", "PROMPT"),
    "linkedin_post": ("INSIGHT", "BODY", "DISCUSSION"),
    "linkedin_article": ("TITLE", "SUMMARY", "CONCLUSION"),
    "tiktok_story": ("STORY", "INTERACTION"),
    "tiktok_video": ("HOOK", "SCRIPT", "VISUALS", "CTA"),
}
MAX_HASHTAGS = {
    "instagram_story": 0, "instagram_instants": 0, "instagram_live": 0,
    "instagram_broadcast_channel": 0, "linkedin_post": 0,
    "linkedin_article": 0, "linkedin_carousel": 0, "tiktok_story": 0,
    "instagram_reel": 5, "instagram_post": 5, "instagram_carousel": 5,
    "tiktok_video": 5, "tiktok_photo_carousel": 5,
}
# Soft editorial bounds; not platform technical limits.
WORD_RANGES = {
    "instagram_story": (2, 140), "instagram_reel": (35, 320),
    "instagram_post": (8, 300), "instagram_carousel": (30, 500),
    "instagram_instants": (1, 35), "instagram_live": (35, 500),
    "instagram_broadcast_channel": (4, 160),
    "linkedin_post": (35, 380), "linkedin_article": (180, 2500),
    "linkedin_carousel": (30, 600),
    "tiktok_story": (2, 140), "tiktok_video": (25, 300),
    "tiktok_photo_carousel": (25, 420),
}

def _field(text: str, name: str) -> str:
    pattern = re.compile(r"(?im)^" + re.escape(name) + r"[ \t]*:[ \t]*(.*)$")
    m = pattern.search(text)
    if not m:
        return ""
    following = re.search(r"(?m)^[A-Z][A-Z 0-9]+\s*:", text[m.end():])
    end = m.end() + following.start() if following else len(text)
    return (m.group(1) + "\n" + text[m.end():end]).strip()

def _common(text: str, key: str, scale: int = 1) -> list[str]:
    issues = []
    if not text.strip():
        return ["empty output"]
    legacy_headers = (r"بداية الفيديو\s*\|\s*Hook", r"المحتوى\s*\|\s*Content",
                      r"القفلة\s*\|\s*CTA")
    if all(re.search(pattern, text, re.I) for pattern in legacy_headers):
        issues.append("retired universal caption template is not a native format")
    count = len(text.split())
    lower, upper = WORD_RANGES[key]
    upper *= scale
    if not lower <= count <= upper:
        issues.append(f"{key}: editorial word target {lower}-{upper}; found {count}")
    tags = HASHTAG.findall(text)
    if len(tags) > MAX_HASHTAGS[key]:
        issues.append(f"{key}: too many hashtags ({len(tags)} > {MAX_HASHTAGS[key]})")
    if AI_PHRASES.exists():
        source = AI_PHRASES.read_text(encoding="utf-8")
        banned = re.findall(r"\{phrase:\s*(.+?),\s*fix:", source)
        for phrase in banned:
            if phrase.strip() and phrase.strip() in text:
                issues.append("AI cliche detected: " + phrase.strip())
                break
    return issues

def _carousel(text: str, key: str) -> list[str]:
    issues = []
    slides = list(SLIDE.finditer(text))
    if not 4 <= len(slides) <= 12:
        issues.append("carousel: expected 4-12 sequential SLIDE N: sections (editorial range)")
    indices = [int(m.group(1)) for m in slides]
    if indices != list(range(1, len(indices) + 1)):
        issues.append("carousel: slide numbering must be consecutive from 1")
    labels = re.findall(r"(?m)^([A-Z][A-Z ]*(?: \d+)?)\s*:", text)
    expected = [f"SLIDE {i}" for i in range(1, len(slides) + 1)] + ["CAPTION", "CTA"]
    if labels != expected:
        issues.append("carousel: native section order invalid")
    for i, match in enumerate(slides):
        section = _field(text, f"SLIDE {i+1}")
        if not section:
            issues.append(f"slide {i+1}: empty content")
        if len(section.split()) > 70:
            issues.append(f"slide {i+1}: too dense, shorten copy")
    if not _field(text, "CAPTION"):
        issues.append("carousel: missing CAPTION:")
    if not _field(text, "CTA"):
        issues.append("carousel: missing CTA:")
    return issues

def _story_sequence(key: str, text: str, mode: str) -> list[str]:
    from format_contracts import STORY_TREATMENTS
    if mode not in STORY_TREATMENTS:
        raise ValueError('invalid Story mode')
    matches = list(re.finditer(r'(?m)^(FRAME (\d+)|INTERACTION)[ \t]*:[ \t]*(.*)$', text))
    frames = [m for m in matches if m.group(2)]
    issues = _common(text, key, max(1, len(frames)))
    labels = re.findall(r'(?m)^([A-Z][A-Z ]*(?: \d+)?)[ \t]*:', text)
    if matches and text[:matches[0].start()].strip():
        issues.append('unexpected content before Story frames')
    expected = [f'FRAME {i}' for i in range(1, len(frames) + 1)] + ['INTERACTION']
    if not 2 <= len(frames) <= 8 or labels != expected:
        issues.append('Story sequence requires 2-8 consecutive FRAME N: sections then INTERACTION:')
    for i, match in enumerate(matches):
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        body = (match.group(3) + text[match.end():end]).strip()
        if not body or (match.group(2) and len(body.split()) > 140):
            issues.append('Story frame/interaction empty or frame too dense')
    return issues


def check(fmt: str, text: str, *, story_mode: str = 'moment', story_intent: str = 'auto') -> list[str]:
    """Deterministic checks for the selected profile, returning actionable issues."""
    key = LEGACY_FORMATS.get(fmt, fmt)
    get_profile(key)  # reject unknown keys, never silently use a generic format
    if story_intent not in ('auto', *STORY_STYLES) or (story_intent != 'auto' and (not is_story(key) or story_mode != 'moment')):
        raise ValueError('invalid short Story intent')
    if story_mode != 'moment':
        if key not in ('instagram_story', 'tiktok_story'):
            raise ValueError('Story mode requires Story format')
        return _story_sequence(key, text, story_mode)
    issues = _common(text, key)
    required = ('STORY',) if story_intent != 'auto' else FIELDS.get(key, ())
    if is_story(key):
        spoken = '\n'.join(_field(text, name) for name in ('STORY', 'INTERACTION')).strip()
        if len(spoken.split()) > 75 or len(spoken) > 800:
            issues.append('short Story exceeds the 30-second editorial ceiling (75 words / 800 characters)')
        triad = all(marker in text for marker in ('📊', '🔥', '💡'))
        plain = re.sub(r'[*_`]', '', text)
        labelled = re.findall(r'(?m)^\s*(?:[📊🔥💡]\s*)?(?:أول شي|اول شي|ثاني شي|بس انتبه)\s*:', plain)
        numbered = re.findall(r'(?m)^\s*([1-3١-٣])[.)]\s+\S', plain)
        if triad or len(labelled) >= 3 or (len(numbered) >= 3 and story_intent != 'ask_audience'):
            issues.append('retired three-point lesson is not a short Story')
        if story_intent == 'ask_audience' and not re.search(r'[؟?]', _field(text, 'STORY')):
            issues.append('audience-question Story requires a genuine question')
    labels = re.findall(r"(?m)^([A-Z][A-Z ]*(?: \d+)?)\s*:", text)
    if len(labels) != len(set(labels)):
        issues.append("duplicate native section")
    if key not in ("instagram_carousel", "tiktok_photo_carousel", "linkedin_carousel"):
        if labels != list(required):
            issues.append("native sections must appear once in the required order")
    if key in ("instagram_carousel", "tiktok_photo_carousel", "linkedin_carousel"):
        return issues + _carousel(text, key)
    for name in required:
        if not _field(text, name):
            issues.append(f"{key}: missing or empty {name}:")
    if key in ("instagram_story", "tiktok_story") and story_intent == "auto" and not re.search(r"[؟?]", _field(text, "INTERACTION")):
        issues.append(f"{key}: INTERACTION should include a question")
    if key == "linkedin_article":
        headings = list(HEADING.finditer(text))
        if len(headings) < 2:
            issues.append("linkedin_article: include at least two ## section headings")
        summary = re.search(r"(?m)^SUMMARY\s*:", text)
        conclusion = re.search(r"(?m)^CONCLUSION\s*:", text)
        if headings and summary and conclusion and not (
                summary.start() < headings[0].start() < headings[-1].start() < conclusion.start()):
            issues.append("linkedin_article: analysis sections must follow SUMMARY and precede CONCLUSION")
    if key in ("instagram_reel", "tiktok_video") and len(_field(text, "HOOK").split()) > 30:
        issues.append(f"{key}: hook too long (editorial target <=30 words)")
    return issues

def split_owner_note(text: str) -> tuple[str, str]:
    m = OWNER_NOTE.search(text)
    return (text[:m.start()].strip(), text[m.end():].strip()) if m else (text.strip(), "")

@dataclass
class Checked:
    text: str
    provider: str
    refused: bool = False
    failures: list[str] = field(default_factory=list)
    attempts: int = 1
    owner_note: str = ""
    calls: list[Result] = field(default_factory=list)
    status: str = "needs_review"
    review_history: list[dict] = field(default_factory=list)
    planning: dict = field(default_factory=dict)
    clarification: str = ""
    story_mode: str = "moment"
    story_intent: str = "auto"
    production_plan: dict = field(default_factory=dict)

async def generate_checked(fmt: str, system: str, topic: str,
                           angle: str = "", notes: str = "") -> Checked:
    # Compatibility entry point; the same bounded engine is used by CLI and Telegram.
    from dataclasses import replace
    from revision import Settings, execute
    settings = replace(Settings.from_env(), analyst=False)
    checked, _, _ = await execute(fmt, system, topic, angle, settings, analyst_notes=notes)
    return checked


def render_story_copy(text: str) -> str:
    """Remove transport labels after validation; the audience gets only spoken copy."""
    story, interaction = _field(text, 'STORY'), _field(text, 'INTERACTION')
    if not interaction or story.endswith(interaction):
        return story
    return story + '\n\n' + interaction
