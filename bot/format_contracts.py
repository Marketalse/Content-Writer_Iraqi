"""Per-format editorial contracts shared by writer and reviewer.

These describe this product's creative choices, not platform ranking requirements.
Transport section labels do not prescribe a fixed narrative or number of points.
"""
from platform_intelligence import LEGACY_FORMATS, PROFILES

FORMAT_CONTRACT_VERSION = "native-v2"

NATIVE_OUTPUTS = {
    'instagram_story': 'STORY: one immediate moment, observation or quick explanation\nINTERACTION: a context-linked reply or sticker question',
    'instagram_reel': 'HOOK: spoken opening\nSCRIPT: complete spoken narrative or demonstration\nVISUALS: shot, editing and on-screen cues\nCTA: one relevant next action',
    'instagram_post': 'HEADLINE: visual headline\nCAPTION: context and one developed idea\nCTA: one relevant response or next action',
    'instagram_carousel': 'SLIDE 1: cover\nSLIDE 2: develop the idea\nSLIDE 3: continue the sequence\nSLIDE 4: payoff\nAdditional consecutive slides only as needed (4-12 total).\nCAPTION: context without repeating all slides\nCTA: one relevant next action',
    'instagram_instants': 'CAPTION: one short spontaneous caption',
    'instagram_live': 'OPENING: host opening\nTALKING POINTS: flexible discussion outline\nAUDIENCE QUESTIONS: useful live conversation prompts\nCLOSING: recap and natural next step',
    'instagram_broadcast_channel': 'UPDATE: useful insider message\nPROMPT: one relevant reaction, reply or poll invitation',
    'linkedin_post': 'INSIGHT: specific professional observation\nBODY: reasoning, experience supplied in the brief, or a practical lesson\nDISCUSSION: a substantive professional question',
    'linkedin_article': 'TITLE: specific analytical title\nSUMMARY: executive summary\n## Topic-specific section title\nDevelop the analysis.\n## Another topic-specific section title\nDevelop evidence, trade-offs and recommendations. Add sections as needed.\nCONCLUSION: actionable synthesis',
    'tiktok_story': 'STORY: a casual in-the-moment observation\nINTERACTION: an easy reply question',
    'tiktok_video': 'HOOK: immediate spoken or visual opening\nSCRIPT: complete entertaining explanation or demonstration\nVISUALS: action, shot progression and on-screen cues\nCTA: one natural participation invitation',
    'tiktok_photo_carousel': 'SLIDE 1: curiosity cover\nSLIDE 2: relatable setup\nSLIDE 3: visual progression\nSLIDE 4: payoff\nAdditional consecutive slides only as needed (4-12 total).\nCAPTION: short context\nCTA: one relevant next action',
}

GUIDANCE = {
    'instagram_story': '''An intimate, immediate exchange with an existing follower. Write one small
moment or quick useful observation in conversational Baghdadi, then a question that belongs to
that moment. Let the viewer feel present. No lecture, artificial viral hook, three-point lesson,
or follow/sales pitch. Do not invent a personal event. If the brief asks for a checklist,
keep it genuinely brief; never insert one by default.''',
    'instagram_reel': '''A visual discovery video. Start in the interesting action or tension,
then demonstrate, tell a supplied real story, contrast an assumption with reality, or explain
one useful idea with a payoff. SCRIPT is speech, VISUALS describes what makes it visible.
Choose the progression from the topic; do not default to an intro and three tips. A list is
appropriate only when the brief calls for steps. Close with one ask connected to the payoff.''',
    'instagram_post': '''One focused visual message. HEADLINE belongs on the image; CAPTION
adds context, perspective or an example rather than restating it. Develop one memorable idea
in natural paragraphs. Do not stretch it into a video script or an arbitrary numbered list.
The final action should follow from the message, not a generic request to follow.''',
    'instagram_carousel': '''A deliberately swipeable educational sequence. Each slide earns
the next: a question, explanation, worked example, contrast or reveal. Use one clear visual
idea per slide and enough slides to resolve the cover promise. Do not repeat a full caption
on each slide or force exactly three lessons. The accompanying caption adds context.
A save/share invitation should make sense for what the sequence teaches.''',
    'instagram_instants': '''A private, spontaneous, unpolished glimpse. One short caption
attached to the supplied moment. No hook section, lesson, numbered advice, content funnel
or CTA. Do not turn it into an inspirational feed post or invent the image/event.
A simple human reaction can be the whole piece.''',
    'instagram_live': '''A live conversation plan for a host, not a polished short-video script.
Establish why the audience is here, develop flexible talking points with demonstration or
follow-up opportunities, invite relevant questions and summarize. Leave room for responses
and unscripted discussion. The number of topics and audience prompts follows the brief;
there is no mandatory three-point agenda.''',
    'instagram_broadcast_channel': '''A direct insider message to an opted-in community.
Share a useful update, a decision, early access detail or behind-the-scenes context grounded
in the brief. End with an easy reaction or poll connected to that update. Avoid a public-feed
hook, a mini article, three teaching points or repeated follow requests.''',
    'linkedin_post': '''A credible professional perspective for Iraqi founders and practitioners.
Open with a specific observation, develop the reasoning and trade-offs in short paragraphs,
and invite substantive discussion. Use only supplied experience; never invent clients or
results. A story, analysis, counterexample or lesson can work. Do not impose three numbered
points, an algorithmic hook or an unrelated follow CTA.''',
    'linkedin_article': '''An analytical article, not an expanded caption. Use a clear title,
executive summary and topic-specific section headings. Develop the problem, evidence,
reasoning, trade-offs and practical recommendations as the topic requires. Distinguish
supported facts from hypotheses. Give the argument enough space; do not compress it into
three tips or pad it with a repeated hook/CTA formula.''',
    'tiktok_story': '''A casual immediate moment for an informal reply. Keep it light, direct
and recognizably Iraqi, as if responding to someone in the moment. One quick observation
and an easy question are enough. Do not import Instagram Reel staging, an educational
three-point list or a promotional ending. Do not fabricate events.''',
    'tiktok_video': '''An entertainment-led discovery video with visible action and spoken
energy. Lead with an immediate situation, surprise or relatable problem, develop it through
a demonstration, contrast, response or supplied real story, and deliver the payoff.
VISUALS must support that progression. Avoid the same three-tip speech used for every topic;
use steps only when requested. Participation should be natural to the situation.''',
    'tiktok_photo_carousel': '''A visually led, relatable swipe sequence. Establish curiosity,
show an unfolding situation, contrast or example, then deliver a clear visual payoff.
Keep copy easy to scan, with each slide moving the idea forward. It should feel native
to photo swiping rather than a LinkedIn essay split into cards. Do not force three tips
or identical captions on every slide.''',
}

assert NATIVE_OUTPUTS.keys() == GUIDANCE.keys() == PROFILES.keys()


STORY_TREATMENTS = {
    'teaching': 'Teach one useful concept through connected frames; develop the reasoning and resolve the initial question.',
    'poll': 'Invite a genuine poll or question, develop its context and offer a useful follow-up; never invent audience results.',
    'reveal': 'Show a supplied starting situation and a supported contrast or explicitly hypothetical desired state, then the takeaway.',
    'demonstration': 'Show how a supplied process or product works across clear frames, explaining its practical relevance.',
    'referral': 'Give useful context and value before referring to an existing supplied resource or destination; never invent links or automation.',
}


def format_contract(fmt: str, story_mode: str = 'moment') -> str:
    key = LEGACY_FORMATS.get(fmt, fmt)
    if key not in GUIDANCE:
        raise ValueError(f'Unknown platform format: {fmt}')
    guidance, output = GUIDANCE[key], NATIVE_OUTPUTS[key]
    if story_mode != 'moment':
        if key not in ('instagram_story', 'tiktok_story') or story_mode not in STORY_TREATMENTS:
            raise ValueError('invalid Story mode')
        guidance = ('Connected native Story sequence. ' + STORY_TREATMENTS[story_mode]
                    + ' Keep the Iraqi conversational voice. Choose 2-8 frames according to the idea, '
                      'not a fixed number of tips. Each frame has one clear purpose. '
                      'An interaction can be a relevant question, poll or truthful resource action.')
        output = ('FRAME 1: establish the situation\nFRAME 2: develop or resolve it\n'
                  'Add consecutive FRAME N: sections only as needed (2-8 total).\n'
                  'INTERACTION: one relevant question, poll or next action')
    return ('# Format character and creative treatment (' + FORMAT_CONTRACT_VERSION + ')\n' + guidance
            + '\n\n# Required platform-specific output structure (editorial template, not official ranking rule)\n'
            + output
            + '\nUse the exact native section labels above, each once and in order. '
            'Explanatory lines describe the contract; do not copy them into the output. '
            'Choose narrative, detail and point count from the topic and this format. '
            'There is no universal Hook / three points / CTA template. '
            'Shared voice examples provide diction and rhythm only, never another format layout.')


def adapt_contract(system: str, fmt: str, story_mode: str) -> str:
    if story_mode == 'moment':
        return system
    if system.endswith(format_contract(fmt, story_mode)):
        return system
    original = format_contract(fmt)
    prefix = system[:-len(original)] if system.endswith(original) else system + '\n'
    return prefix + format_contract(fmt, story_mode)
