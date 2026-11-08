"""Short Story intent choices. These guide creative treatment, never a three-point layout."""
STORY_STYLES = {
    'entertain': {
        'label': '😄 ترفيهي', 'purpose': 'entertain',
        'instruction': 'One light, relatable observation or contrast. A small smile or recognition is enough. No forced lesson or promotional ending; no humiliation, invented personal events or results.',
        'topic_prompt': 'دز الموضوع أو الموقف اللي تريد نحچي عنه بخفة.',
    },
    'educational': {
        'label': '💡 معلومة بسيطة', 'purpose': 'educate',
        'instruction': 'Deliver one useful fact, clarification or practical insight directly. Explain just enough to understand it. No introduction promising tips, numbered advice or mandatory audience question.',
        'topic_prompt': 'شنو المعلومة أو الفكرة اللي تريد توصلها؟',
    },
    'everyday': {
        'label': '🏙️ موقف من الحياة', 'purpose': 'trust',
        'instruction': 'One recognizable everyday-life issue and a concise observation about it. Use supplied real events or clearly hypothetical situations; do not invent an experience in the creator\'s voice. No list of solutions.',
        'topic_prompt': 'دز الموقف أو المشكلة اليومية؛ وإذا حقيقية، اذكر التفاصيل اللي نكدر نستخدمها.',
    },
    'ask_audience': {
        'label': '❓ سؤال للجمهور', 'purpose': 'conversation',
        'instruction': 'Ask one specific, easy-to-answer question addressed to the audience. Include only the minimum context needed. It may suit a question sticker or a meaningful poll. Do not answer it yourself or add a lesson or second ask.',
        'topic_prompt': 'عن شنو تريد تسأل الجمهور؟',
    },
    'answer_question': {
        'label': '🗣️ جواب على سؤال', 'purpose': 'educate',
        'instruction': 'Answer the supplied question directly, in simple Iraqi speech, with only the explanation needed. Do not turn it back into an audience question, invent who asked it, or end with a follow request.',
        'topic_prompt': 'دز السؤال اللي تريد نبني عليه الجواب.',
    },
}
STORY_ANGLE_KEYS = {f'story_{key}': key for key in STORY_STYLES}


def is_story(fmt: str | None) -> bool:
    return fmt in ('story', 'instagram_story', 'tiktok_story')


def short_story_policy(intent: str) -> str:
    if intent not in STORY_STYLES:
        raise ValueError('unknown Story intent')
    return ('Short spoken Story, approximately 30 seconds. One idea, simple direct Baghdadi speech. '
            'Use only the context necessary to make the point. Target 35-65 spoken words at most '
            'for explanation, fewer for a question; hard editorial ceiling 75 words and 800 characters. '
            'Do not pad a short answer to meet a word target. No named hook/content/CTA blocks, '
            'no numbered three-tip lesson, no 📊/🔥/💡 point stack, no generic follow/sales closing. '
            'A natural opening is enough; no mandatory suspense, slogan or greeting. '
            + STORY_STYLES[intent]['instruction'])
