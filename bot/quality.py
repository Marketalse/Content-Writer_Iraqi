"""Quality gate for generated content.

Every format replies with a labelled caption: Hook, Content (intro + 3 numbered
points), CTA. check(fmt, text) returns a list of failures (empty = passes).
generate_checked() retries once with the failures listed, then returns the draft
with the failures for the owner to review.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from llm import generate

ROOT = Path(__file__).resolve().parent.parent
PHRASES_FILE = ROOT / "knowledge" / "copywriting" / "ai_phrases_ar.yaml"
MAX_ATTEMPTS = 2

GREETINGS = ["هلا بيكم", "هلا والله", "مرحبا", "السلام عليكم", "أهلاً", "اهلا"]
DIACRITICS = re.compile(r"[ً-ْـ]")
KEYCAP = re.compile(r"([0-9])️?⃣")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
SECTION = re.compile(r"^\s*(Hook|Content|CTA)\s*:", re.MULTILINE | re.IGNORECASE)
NUMBERED = re.compile(r"^\s*[1-3١-٣][.)]\s+\S", re.MULTILINE)
OWNER_NOTE = re.compile(r"\*{0,2}NOTE FOR OWNER:?\*{0,2}", re.IGNORECASE)
HASHTAG_LIMITS = {"story": 0, "linkedin": 0, "reel": 5, "carousel": 5}


def _norm(s: str) -> str:
    s = DIACRITICS.sub("", s)
    return s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")


def _banned_phrases() -> list[str]:
    if not PHRASES_FILE.exists():
        return []
    text = PHRASES_FILE.read_text(encoding="utf-8")
    return [m.group(1).strip() for m in re.finditer(r"\{phrase:\s*(.+?),\s*fix:", text)]


def _words(s: str) -> int:
    return len(s.split())


def _fields(text: str, label: str) -> list[str]:
    """Values of 'LABEL: value' fields. A line may hold several fields split by ' | '."""
    out = []
    for line in text.splitlines():
        for part in line.split("|"):
            part = re.sub(r"\[[^\]]*\]", " ", part).replace("*", " ").strip()
            if part.upper().startswith(label + ":"):
                out.append(part[len(label) + 1:].strip().strip("*").strip())
    return out


def _hashtags(text: str) -> list[str]:
    return re.findall(r"#\S+", text)


def _invented_numbers(text: str) -> list[str]:
    t = text.translate(ARABIC_DIGITS)
    t = re.sub(r"\{\{.*?\}\}", " ", t)          # placeholders are allowed
    t = re.sub(r"\[[^\]]*\]", " ", t)            # timing labels like [8-14s]
    t = KEYCAP.sub(" ", t)                      # 1️⃣ markers
    t = re.sub(r"(?m)^\s*\d+[.)]\s", " ", t)    # 1. list markers
    bad = []
    for m in re.finditer(r"(\d+)\s*(%|٪|ألف|مليون|دينار|د\.ع|\$)?", t):
        n = int(m.group(1))
        if m.group(2) or n > 10:
            bad.append(m.group(0).strip())
    return bad


def _common(text: str) -> list[str]:
    fails = []
    norm = _norm(text)
    for g in GREETINGS:
        if _norm(g) in norm:
            fails.append(f"greeting found: '{g}' (no greetings allowed)")
    for p in _banned_phrases():
        if _norm(p) and _norm(p) in norm:
            fails.append(f"AI-sounding phrase found: '{p}' (rewrite it)")
    nums = _invented_numbers(text)
    if nums:
        fails.append(f"numbers that must be {{{{placeholders}}}} instead: {', '.join(nums)}")
    return fails


def _label(raw: str) -> str:
    return "CTA" if raw.upper() == "CTA" else raw.capitalize()


def _sections(text: str) -> dict[str, list[str]]:
    """Map each label (Hook, Content, CTA) to the text after it, up to the next label."""
    found = list(SECTION.finditer(text))
    out: dict[str, list[str]] = {}
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        out.setdefault(_label(m.group(1)), []).append(text[m.end():end].strip())
    return out


def _caption(text: str) -> list[str]:
    fails = []
    order = [_label(m.group(1)) for m in SECTION.finditer(text)]
    if order != ["Hook", "Content", "CTA"]:
        return [f"the reply must have the labels Hook:, Content:, CTA: in that order (found {order or 'none'})"]
    secs = _sections(text)
    hook, content, cta = secs["Hook"][0], secs["Content"][0], secs["CTA"][0]
    if _words(hook) > 15:
        fails.append(f"Hook has {_words(hook)} words, must be 15 or fewer")
    points = NUMBERED.findall(content)
    if len(points) != 3:
        fails.append(f"Content has {len(points)} numbered points, must be exactly 3 (1. 2. 3.)")
    if _words(cta) > 25:
        fails.append(f"CTA has {_words(cta)} words, must be 25 or fewer")
    total = _words(text.split("NOTE FOR OWNER")[0])
    if not 40 <= total <= 160:
        fails.append(f"caption has {total} words, must be 40 to 160")
    return fails


TIMED_LABEL = re.compile(r"\[\s*\d+\s*-\s*\d+\s*s\s*\]\s*\**\s*(HOOK|CONTENT|CTA)\b", re.IGNORECASE)
SCRIPT_POINT = re.compile(r"^[1-3١-٣][.)]\s")


def _timed(text: str) -> list[str]:
    """Story and reel: HOOK, CONTENT lines with 3 numbered points, CTA last, timed."""
    fails = []
    labels = [m.group(1).upper() for m in TIMED_LABEL.finditer(text)]
    if not labels:
        return ["script lines must start with [0-3s] HOOK, CONTENT lines, then CTA"]
    if labels[0] != "HOOK" or labels[-1] != "CTA" or labels.count("HOOK") != 1 or labels.count("CTA") != 1:
        fails.append(f"block order must be HOOK, CONTENT, CTA (found {labels})")
    spoken = [s for s in _fields(text, "SPOKEN") if s]
    points = [s for s in spoken if SCRIPT_POINT.match(s)]
    if len(points) != 3:
        fails.append(f"CONTENT has {len(points)} numbered points, must be exactly 3 (1. 2. 3.)")
    if spoken and SCRIPT_POINT.match(spoken[-1]):
        fails.append("the last SPOKEN line must be the CTA, not a numbered point")
    if spoken and _words(spoken[0]) > 7:
        fails.append(f"HOOK has {_words(spoken[0])} spoken words, must be 7 or fewer")
    total = sum(_words(s) for s in spoken)
    if total > 75:
        fails.append(f"spoken words total {total}, must be 75 or fewer")
    for on in _fields(text, "ON SCREEN"):
        if _words(on) > 6:
            fails.append(f"on-screen card '{on[:40]}' has {_words(on)} words, max 6")
    return fails


def check(fmt: str, text: str) -> list[str]:
    if fmt in ("story", "reel"):
        fails = _common(text) + _timed(text)
        if fmt == "story" and not _fields(text, "STICKER"):
            fails.append("story needs one STICKER in the CTA line")
    else:
        fails = _common(text) + _caption(text)
    limit = HASHTAG_LIMITS.get(fmt, 5)
    tags = _hashtags(text)
    if len(tags) > limit:
        fails.append(f"{len(tags)} hashtags, max {limit} for {fmt}")
    return fails


def split_owner_note(text: str) -> tuple[str, str]:
    """Separate the publishable caption from the NOTE FOR OWNER block (never published)."""
    m = OWNER_NOTE.search(text)
    if not m:
        return text.strip(), ""
    return text[: m.start()].strip(), text[m.end():].strip()


@dataclass
class Checked:
    text: str            # publishable caption only
    provider: str
    refused: bool = False
    failures: list[str] = field(default_factory=list)
    attempts: int = 1
    owner_note: str = ""  # for the owner only; never publish


async def generate_checked(fmt: str, system: str, topic: str) -> Checked:
    base = f"الموضوع: {topic}"
    prompt = base
    result = None
    failures: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = await generate(system, prompt)
        if result.refused or not result.text:
            return Checked(result.text, result.provider, result.refused, [], attempt)
        content, note = split_owner_note(result.text)
        failures = check(fmt, content)
        if not failures:
            return Checked(content, result.provider, False, [], attempt, note)
        prompt = (
            base
            + "\n\nالنسخة السابقة فيها هذي المشاكل، صححها وأعد كتابة الرد كامل بنفس الشكل (Hook / Content / CTA):\n- "
            + "\n- ".join(failures)
        )
    content, note = split_owner_note(result.text)
    return Checked(content, result.provider, False, failures, MAX_ATTEMPTS, note)
