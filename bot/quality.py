"""Format-native structural quality gates for twelve social publishing formats.

These are local editorial checks, not official ranking rules or fact verification.
The checker never treats a creative heuristic as a platform API limit.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from llm import Result, generate
from platform_intelligence import get_profile, LEGACY_FORMATS

ROOT = Path(__file__).resolve().parent.parent
MAX_ATTEMPTS = 2
OWNER_NOTE = re.compile(r"\*{0,2}NOTE FOR OWNER:?\*{0,2}", re.I)
AI_PHRASES = ROOT / "knowledge" / "copywriting" / "ai_phrases_ar.yaml"
SLIDE = re.compile(r"(?im)^SLIDE\s+(\d+)\s*:\s*(.*)$")
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
    "linkedin_article": 0, "tiktok_story": 0,
    "instagram_reel": 5, "instagram_post": 5, "instagram_carousel": 5,
    "tiktok_video": 5, "tiktok_photo_carousel": 5,
}
# Soft editorial bounds; not platform technical limits.
WORD_RANGES = {
    "instagram_story": (4, 140), "instagram_reel": (35, 320),
    "instagram_post": (8, 300), "instagram_carousel": (30, 500),
    "instagram_instants": (1, 35), "instagram_live": (35, 500),
    "instagram_broadcast_channel": (4, 160),
    "linkedin_post": (35, 380), "linkedin_article": (180, 2500),
    "tiktok_story": (4, 140), "tiktok_video": (25, 300),
    "tiktok_photo_carousel": (25, 420),
}

def _field(text: str, name: str) -> str:
    pattern = re.compile(r"(?im)^" + re.escape(name) + r"\s*:\s*(.*)$")
    m = pattern.search(text)
    if not m:
        return ""
    following = re.search(r"(?m)^[A-Z][A-Z ]+\s*:", text[m.end():])
    end = m.end() + following.start() if following else len(text)
    return (m.group(1) + "\n" + text[m.end():end]).strip()

def _common(text: str, key: str) -> list[str]:
    issues = []
    if not text.strip():
        return ["empty output"]
    count = len(text.split())
    lower, upper = WORD_RANGES[key]
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
    for i, match in enumerate(slides):
        stop = slides[i+1].start() if i+1 < len(slides) else len(text)
        section = text[match.start():stop].split("CAPTION:", 1)[0].split("CTA:", 1)[0]
        if len(section.split()) > 70:
            issues.append(f"slide {i+1}: too dense, shorten copy")
    if not _field(text, "CAPTION"):
        issues.append("carousel: missing CAPTION:")
    if not _field(text, "CTA"):
        issues.append("carousel: missing CTA:")
    return issues

def check(fmt: str, text: str) -> list[str]:
    """Deterministic checks for the selected profile, returning actionable issues."""
    key = LEGACY_FORMATS.get(fmt, fmt)
    get_profile(key)  # reject unknown keys, never silently use a generic format
    issues = _common(text, key)
    if key in ("instagram_carousel", "tiktok_photo_carousel"):
        return issues + _carousel(text, key)
    for name in FIELDS[key]:
        if not _field(text, name):
            issues.append(f"{key}: missing or empty {name}:")
    if key in ("instagram_story", "tiktok_story") and not re.search(r"[؟?]", _field(text, "INTERACTION")):
        issues.append(f"{key}: INTERACTION should include a question")
    if key == "linkedin_article" and len(HEADING.findall(text)) < 2:
        issues.append("linkedin_article: include at least two ## section headings")
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

async def generate_checked(fmt: str, system: str, topic: str,
                           angle: str = "", notes: str = "") -> Checked:
    base = f"الموضوع: {topic}"
    if angle:
        base += f"\nالزاوية: {angle}"
    if notes:
        base += f"\nتحليل الجمهور:\n{notes}"
    prompt = base
    calls: list[Result] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = await generate(system, prompt)
        calls.append(result)
        if result.refused or not result.text:
            return Checked(result.text, result.provider, result.refused, [], attempt, calls=calls)
        content, note = split_owner_note(result.text)
        failures = check(fmt, content)
        if not failures:
            return Checked(content, result.provider, False, [], attempt, note, calls)
        prompt = base + "\n\nFix these format-specific quality issues without changing the selected platform format:\n- " + "\n- ".join(failures)
    return Checked(content, result.provider, False, failures, MAX_ATTEMPTS, note, calls)
