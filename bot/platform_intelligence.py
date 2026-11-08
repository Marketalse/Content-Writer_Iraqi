"""Versioned platform-native strategy registry.

Creative recommendations are hypotheses, NOT official algorithm guarantees.
This module is intentionally side-effect-free and does not enable publishing.
"""
from dataclasses import dataclass
from typing import Tuple
from story_styles import short_story_policy, is_story

@dataclass(frozen=True)
class Profile:
    platform: str
    format: str
    character: str
    objective: str
    structure: Tuple[str, ...]
    cta: str
    metrics: Tuple[str, ...]
    official_urls: Tuple[str, ...]
    publish_api_status: str = "unverified"

META_RANKING = "https://about.fb.com/news/2023/06/how-ai-ranks-content-on-facebook-and-instagram/"
META_BEST = "https://about.fb.com/news/2024/10/best-practices-education-hub-creators-instagram/"
LINKEDIN_ARTICLE = "https://www.linkedin.com/help/linkedin/answer/a516913"
TIKTOK_RANKING = "https://support.tiktok.com/en/using-tiktok/exploring-videos/how-tiktok-recommends-content"

PROFILES = {
    "instagram_story": Profile("instagram", "story", "intimate, immediate, interactive", "relationship", ("context", "observation", "question"), "reply or sticker interaction", ("replies", "sticker_interactions", "completion"), (META_RANKING, "https://about.fb.com/news/2024/05/new-stickers-in-instagram-stories/")),
    "instagram_reel": Profile("instagram", "reel", "visual, dynamic, relatable", "discovery", ("hook", "tension", "demonstration", "payoff", "cta"), "share or follow", ("watch_time", "shares", "follows"), (META_RANKING, META_BEST)),
    "instagram_post": Profile("instagram", "post", "focused, visual, memorable", "message", ("visual_headline", "caption_context", "takeaway", "cta"), "save or comment", ("saves", "shares", "profile_visits"), (META_RANKING, "https://about.fb.com/news/2023/11/new-ways-to-create-content-on-instagram/")),
    "instagram_carousel": Profile("instagram", "carousel", "sequenced, educational, swipeable", "education", ("cover", "problem", "insights", "example", "summary", "cta"), "save or share", ("saves", "shares", "comments"), (META_BEST, "https://about.fb.com/news/2023/11/new-ways-to-create-content-on-instagram/")),
    "instagram_instants": Profile("instagram", "instants", "private, spontaneous, unpolished", "close_connections", ("moment", "short_caption"), "authentic reaction", ("manual_feedback",), ("https://about.fb.com/news/2026/05/instants-share-in-the-moment/",)),
    "instagram_live": Profile("instagram", "live", "interactive, unscripted, transparent", "community", ("opening", "talking_points", "audience_questions", "recap", "cta"), "ask questions", ("live_viewers", "questions", "inquiries"), ("https://about.fb.com/news/2021/03/doubling-up-on-instagram-live-with-live-rooms/",)),
    "instagram_broadcast_channel": Profile("instagram", "broadcast_channel", "direct, insider, communal", "retention", ("personal_update", "value", "prompt"), "react or vote", ("reactions", "poll_participation"), ("https://about.fb.com/news/2023/02/instagram-broadcast-channels-creators-deepen-connections-with-followers/", "https://about.fb.com/news/2024/12/get-closer-to-your-community-with-replies-prompts-and-insights/")),
    "linkedin_post": Profile("linkedin", "post", "credible, insightful, professional", "authority", ("insight", "context", "evidence", "lesson", "discussion"), "professional discussion", ("relevant_comments", "reposts", "inquiries"), ("https://www.linkedin.com/help/linkedin/answer/a7134086", "https://www.linkedin.com/business/marketing/blog/ai-search/how-to-maximize-ai-visibility-for-your-linkedin-posts")),
    "linkedin_article": Profile("linkedin", "article", "analytical, structured, evidence-based", "thought_leadership", ("title", "summary", "problem", "analysis", "evidence", "framework", "recommendations", "conclusion"), "discuss or consult", ("article_views", "inquiries", "referrals"), (LINKEDIN_ARTICLE, "https://www.linkedin.com/business/marketing/blog/content-marketing/linkedin-articles")),
    "tiktok_story": Profile("tiktok", "story", "casual, immediate, participatory", "connection", ("moment", "context", "reply_prompt"), "react or reply", ("views", "replies", "reactions"), ("https://support.tiktok.com/en/using-tiktok/creating-videos/tiktok-stories",)),
    "tiktok_video": Profile("tiktok", "video", "fast, authentic, entertaining", "discovery", ("pattern_interrupt", "relatable_problem", "insight", "payoff", "cta"), "participate or share", ("watch_time", "full_views", "shares"), (TIKTOK_RANKING, "https://ads.tiktok.com/business/en/guides/what-is-ad-creative-guide")),
    "tiktok_photo_carousel": Profile("tiktok", "photo_carousel", "visual, swipeable, relatable", "education", ("curiosity_cover", "problem", "progression", "payoff", "cta"), "save or comment", ("saves", "shares", "comments"), (TIKTOK_RANKING, "https://newsroom.tiktok.com/editing-tools?lang=en")),
}

# Backwards-compatible mapping: existing four Telegram choices remain unchanged.
LEGACY_FORMATS = {
    "story": "instagram_story",
    "reel": "instagram_reel",
    "carousel": "instagram_carousel",
    "linkedin": "linkedin_post",
}

def get_profile(key: str) -> Profile:
    resolved = LEGACY_FORMATS.get(key, key)
    try:
        return PROFILES[resolved]
    except KeyError as exc:
        raise ValueError(f"Unknown platform format: {key}") from exc

def strategy_prompt(key: str, *, story_intent: str = 'auto') -> str:
    """Stable policy fragment suitable for cached system prompts."""
    p = get_profile(key)
    if story_intent != 'auto':
        if not is_story(key):
            raise ValueError('Story intent requires Story format')
        return ('# Native short Story strategy (editorial guidance)\nPlatform: ' + p.platform
                + '\n' + short_story_policy(story_intent)
                + '\nNo engagement or ranking guarantees; never invent evidence.')
    return "\n".join([
        "# Platform-native creative strategy (recommendations, not algorithm requirements)",
        f"Platform: {p.platform}",
        f"Format: {p.format}",
        f"Character: {p.character}",
        f"Primary purpose: {p.objective}",
        "Preferred storytelling order: " + " -> ".join(p.structure),
        "Preferred CTA: " + p.cta,
        "Evaluate against: " + ", ".join(p.metrics),
        "Do not claim these creative defaults are official ranking factors.",
        "Never invent research, sales results, or creator experience.",
        "Do not claim automated publishing works without endpoint verification.",
    ])
