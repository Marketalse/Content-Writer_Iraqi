"""Builds the stable system prompt from the guideline files.

The system prompt is identical on every request, so it is cached by the API
(see cache_control in bot.py). Keep it byte-stable: do not put timestamps or
per-user data in it.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORMATS = {
    "story": ("📱 ستوري", ROOT / "formats" / "stories" / "guide.md"),
    "carousel": ("🖼️ كاروسيل", ROOT / "formats" / "carousels" / "guide.md"),
    "reel": ("🎥 ريل", ROOT / "formats" / "reels" / "guide.md"),
    "linkedin": ("💼 لينكدإن", ROOT / "formats" / "linkedin" / "guide.md"),
}

STYLE_GUIDE = ROOT / "guidelines" / "iraqi_dialect_style_guide.md"

BASE_INSTRUCTIONS = """أنت كاتب محتوى محترف متخصص باللهجة العراقية (البغدادية المفهومة بكل العراق).
تكتب حصراً باللهجة العراقية، بالحروف الصحيحة (گ، چ، پ) حسب الدليل أدناه.
تلتزم بقواعد الفورمة المطلوبة من حيث الطول، الهيكل، النبرة، والإخراج.
لا تكتب مقدمات مثل "أكيد، هذا المحتوى" — ابدأ بالمحتوى مباشرة.
إذا المعلومات ناقصة (مثلاً السعر أو اسم البراند)، اكتب مكانها [بين قوسين] عشان المستخدم يعبّيها.
لا تخترع أرقام أو إحصائيات أو ادعاءات طبية/مالية.
"""


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def build_system_prompt(fmt: str) -> str:
    """System prompt for one format. Each format gets its own cache entry."""
    if fmt not in FORMATS:
        raise ValueError(f"unknown format: {fmt}")
    _, path = FORMATS[fmt]
    return "\n\n".join(
        [
            BASE_INSTRUCTIONS,
            "# دليل اللهجة العراقية\n\n" + load_text(STYLE_GUIDE),
            "# قواعد هذه الفورمة\n\n" + load_text(path),
        ]
    )
