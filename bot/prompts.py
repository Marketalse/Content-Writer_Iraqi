"""Builds the stable system prompt from the repo's knowledge base.

The system prompt is identical on every request for a given format, so the API
caches it (see cache_control in bot.py). Keep it byte-stable: no timestamps or
per-user data in it. Files are read once at import time.
"""

from pathlib import Path

from platform_intelligence import strategy_prompt, LEGACY_FORMATS, PROFILES
from format_contracts import NATIVE_OUTPUTS, format_contract
from source_knowledge import lesson_prompt
from briefs import Brief
from editorial import approved_examples
from content_choices import structure_prompt
from story_styles import STORY_STYLES, STORY_ANGLE_KEYS, is_story

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "knowledge"
EXAMPLE_LIMIT = 30000  # chars of creator examples (transcripts + posts) per request

# Each Telegram choice maps to a distinct native content profile.
# Keep old IDs for saved conversations; new choices use explicit platform IDs.
FORMATS = {
    "story": ("📸 Instagram Story · ٣٠ ثانية", None, None),
    "reel": ("🎬 Instagram Reel", None, None),
    "carousel": ("🗂 Instagram Carousel", None, None),
    "linkedin": ("💼 LinkedIn Post", None, None),
    "instagram_post": ("🖼 Instagram Post", None, None),
    "instagram_instants": ("⚡ Instagram Instants", None, None),
    "instagram_live": ("🔴 Instagram Live", None, None),
    "instagram_broadcast_channel": ("📣 Instagram Broadcast", None, None),
    "linkedin_carousel": ("📑 LinkedIn Carousel · مستند", None, None),
    "linkedin_article": ("📄 LinkedIn Article", None, None),
    "tiktok_story": ("📱 TikTok Story · ٣٠ ثانية", None, None),
    "tiktok_video": ("🎥 TikTok Video", None, None),
    "tiktok_photo_carousel": ("🖼 TikTok Photo Carousel", None, None),
}

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

def angle_options(fmt: str | None = None) -> dict[str, str]:
    if is_story(fmt):
        return {key: STORY_STYLES[intent]['label'] for key, intent in STORY_ANGLE_KEYS.items()}
    return ANGLE_BUTTONS


def angle_description(fmt: str, key: str) -> str:
    if is_story(fmt) and key in STORY_ANGLE_KEYS:
        return STORY_STYLES[STORY_ANGLE_KEYS[key]]['instruction']
    return ANGLES[key]  # Keep legacy callbacks/conversations working.


BASE_INSTRUCTIONS = """أنت كاتب محتوى محترف متخصص باللهجة العراقية (البغدادية المفهومة بكل العراق).
تكتب حصراً باللهجة العراقية. استخدم گ و چ بشكل طبيعي (مثل: گدر، أگلكم، چيبس، أحچي) كما في أسلوب صاحب الحساب.
تلتزم بقواعد الفورمة المطلوبة من حيث الطول والهيكل والنبرة والإخراج.
استخدم كلمات قاموس العراقي بدل الفصحى كلما توفر مقابل، وتجنب كلمات اللهجات الأخرى.
تجنب العبارات المكتوبة بأسلوب الذكاء الاصطناعي أو المقالات الرسمية (انظر القائمة).
لا تكتب مقدمات مثل "أكيد، هذا المحتوى" — ابدأ بالمحتوى مباشرة.
إذا المعلومات ناقصة (مثلاً السعر أو اسم البراند)، اكتب مكانها {{...}} عشان المستخدم يعبّيها.
لا تخترع أرقام أو إحصائيات أو ادعاءات طبية/مالية.
إذا صيغة الموضوع توحي بضمان نتيجة مثل البيع بدون أي خسارة، قدّمها كتقليل للمخاطر؛ لا توعد بنتيجة مضمونة.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _examples(fmt: str, story_mode: str = 'moment', story_intent: str = 'auto') -> str:
    """Creator's own transcripts and published posts, used as style examples."""
    parts = ["Human-approved STYLE example (facts are not evidence for a new brief):\n"
             + row['text'] + "\nHuman review reason: " + row['reason']
             for row in approved_examples(fmt, story_mode, story_intent)]
    key = LEGACY_FORMATS.get(fmt, fmt)
    # Published posts are LinkedIn examples; transcripts belong only to spoken videos.
    # Do not condition Stories, Instants or community messages on long-form layouts.
    folders = {
        "linkedin_post": (KB / "examples" / "posts",),
        "instagram_reel": (KB / "examples" / "transcripts",),
        "tiktok_video": (KB / "examples" / "transcripts",),
    }.get(key, ())
    for folder in folders:
        if not folder.exists():
            continue
        for f in sorted(folder.glob("*")):
            if f.name == "README.md" or f.suffix not in {".md", ".txt"}:
                continue
            parts.append(f"--- {f.name} ---\n{_read(f).strip()}")
    return "\n\n".join(parts)[:EXAMPLE_LIMIT]


def build_system_prompt(fmt: str, *, brief: Brief | None = None) -> str:
    if fmt not in FORMATS and fmt not in PROFILES:
        raise ValueError(f"unknown format: {fmt}")
    brief = brief or Brief()
    brief.validate_format(fmt)
    profile_key = LEGACY_FORMATS.get(fmt, fmt)

    sections = [
        BASE_INSTRUCTIONS,
        "# صوتي وأسلوبي (voice.md)\n\n" + _read(KB / "voice" / "voice.md"),
        "# دليل اللهجة العراقية\n\n" + _read(ROOT / "guidelines" / "iraqi_dialect_style_guide.md"),
        "# قاموس العراقي (المصدر الأساسي)\n\n" + _read(KB / "dialect" / "iraqi_words.csv"),
        "# لهجات ممنوعة\n\n" + _read(KB / "dialect" / "other_dialects.yaml"),
        "# عبارات ممنوعة (أسلوب AI)\n\n" + _read(KB / "copywriting" / "ai_phrases_ar.yaml"),
        "# مستويات العمق\n\n" + _read(KB / "formats" / "levels.yaml"),
        strategy_prompt(profile_key, story_intent=brief.story_intent),
        lesson_prompt(profile_key, brief.distribution),
    ]
    examples = _examples(fmt, brief.story_mode, brief.story_intent)
    if examples:
        sections.append("# أمثلة من كلامي الحقيقي (فيديوهات ومنشورات)\n\n" + examples)
    sections.append(structure_prompt(profile_key, brief.structure_id))
    sections.append(format_contract(profile_key, brief.story_mode, brief.story_intent))
    return "\n\n".join(s for s in sections if s.strip())
