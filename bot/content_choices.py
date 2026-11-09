"""Deterministic menus and editorial narratives, not platform ranking recipes.

IDs are scoped by format. Legacy Telegram format IDs remain valid.
No model call is needed to present or validate a choice.
"""
from dataclasses import dataclass
from platform_intelligence import LEGACY_FORMATS, PROFILES

FAMILIES = {
    'story': ('📸 Story · ٣٠ ثانية', ('story', 'tiktok_story')),
    'carousel': ('🗂 Carousel', ('carousel', 'tiktok_photo_carousel', 'linkedin_carousel')),
    'video': ('🎬 Reel / فيديو قصير', ('reel', 'tiktok_video')),
    'linkedin': ('💼 LinkedIn · بوست أو مقال', ('linkedin', 'linkedin_article')),
    'more': ('➕ فورمات إضافية', ('instagram_post', 'instagram_instants', 'instagram_live', 'instagram_broadcast_channel')),
}


@dataclass(frozen=True)
class Structure:
    id: str
    label: str
    instruction: str


def options(*rows: tuple[str, str, str]) -> tuple[Structure, ...]:
    return tuple(Structure(*row) for row in rows)


STRUCTURES = {
    'instagram_story': options(
        ('insight', '💡 ملاحظة → معناها → خلاصة', 'One immediate observation, why it matters, one concise takeaway.'),
        ('moment', '🎭 موقف → مفاجأة → إدراك', 'A supplied everyday situation, a small tension or surprise, a realization; never invent personal events.'),
        ('question', '❓ سياق → سؤال → خيارات', 'Brief context, one specific audience question, optional simple reply/poll choices.')),
    'tiktok_story': options(
        ('checkin', '📱 لحظة → رد فعل', 'An immediate supplied moment and an informal reaction; keep it spontaneous.'),
        ('exchange', '💬 سؤال → جواب → رجعة للجمهور', 'A supplied question, a direct short answer, and only if suitable a brief return question.'),
        ('participate', '🙋 موقف → دعوة للمشاركة', 'A relatable situation and a low-effort participation prompt; no invented trend or challenge.')),
    'instagram_reel': options(
        ('demo', '🎬 نتيجة → توضيح → تفصيل', 'Show a supported result or clearly hypothetical target, demonstrate the process, highlight a useful detail.'),
        ('reversal', '🔄 اعتقاد → مثال معاكس → تفسير', 'A recognizable assumption, a supported counterexample, explanation and implication.'),
        ('story', '🎭 موقف → عقبة → قرار → نتيجة', 'A supplied situation, obstacle, decision, supported outcome and lesson.')),
    'tiktok_video': options(
        ('pov', '🎭 موقف مألوف → تصاعد → قفلة', 'A relatable POV situation, escalation and entertaining payoff; label fictional scenarios as hypothetical.'),
        ('answer', '💬 سؤال → جواب → عرض', 'A supplied real question/comment, direct answer, visible demonstration and takeaway; never invent a quoted comment.'),
        ('test', '🧪 سؤال → تجربة → ملاحظة → حكم', 'A question, supplied test/process, supported observed outcome and qualified verdict; propose a test if no results exist.')),
    'instagram_carousel': options(
        ('guide', '📚 فكرة → شرح → مثال → خلاصة', 'A clear cover promise, progressive explanation, worked example and recap.'),
        ('compare', '⚖️ قرار → معايير → مقارنة → توجيه', 'A decision question, relevant criteria, alternatives, trade-offs and qualified guidance.'),
        ('case', '🔎 حالة → تحدي → اختيارات → درس', 'A supplied case, challenge, choices, supported outcome and lesson; do not invent case evidence.')),
    'tiktok_photo_carousel': options(
        ('reveal', '👀 فضول → تطور بصري → كشف', 'A curiosity cover, unfolding visual sequence and a clear supported reveal.'),
        ('collection', '🎭 موقف مشترك → لقطات → معنى', 'A relatable theme, varied image moments and a connecting payoff; no fixed number of tips.'),
        ('details', '🔍 سؤال → تفاصيل → فروقات → استنتاج', 'A visual question, inspectable details, meaningful differences and a grounded conclusion.')),
    'linkedin_carousel': options(
        ('playbook', '📚 مشكلة مهنية → طريقة → تطبيق', 'A professional problem, a usable method, worked application and practical synthesis across document pages.'),
        ('decision', '⚖️ قرار → معايير → مفاضلات', 'A professional decision, evaluation criteria, trade-offs and justified guidance across document pages.'),
        ('case', '🔎 سياق → قرارات → دليل → دروس', 'A supplied business case, decisions, supported evidence and transferable lessons; never invent clients or results.')),
    'linkedin_post': options(
        ('lesson', '💼 تجربة موثقة → إدراك → درس', 'A supplied professional experience or explicitly hypothetical situation, realization, practical lesson and meaningful discussion.'),
        ('viewpoint', '📊 رأي → دليل → دلالة', 'A clear viewpoint, supplied supporting evidence, limitations and professional implication.'),
        ('distinction', '⚖️ خلط شائع → فرق → تطبيق', 'A common confusion, precise distinction and practical application; no mandatory numbered list.')),
    'linkedin_article': options(
        ('analysis', '🔎 سؤال → حجة → دليل → توصيات', 'A substantial analytical question, argument, supported evidence, counterarguments and recommendations.'),
        ('guide', '📚 هدف → طريقة → أمثلة → حدود', 'A professional goal, practical method, worked examples, limitations and implementation guidance.'),
        ('case', '💼 سياق → مشكلة → قرارات → دروس', 'A detailed supplied case, problem, decisions, supported outcomes, limitations and lessons.')),
    'instagram_post': options(
        ('visual', '🖼 صورة → معنى → خلاصة', 'A visual-led insight whose caption adds meaning and one takeaway.'),
        ('opinion', '💬 موقف → سبب → دلالة', 'A clear point of view, reasoning and practical implication.'),
        ('product', '🛍 ميزة → فائدة → استخدام', 'A supplied product feature, relevant benefit and specific use case without unsupported promises.')),
    'instagram_instants': options(
        ('moment', '⚡ وصف اللحظة', 'A minimal caption describing only the supplied moment.'),
        ('reaction', '🙂 إحساس أو رد فعل', 'One spontaneous reaction appropriate to the supplied moment.'),
        ('shared', '🤝 سياق مشترك', 'A short shared-context caption based only on supplied context. No funnel or CTA.')),
    'instagram_live': options(
        ('clinic', '💬 أسئلة → نقاش → خلاصة', 'An audience clinic with a useful opening, flexible questions, follow-ups and recap.'),
        ('workshop', '🛠 هدف → تطبيق مباشر → أسئلة', 'A live workshop: goal, demonstration, audience checks and practical recap.'),
        ('guest', '🎙 تقديم → حوار → أسئلة الجمهور', 'A guest conversation with supplied guest details, open questions, follow-ups and audience questions.')),
    'instagram_broadcast_channel': options(
        ('update', '📣 تحديث → أهميته → رد', 'A supplied insider update, why it matters and one relevant reaction invitation.'),
        ('decision', '🗳 سياق → اختيارات → تصويت', 'A real community decision, meaningful alternatives and a poll/reply invitation; never invent results.'),
        ('resource', '🎁 قيمة → تطبيق → مورد', 'Useful exclusive guidance, practical application and a supplied real resource if available; never invent links.')),
}
assert STRUCTURES.keys() == PROFILES.keys()
assert all(len(rows) == 3 and len({row.id for row in rows}) == 3 for rows in STRUCTURES.values())


def structure_options(fmt: str) -> tuple[Structure, ...]:
    try:
        return STRUCTURES[LEGACY_FORMATS.get(fmt, fmt)]
    except KeyError as exc:
        raise ValueError('unknown format for narrative structure') from exc


def get_structure(fmt: str, structure_id: str) -> Structure:
    for item in structure_options(fmt):
        if item.id == structure_id:
            return item
    raise ValueError('structure does not belong to this format')


def structure_prompt(fmt: str, structure_id: str = '') -> str:
    if not structure_id:
        return ''
    selected = get_structure(fmt, structure_id)
    return ('# User-selected narrative structure (editorial choice, not algorithm rule)\n'
            + selected.instruction
            + '\nUse this progression inside the native output sections. It takes precedence over default '
              'storytelling order, optional planning frameworks, examples and conflicting angle suggestions. '
              'Preserve the chosen Story intent, brevity, facts, safety and native section contract. '
              'Do not print framework names or turn stages into three numbered tips. '
              'Assess and preserve this selection during review and revision.')
