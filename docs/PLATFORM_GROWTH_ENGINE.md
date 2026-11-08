# Platform-Native Growth Engine — Implementation Strategy

Status: **Phase 1 merged; Phase 2 AI quality engine implemented for PR review**. Not a claim of automated growth or API publishing.

## Problem uncovered in original repository
- Four menu types were conflating Instagram and TikTok, while LinkedIn Post and Article had no distinction.
- `knowledge/formats/caption.yaml` dictated exactly three Hook/Content/CTA blocks for every output.
- `bot/quality.py` enforced the generic structure even for slides, articles and videos.
- Old format guides contained unsupported absolutes about "strongest algorithm signals", posting windows and ideal content lengths.
- `/published <id>` records a publication event but does not yet ingest outcome metrics or learn by platform.
- Prompt construction loads extensive examples on every request; review token cost and cache efficiency before increasing KB size.

## Phase 1 — implemented in this branch
1. Add 12 independently sourced editorial profiles in `bot/platform_intelligence.py`. Keep strategy separate from technical publishing eligibility.
2. Replace the universal prompt output contract with a native structure for each format in `bot/prompts.py`.
3. Replace the universal three-block validator with deterministic format-native checks in `bot/quality.py`; editorial bounds are soft heuristics, **not** algorithm facts.
4. Keep old Telegram IDs `story`, `carousel`, `reel`, `linkedin` working; add new explicit choices.
5. Add offline regression tests. No live Anthropic/Telegram tests performed.

## Phase 2 — quality, evidence and publishing controls

The AI reviewer and bounded revision engine are implemented; see
[architecture, validation and remaining scope](AI_QUALITY_ENGINE.md). The broader items
below include future work; typed draft schemas and an approval queue are not yet implemented.
- Separate user-verified numbers from invented numbers: accept statistics only when supplied with provenance; mark unsupported numeric claims for human review, not a naïve ban on all numbers.
- Structured JSON drafting with a typed schema per format, then deterministic formatting for Telegram. This eliminates brittle text header parsing.
- Confidence labels on research statements: `official_documented`, `creative_hypothesis`, `account_specific`, `unverified`. Retain official URL, checked_at, version, and scope.
- Add rubric scoring per format: usefulness, native tone, novelty, dialect accuracy, clarity, credibility, audience fit, CTA consistency.
- Add approval queue and explicitly separate *drafting* from *publishing*. Verify endpoints, permissions, quotas and media constraints for each supported API before offering publish.
- Update the analyst to reason about platform-specific audience intent, not generic "pain + objection" alone.
- Expand max output token strategy and chunk rendering for long LinkedIn Articles; add article-specific length safeguards.
- Track feature flags and migration compatibility; keep main operational until tests and pilot review pass.

## Phase 3 — measurement and feedback loop
- Extend post log with `platform`, `format`, `content_id`, `publication_timestamp`, `objective`, `hook_type`, `language`, `variant_id`, `source_refs`.
- Ingest permitted metrics from official provider analytics or manual user input, normalized per platform. Include sample size, measurement window, data source, and reach denominator.
- Optimize objective-aligned metrics, not vanity views alone. Example: reach -> non-follower reach/watch time; authority -> relevant discussions and inbound leads; retention -> qualified replies.
- Build an experiment ledger for hook, CTA, presentation, and narrative variants; compare within the SAME platform and format, accounting for posting time and topic.
- Recommend new experiments based on observed patterns, without claiming causal certainty from uncontrolled correlations.
- Report quality and cost metrics: acceptance rate, validator false positives, revisions per accepted draft, tokens/cost, time-to-draft, published outcomes.

## Phase 4 — operational growth system
- Telegram commands: `/platform`, `/brief`, `/draft`, `/review`, `/published`, `/results`, `/experiments`, `/report`. These are a roadmap, NOT all implemented.
- Content calendar, cross-format repurposing from one core insight, deliberate audience-specific adaptation, approval workflow, retention of source citations.
- Dashboards by platform and objective, with safe storage of results and user-consented usage.

## Acceptance criteria before merge
- All 12 native choices visible in Telegram and correctly routed to their own checker.
- Legacy callbacks still generate correctly; no duplicate or incompatible templates in system prompt.
- Unit tests pass; test invalid/missing fields, slide ordering, article headings, and prohibited claims.
- Manually review at least 3 drafts per format with Iraqi copywriting rubric; log findings.
- No hidden auto-publication, no unverified algorithm promises, no external API work without explicit configuration.
- Test concurrent requests, failures, quota enforcement, long outputs and cost tracking.
- Validate actual official APIs separately from the editorial format registry.

## Official reference entry points
- Meta ranking: https://about.fb.com/news/2023/06/how-ai-ranks-content-on-facebook-and-instagram/
- Meta creator best practices: https://about.fb.com/news/2024/10/best-practices-education-hub-creators-instagram/
- Instagram Instants: https://about.fb.com/news/2026/05/instants-share-in-the-moment/
- LinkedIn article advice: https://www.linkedin.com/help/linkedin/answer/a516913
- TikTok recommendation system: https://support.tiktok.com/en/using-tiktok/exploring-videos/how-tiktok-recommends-content
- TikTok Stories: https://support.tiktok.com/en/using-tiktok/creating-videos/tiktok-stories

**Note:** Documentation is versioned; a launch page is not proof of current API support. Check account capabilities and publication API documentation before integration.
