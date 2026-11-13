"""User-approved spreadsheet taxonomy. Platform routing and narrative guidance are distinct."""
from dataclasses import dataclass
from platform_intelligence import LEGACY_FORMATS

FEATURES = {
    'post': ('📝 Post', ('instagram_post', 'carousel', 'linkedin', 'linkedin_carousel', 'tiktok_photo_carousel')),
    'story': ('📸 Story', ('story', 'tiktok_story')),
    'reel': ('🎬 Reel', ('reel', 'tiktok_video')),
    'live': ('🔴 Live Topic', ('instagram_live',)),
}
FLOWS = {
    'hook_value': 'Hook → مشكلة/موقف → قيمة سريعة → CTA',
    'guide': 'عنوان قوي → نقاط واضحة → مثال عراقي → سؤال/CTA',
    'interaction': 'سؤال أو Poll → تفاعل → جواب أو توضيح',
    'insight': 'فكرة واحدة → موقف/دليل → سؤال للنقاش',
    'professional': 'مشكلة أعمال → مثال من السوق → إطار أو رأي مدعوم → سؤال مهني',
    'clinic': 'افتتاحية → أسئلة الجمهور → نقاش → خلاصة',
    'workshop': 'هدف → تطبيق مباشر → أسئلة → خلاصة',
    'guest': 'تقديم الضيف → حوار → أسئلة الجمهور → خلاصة',
}

@dataclass(frozen=True)
class Strategy:
    id: str
    label: str
    flow: str
    instruction: str

CATALOG = {
    'comedy': Strategy('comedy','Comedy / Skit','hook_value','Use a relatable comedic situation or skit; clearly label hypothetical scenes and never invent personal experience.'),
    'guide': Strategy('guide','Framework / Saveable guide','guide','Give an organized reusable framework with an Iraqi worked example.'),
    'howto': Strategy('howto','How-to / Checklist','guide','Provide practical actionable steps or a concise checklist adapted to the available duration.'),
    'problem': Strategy('problem','Problem / Solution','hook_value','Explain a specific problem and a realistic solution without promising guaranteed outcomes.'),
    'engage': Strategy('engage','Q&A / Engagement','interaction','Ask a meaningful question or answer a supplied question; never invent audience responses.'),
    'experiment': Strategy('experiment','Storytelling / Experiment','hook_value','Use a supplied story or experiment; if results are unavailable propose a test or clearly hypothetical scenario.'),
    'why': Strategy('why','Explainer / Why','hook_value','Explain one why or mechanism simply, with evidence for factual claims.'),
    'hot_take': Strategy('hot_take','Hot take','hook_value','Present a clear opinion with reasoning; distinguish opinion from factual claims.'),
    'mistake': Strategy('mistake','Mistake / Correction','guide','Identify a specific mistake and show its correction without unsupported before/after results.'),
    'insight': Strategy('insight','Single insight','insight','Convey one useful insight with only the context needed to understand it.'),
    'b2b': Strategy('b2b','B2B / Leadership insight','professional','Explain a practical leadership or business decision with supported or explicitly hypothetical examples.'),
    'deepdive': Strategy('deepdive','Deep-dive / Framework','professional','Develop a professional framework with concrete application; fit the selected medium and duration.'),
    'quiz': Strategy('quiz','Interactive quiz','interaction','Pose a clear quiz, invite a response and provide an evidence-supported explanation; never invent votes.'),
    'poll': Strategy('poll','Poll / Debate','interaction','Offer meaningful alternatives and a discussion prompt; do not invent poll results.'),
    'professional': Strategy('professional','Professional insight','insight','Present one professional insight, its support and a relevant discussion question.'),
    'clinic': Strategy('clinic','أسئلة الجمهور / Audience Q&A','clinic','Plan audience questions and useful follow-ups; proposed questions are not actual audience quotations.'),
    'workshop': Strategy('workshop','ورشة عملية / Practical workshop','workshop','Plan a feasible live demonstration with audience checks and a practical recap.'),
    'guest': Strategy('guest','حوار مع ضيف / Guest conversation','guest','Plan a guest conversation using supplied guest details or placeholders; do not invent a guest or credentials.'),
}
STRATEGIES = {
    'post': ('comedy','guide','howto','problem','engage','experiment'),
    'story': ('comedy','why','hot_take','howto','mistake','problem','insight','experiment'),
    'reel': ('b2b','deepdive','quiz','poll','professional','engage'),
    'live': ('clinic','workshop','guest'),
}


def get_strategy(feature: str, strategy: str) -> Strategy:
    if strategy not in STRATEGIES.get(feature, ()):
        raise ValueError('strategy does not belong to feature')
    return CATALOG[strategy]


def validate_selection(fmt: str, feature: str, strategy: str, structure: str):
    selected = get_strategy(feature, strategy)
    key = LEGACY_FORMATS.get(fmt, fmt)
    if key not in {LEGACY_FORMATS.get(f, f) for f in FEATURES[feature][1]}:
        raise ValueError('feature does not support format')
    if structure != selected.flow:
        raise ValueError('structure does not belong to strategy')
    return selected


def selection_prompt(fmt: str, feature: str, strategy: str, structure: str) -> str:
    selected = validate_selection(fmt, feature, strategy, structure)
    return ('# Selected content layers (editorial guidance)\n'
            f'Feature: {feature}. Content strategy: {selected.label}.\n{selected.instruction}\n'
            f'Script progression: {FLOWS[structure]}\n'
            'The selected strategy takes precedence over default creative examples for this format. '
            'Do not require comedy, a demonstration or a personal story unless the selected strategy calls for it. '
            'Use this treatment and progression within native output sections. Adapt the example '
            'to the actual medium, topic and duration. Point counts (including suggested 3-6 points), '
            'a two-second hook and a closing CTA/question are guidance, not mandatory rejection rules. '
            'For static posts adapt a spoken hook to a headline. For short Stories preserve one idea, '
            'the selected intent and brevity; do not force multiple tips or an interaction. '
            'Never invent facts, quotations, experience, poll results or experiments. '
            'Do not print strategy or progression labels in audience-facing copy.')
