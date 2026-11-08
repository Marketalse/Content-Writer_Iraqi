"""Builds the stable system prompt from the repo's knowledge base.

The system prompt is identical on every request for a given format, so the API
caches it (see cache_control in bot.py). Keep it byte-stable: no timestamps or
per-user data in it. Files are read once at import time.
"""

from pathlib import Path

from platform_intelligence import strategy_prompt, LEGACY_FORMATS

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "knowledge"
EXAMPLE_LIMIT = 30000  # chars of creator examples (transcripts + posts) per request

# Each Telegram choice maps to a distinct native content profile.
# Keep old IDs for saved conversations; new choices use explicit platform IDs.
FORMATS = {
    "story": ("📸 Instagram Story", None, None),
    "reel": ("🎬 Instagram Reel", None, None),
    "carousel": ("🗂 Instagram Carousel", None, None),
    "linkedin": ("💼 LinkedIn Post", None, None),
    "instagram_post": ("🖼 Instagram Post", None, None),
    "instagram_instants": ("⚡ Instagram Instants", None, None),
    "instagram_live": ("🔴 Instagram Live", None, None),
    "instagram_broadcast_channel": ("📣 Instagram Broadcast", None, None),
    "linkedin_article": ("📄 LinkedIn Article", None, None),
    "tiktok_story": ("📱 TikTok Story", None, None),
    "tiktok_video": ("🎥 TikTok Video", None, None),
    "tiktok_photo_carousel": ("🖼 TikTok Photo Carousel", None, None),
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

# A format has its own explicit output layout; no universal caption.yaml.
NATIVE_OUTPUTS = {
    "instagram_story": "STORY: short, human first-person moment or explanation\\nINTERACTION: one question usable with a Story sticker",
    "instagram_reel": "HOOK: spoken opening\\nSCRIPT: complete natural spoken video\\nVISUALS: editing, on-screen highlights or demonstration cues\\nCTA: one natural ask",
    "instagram_post": "HEADLINE: one visual claim\\nCAPTION: complete feed caption with substance\\nCTA: one appropriate ask",
    "instagram_carousel": "SLIDE 1: compelling cover\\nSLIDE 2: context\\nSLIDE 3: first insight\\nSLIDE 4: explanation\\nSLIDE 5: example\\nSLIDE 6: conclusion\\nCAPTION: accompanying post caption\\nCTA: one ask",
    "instagram_instants": "CAPTION: a single short spontaneous caption; do not invent visual assets or claim API publishing",
    "instagram_live": "OPENING: host opening\\nTALKING POINTS: practical outline with several points\\nAUDIENCE QUESTIONS: at least three prompts\\nCLOSING: summary and one next action",
    "instagram_broadcast_channel": "UPDATE: direct personal message with useful substance\\nPROMPT: one question, poll or reaction request",
    "linkedin_post": "INSIGHT: one professional observation\\nBODY: relevant experience, reasoning and practical lesson in clear paragraphs\\nDISCUSSION: one meaningful professional question",
    "linkedin_article": "TITLE: specific title\\nSUMMARY: executive summary\\n## Problem\\n## Analysis\\n## Practical framework\\nCONCLUSION: actionable synthesis",
    "tiktok_story": "STORY: one casual moment or quick point\\nINTERACTION: a reply question",
    "tiktok_video": "HOOK: fast spoken or visual opening\\nSCRIPT: natural and entertaining complete explanation\\nVISUALS: shot directions, demonstration and text cues\\nCTA: natural participation prompt",
    "tiktok_photo_carousel": "SLIDE 1: curiosity cover\\nSLIDE 2: relatable problem\\nSLIDE 3: insight\\nSLIDE 4: example\\nSLIDE 5: payoff\\nCAPTION: short contextual description\\nCTA: one action",
}

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
    profile_key = LEGACY_FORMATS.get(fmt, fmt)

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
        strategy_prompt(profile_key),
        "# Required platform-specific output structure (editorial template, not official ranking rule)\n\n" + NATIVE_OUTPUTS[profile_key],
        "Follow ONLY the native output structure above; ignore older example layouts that demand three generic blocks.",
    ]
    examples = _examples()
    if examples:
        sections.append("# أمثلة من كلامي الحقيقي (فيديوهات ومنشورات)\n\n" + examples)
    return "\n\n".join(s for s in sections if s.strip())
