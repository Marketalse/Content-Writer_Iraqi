"""Quality gate for generated content.

check(fmt, text) returns a list of failures (empty list = passes).
generate_checked() calls the model, checks the draft, and retries once with
the failures listed, so the model can fix them. If it still fails, the caller
receives the draft plus the failures and must show them to the owner.
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


def _invented_numbers(text: str) -> list[str]:
    t = text.translate(ARABIC_DIGITS)
    t = re.sub(r"\{\{.*?\}\}", " ", t)          # placeholders are allowed
    t = re.sub(r"\[\d+-\d+s\]", " ", t)         # timing labels
    t = KEYCAP.sub(" ", t)                      # 1️⃣ list markers
    t = re.sub(r"(?m)^\s*\d+[.)]\s", " ", t)    # 1. list markers
    bad = []
    for m in re.finditer(r"(\d+)\s*(%|٪|ألف|مليون|دينار|د\.ع|\$)?", t):
        n = int(m.group(1))
        if m.group(2) or n > 10:
            bad.append(m.group(0).strip())
    return bad


def _hashtags(text: str) -> list[str]:
    return re.findall(r"#\S+", text)


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


def _fields(text: str, label: str) -> list[str]:
    """Values of 'LABEL: value' fields. A line may hold several fields split by ' | '."""
    out = []
    for line in text.splitlines():
        for part in line.split("|"):
            part = re.sub(r"\[[^\]]*\]", " ", part).replace("*", " ").strip()
            if part.upper().startswith(label + ":"):
                out.append(part[len(label) + 1:].strip().strip("*").strip())
    return out


def _story(text: str) -> list[str]:
    fails = []
    spoken = [s for s in _fields(text, "SPOKEN") if s]
    if len(spoken) < 4:
        fails.append("story needs SPOKEN lines for each beat (found fewer than 4)")
    total = sum(_words(s) for s in spoken)
    if total > 75:
        fails.append(f"spoken words total {total}, must be 75 or fewer")
    if spoken and _words(spoken[0]) > 7:
        fails.append(f"hook has {_words(spoken[0])} spoken words, must be 7 or fewer")
    for on in _fields(text, "ON SCREEN"):
        if _words(on) > 6:
            fails.append(f"on-screen text '{on[:40]}' has {_words(on)} words, max 6")
    if not _fields(text, "STICKER"):
        fails.append("missing the STICKER field (every story needs one interactive sticker)")
    return fails


def _instagram(text: str) -> list[str]:
    fails = []
    tags = _hashtags(text)
    if len(tags) > 5:
        fails.append(f"{len(tags)} hashtags, max 5")
    first = next((l for l in text.splitlines() if l.strip()), "")
    if len(first) > 125:
        fails.append(f"first line is {len(first)} characters; Instagram cuts it after about 125")
    return fails


def _linkedin(text: str) -> list[str]:
    fails = []
    n = _words(text)
    if not 120 <= n <= 220:
        fails.append(f"caption has {n} words, must be 120 to 220")
    first = next((l for l in text.splitlines() if l.strip()), "")
    if not first.startswith("💡"):
        fails.append("first line must start with 💡 (problem line)")
    positions = [text.find(e) for e in ("🔥", "📌", "🤔")]
    if min(positions) < 0:
        fails.append("missing one of the block markers 🔥 📌 🤔")
    elif positions != sorted(positions):
        fails.append("block markers must come in the order 🔥, 📌, 🤔")
    if any(int(d) >= 4 for d, _ in [(m.group(1), m) for m in KEYCAP.finditer(text)]):
        fails.append("more than 3 levels (only 1️⃣ 2️⃣ 3️⃣ allowed)")
    if _hashtags(text):
        fails.append("LinkedIn captions have no hashtags")
    return fails


def check(fmt: str, text: str) -> list[str]:
    fails = _common(text)
    if fmt == "story":
        fails += _story(text)
    elif fmt == "linkedin":
        fails += _linkedin(text)
    else:  # carousel, reel
        fails += _instagram(text)
    return fails


@dataclass
class Checked:
    text: str
    provider: str
    refused: bool = False
    failures: list[str] = field(default_factory=list)
    attempts: int = 1


async def generate_checked(fmt: str, system: str, topic: str) -> Checked:
    base = f"الموضوع: {topic}"
    prompt = base
    result = None
    failures: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = await generate(system, prompt)
        if result.refused or not result.text:
            return Checked(result.text, result.provider, result.refused, [], attempt)
        failures = check(fmt, result.text)
        if not failures:
            return Checked(result.text, result.provider, False, [], attempt)
        prompt = (
            base
            + "\n\nالنسخة السابقة فيها هذي المشاكل، صححها وأعد كتابة النص كامل بنفس الفورمة:\n- "
            + "\n- ".join(failures)
        )
    return Checked(result.text, result.provider, False, failures, MAX_ATTEMPTS)
