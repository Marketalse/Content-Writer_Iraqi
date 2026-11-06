"""Quality gate for generated content.

Formats:
  story, reel   timed script: [0-3s] HOOK | SPOKEN ... ; CONTENT lines with 1. 2. 3.; CTA last
  carousel, linkedin  labelled caption: Hook:, Content: (intro + 1. 2. 3.), CTA:, then Keywords:
check(fmt, text) returns failures (empty = passes). generate_checked() retries once with the
failures listed and returns the draft with any remaining failures for the owner.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from llm import Result, generate

ROOT = Path(__file__).resolve().parent.parent
PHRASES_FILE = ROOT / "knowledge" / "copywriting" / "ai_phrases_ar.yaml"
MAX_ATTEMPTS = 2

GREETINGS = ["هلا بيكم", "هلا والله", "مرحبا", "السلام عليكم", "أهلاً", "اهلا"]
DIACRITICS = re.compile(r"[ً-ْـ]")
KEYCAP = re.compile(r"([0-9])️?⃣")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
SECTION = re.compile(r"^\s*(Hook|Content|CTA)\s*:", re.MULTILINE | re.IGNORECASE)
KEYWORDS = re.compile(r"^\s*Keywords\s*:\s*(.*)$", re.MULTILINE | re.IGNORECASE)
NUMBERED = re.compile(r"^\s*[1-3١-٣][.)]\s+\S", re.MULTILINE)
SCRIPT_POINT = re.compile(r"^[1-3١-٣][.)]\s")
TIMED_LABEL = re.compile(r"\[\s*\d+\s*-\s*\d+\s*s\s*\]\s*\**\s*(HOOK|CONTENT|CTA)\b", re.IGNORECASE)
OWNER_NOTE = re.compile(r"\*{0,2}NOTE FOR OWNER:?\*{0,2}", re.IGNORECASE)

ASK_VERBS = {"اكتب", "اكتبلي", "دز", "دزلي", "دزه", "تابع", "تابعني", "احفظ", "شارك",
             "ارسل", "اضغط", "سجل", "اطلب", "راسل", "شوف", "جرب", "صوت", "علّق", "علق"}
HOOK_MAX_CHARS = {"carousel": 125, "linkedin": 210}
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


def _hashtags(text: str) -> list[str]:
    return re.findall(r"#\S+", text)


def _fields(text: str, label: str) -> list[str]:
    """Values of 'LABEL: value' fields. A line may hold several fields split by ' | '."""
    out = []
    for line in text.splitlines():
        for part in line.split("|"):
            part = re.sub(r"\[[^\]]*\]", " ", part).replace("*", " ").strip()
            if part.upper().startswith(label + ":"):
                out.append(part[len(label) + 1:].strip().strip("*").strip())
    return out


def _invented_numbers(text: str) -> list[str]:
    t = text.translate(ARABIC_DIGITS)
    t = re.sub(r"\{\{.*?\}\}", " ", t)          # placeholders are allowed
    t = re.sub(r"\[[^\]]*\]", " ", t)           # timing labels like [8-14s]
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
    found = list(SECTION.finditer(text))
    out: dict[str, list[str]] = {}
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        out.setdefault(_label(m.group(1)), []).append(text[m.end():end].strip())
    return out


def split_keywords(text: str) -> tuple[str, str]:
    """Return (caption without the Keywords line, keywords text)."""
    m = None
    for m in KEYWORDS.finditer(text):
        pass
    if m is None:
        return text, ""
    return text[: m.start()].rstrip(), m.group(1).strip()


EMOJI_LAYOUT = ["🎬", "🔥", "🤔", "🎯", "💰", "📩", "🚀", "📊"]


def _layout(main: str) -> list[str]:
    fails = []
    lines = [l.strip() for l in main.splitlines() if l.strip()]
    if len(lines) != len(EMOJI_LAYOUT):
        fails.append(f"the reply must have {len(EMOJI_LAYOUT)} lines with markers "
                     f"{' '.join(EMOJI_LAYOUT)} (found {len(lines)})")
    for i, (line, marker) in enumerate(zip(lines, EMOJI_LAYOUT)):
        if not line.startswith(marker):
            fails.append(f"line {i + 1} must start with {marker}")
    if len(lines) < len(EMOJI_LAYOUT):
        return fails
    limits = [15, 20, 25, 25, 25, 25, 20, 30]
    for i, (line, limit) in enumerate(zip(lines, limits)):
        body = line[len(EMOJI_LAYOUT[i]):].strip()
        if _words(body) > limit:
            fails.append(f"line {i + 1} ({EMOJI_LAYOUT[i]}) has {_words(body)} words, max {limit}")
    cta = lines[6][len("🚀"):].strip()
    words = re.findall(r"[\u0621-\u064Aa-zA-Z]+", cta)
    asks = [w for w in words if w in ASK_VERBS or (w.startswith("و") and w[1:] in ASK_VERBS)]
    if len(asks) > 1:
        fails.append("the 🚀 line has more than one ask; keep exactly one call to action")
    total = _words(main)
    if not 40 <= total <= 160:
        fails.append(f"reply has {total} words, must be 40 to 160")
    return fails


def _readability(text: str) -> list[str]:
    for para in re.split(r"\n\s*\n", text):
        if _words(para) > 60:
            return [f"a paragraph has {_words(para)} words, max 60 (split it with a blank line)"]
    return []


TIMED_LIMIT_NOTE = "spoken total"


def _timed(text: str) -> list[str]:
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
    main, _ = split_keywords(text)
    fails = _common(text) + _layout(main) + _readability(text)
    limit = HASHTAG_LIMITS.get(fmt, 5)
    if len(_hashtags(text)) > limit:
        fails.append(f"{len(_hashtags(text))} hashtags, max {limit} for {fmt}")
    if fmt == "story" and not any(l.strip().startswith("📊") for l in main.splitlines()):
        fails.append("story needs the 📊 line (the poll sticker)")
    return fails


def split_owner_note(text: str) -> tuple[str, str]:
    """Separate the publishable reply from the NOTE FOR OWNER block (never published)."""
    m = OWNER_NOTE.search(text)
    if not m:
        return text.strip(), ""
    return text[: m.start()].strip(), text[m.end():].strip()


@dataclass
class Checked:
    text: str                 # publishable reply only
    provider: str
    refused: bool = False
    failures: list[str] = field(default_factory=list)
    attempts: int = 1
    owner_note: str = ""      # for the owner only; never publish
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
    result = None
    failures: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = await generate(system, prompt)
        calls.append(result)
        if result.refused or not result.text:
            return Checked(result.text, result.provider, result.refused, [], attempt, calls=calls)
        content, note = split_owner_note(result.text)
        failures = check(fmt, content)
        if not failures:
            return Checked(content, result.provider, False, [], attempt, note, calls)
        prompt = (
            base
            + "\n\nالنسخة السابقة فيها هذي المشاكل، صححها وأعد كتابة الرد كامل بنفس الشكل:\n- "
            + "\n- ".join(failures)
        )
    content, note = split_owner_note(result.text)
    return Checked(content, result.provider, False, failures, MAX_ATTEMPTS, note, calls)
