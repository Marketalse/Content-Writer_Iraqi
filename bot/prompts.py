"""Builds the stable system prompt from the repo's knowledge base.

The system prompt is identical on every request for a given format, so the API
caches it (see cache_control in bot.py). Keep it byte-stable: no timestamps or
per-user data in it. Files are read once at import time.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "knowledge"
EXAMPLE_LIMIT = 30000  # chars of creator examples (transcripts + posts) per request

FORMATS = {
    "story": ("📱 ستوري ٣٠ ثانية", ROOT / "formats" / "stories" / "guide.md", "story_30s.yaml"),
    "carousel": ("🖼️ كاروسيل", ROOT / "formats" / "carousels" / "guide.md", "post.yaml"),
    "reel": ("🎥 ريل ٦٠+ ثانية", ROOT / "formats" / "reels" / "guide.md", "reel_60s.yaml"),
    "linkedin": ("💼 لينكدإن", ROOT / "formats" / "linkedin" / "guide.md", "linkedin_post.yaml"),
}

FORMULAS = ROOT / "knowledge" / "formulas" / "formulas.md"

# Short labels for the Telegram buttons (the model reads the full descriptions in ANGLES).
ANGLE_BUTTONS = {
    "myth": "🙅 خرافة ✅ حقيقة",
    "tip": "💡 نصيحة سريعة",
    "behind": "🎥 من الكواليس",
    "pain": "😓 مشكلة زبون",
    "offer": "🎁 عرض أو دعوة",
    "flip": "🔄 غلطة وتصحيح",
}

ANGLES = {
    "myth": "Myth-busting: a belief, then the truth",
    "tip": "Quick tip: one thing to do today",
    "behind": "Behind the scenes: honest, unpolished",
    "pain": "Customer pain: told without names",
    "offer": "Offer or ask: a reason to act now",
    "flip": "Problem flip: the reader's wrong belief, then the right one",
}

# Every format replies in the emoji text layout (knowledge/formats/caption.yaml).
OUTPUT_SPEC = {fmt: "caption.yaml" for fmt in ("story", "reel", "carousel", "linkedin")}

BASE_INSTRUCTIONS = """أنت كاتب محتوى محترف متخصص باللهجة العراقية (البغدادية المفهومة بكل العراق).
تكتب حصراً باللهجة العراقية. استخدم گ و چ بشكل طبيعي (مثل: گدر، أگلكم، چيبس، أحچي) كما في أسلوب صاحب الحساب.
تلتزم بقواعد الفورمة المطلوبة من حيث الطول والهيكل والنبرة والإخراج.
استخدم كلمات قاموس العراقي بدل الفصحى كلما توفر مقابل، وتجنب كلمات اللهجات الأخرى.
تجنب العبارات المكتوبة بأسلوب الذكاء الاصطناعي أو المقالات الرسمية (انظر القائمة).
لا تكتب مقدمات مثل "أكيد، هذا المحتوى" — ابدأ بالمحتوى مباشرة.
إذا المعلومات ناقصة (مثلاً السعر أو اسم البراند)، اكتب مكانها {{...}} عشان المستخدم يعبّيها.
لا تخترع أرقام أو إحصائيات أو ادعاءات طبية/مالية.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _examples() -> str:
    """Creator's own transcripts and published posts, used as style examples."""
    parts = []
    for folder in (KB / "examples" / "transcripts", KB / "examples" / "posts"):
        if not folder.exists():
            continue
        for f in sorted(folder.glob("*")):
            if f.name == "README.md" or f.suffix not in {".md", ".txt"}:
                continue
            parts.append(f"--- {f.name} ---\n{_read(f).strip()}")
    return "\n\n".join(parts)[:EXAMPLE_LIMIT]


def build_system_prompt(fmt: str) -> str:
    if fmt not in FORMATS:
        raise ValueError(f"unknown format: {fmt}")
    _, guide_path, spec_name = FORMATS[fmt]

    sections = [
        BASE_INSTRUCTIONS,
        "# صوتي وأسلوبي (voice.md)\n\n" + _read(KB / "voice" / "voice.md"),
        "# دليل اللهجة العراقية\n\n" + _read(ROOT / "guidelines" / "iraqi_dialect_style_guide.md"),
        "# الصيغ (formulas)\n\n" + _read(FORMULAS),
        "# قاموس العراقي (المصدر الأساسي)\n\n" + _read(KB / "dialect" / "iraqi_words.csv"),
        "# لهجات ممنوعة\n\n" + _read(KB / "dialect" / "other_dialects.yaml"),
        "# عبارات ممنوعة (أسلوب AI)\n\n" + _read(KB / "copywriting" / "ai_phrases_ar.yaml"),
        "# صيغ الهوك\n\n" + _read(KB / "hooks" / "hooks_ar.yaml"),
        "# مستويات العمق\n\n" + _read(KB / "formats" / "levels.yaml"),
        "# مواصفات الفورمة (ملف الكود)\n\n" + _read(KB / "formats" / spec_name),
        "# قواعد الفورمة\n\n" + _read(guide_path),
        "# شكل الرد النهائي (إلزامي، يلغي أي شكل آخر أعلاه)\n\n" + _read(KB / "formats" / OUTPUT_SPEC[fmt]),
    ]
    examples = _examples()
    if examples:
        sections.append("# أمثلة من كلامي الحقيقي (فيديوهات ومنشورات)\n\n" + examples)
    return "\n\n".join(s for s in sections if s.strip())
