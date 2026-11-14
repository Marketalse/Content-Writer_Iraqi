# Reusing Content Workshop for the creator release

2026-11-14. Source reviewed: Marketalse/Content_Workshop main `ec65d20`.
Current writing-engine baseline: Content-Writer_Iraqi `0eb04d6`.
Static source review only; no browser interaction, paid generation, installation,
legacy test execution or live service validation was performed for this assessment.

## Recommendation

Use the existing Content Workshop dashboard as the starting point for the primary
web experience. Adapt its screens to the current writing engine through a server
API. Keep one engine and one quality/research policy, with Telegram as an optional
second interface. Do not merge both generation loops or deploy the local desktop
server unchanged. This is a recommended direction, not an implemented migration.

## What the old project actually contains

`src/content_workshop/web/dashboard.html` contains a browser interface with creation,
progress, results, run history, copy controls, editing/posted-text capture, metrics,
dialect word review, checks and settings. It is HTML/CSS/JavaScript; introducing a
new frontend framework is not required simply to reuse it.

`dashboard.py` serves it on 127.0.0.1 using ThreadingHTTPServer. It guards local API
calls with a process/session token embedded in the page and expected Host headers.
The app uses local files for output/settings/logs and in-memory threaded jobs.
Those are local-app protections and storage assumptions, not hosted creator accounts.

`committee.py` implements a separate analyst/strategist/writer/dialect/critic flow.
It has structured schemas and bounded revisions, but no external search stage in
that orchestration; the analyst instead flags claims needing verification.
Do not confuse listing claims to verify with actually researching them.

## Reuse decisions

| Component | Decision | Adaptation needed |
|---|---|---|
| Topic form and format cards | Reuse layout and interaction | Current platform/feature/treatment taxonomy; creator profile selection |
| Progress display | Reuse presentation | Real job states from the shared engine, including research, editing and failure outcomes |
| Script section cards and copy buttons | Reuse presentation | Current canonical fields and delivery policy; preserve readable Arabic/RTL |
| Library and run details | Reuse experience | Server persistence, creator ownership and separate draft versions |
| Edited-text capture | Reuse concept and UI | Targeted AI edits must pass final checks; human versions clearly identified |
| Edit-ratio and feedback tracking | Reuse useful measures | Tie to creator/request/profile version; do not call the whole product ready from this metric alone |
| Dialect word review queue | Optional owner/admin feature | Separate spelling and creator voice; never silently impose old orthography |
| Local key/settings/update/Finder/stop controls | Desktop-only | Exclude from hosted creator UI; server secrets and admin deployment controls stay server-side |
| Committee loop and scores | Retain only as reference | Current engine is the proposed single source of orchestration; no parallel scoring systems |
| Local HTTP server and job store | Reference, not a hosted backend | Authentication, authorization, durable jobs, quotas and deployment operations |

## Important incompatibilities to resolve

1. Old formats are short_video, long_video_story, story_questions and post, with
   simple/medium/complex depth. Current feature/strategy/native formats are different.
   A depth level must not stand in for writing treatment or creator voice.
2. Old orthography explicitly favors ك/ج instead of گ/چ. Current calibrated voice
   permits گ/چ naturally. The confirmed creator profile must win, not an old global rule.
3. The old critic uses an 80/100 gate and a separate dialect score; current FQS is
   7.5/10 with mandatory gates. Keep one coherent policy and calibrated human evaluation.
4. Old results expose unpassed drafts with copy controls. Map approved, review-needed
   and withheld states explicitly; respect the current strict delivery policy.
5. Old settings allow choosing Opus for general generation. The current instruction
   limits Opus to failed-content advice; preserve that scope.
6. Old API errors can return exception strings. Hosted APIs need safe categories and
   request references, not raw provider or server exceptions.
7. Neither existing global voice implementation supplies separate creator onboarding.
   Reusing the web interface does not complete the roadmap's voice/profile milestone.
8. The owner's topic bank/examples must not become every new creator's private library.
   Public sample content must be explicitly shared and appropriately scoped.

## Target experience

First visit: creator account → supplied samples → editable voice summary → confirmation.
Everyday use: topic → writing treatment → platform + compatible feature → generate.
Results: clear script sections + suggested visuals/caption where supported, sources
when relevant, and simple controls to copy, request an edit or give feedback.
Internal script progression stays automatic by default.

The browser sends a validated request to an authenticated API. A job runner calls
the existing research/writing/review pipeline, saving the creator/profile version,
request, progress and checked result. The browser polls job status initially;
streaming can be added only if the simpler approach is insufficient. Telegram can
call the same application service later rather than own a separate workflow.

## Migration slices and acceptance

1. Freeze a reference of the current dashboard and agree the retained screens.
   Prove the form/results mapping with synthetic fixtures, no paid calls.
2. Extract the small application boundary used by current Telegram generation:
   validated request, creator/profile lookup, orchestration, persistence and safe
   delivery outcome. Avoid copying Telegram quota/logging semantics into HTML handlers.
3. Connect one complete web Story journey, then Reel/Post. Verify request choices,
   structural rendering, error states, replay protection and reviewed-artifact identity.
4. Implement creator authentication, profile ownership, durable jobs/history and quotas
   before opening the hosted app to independent creators. Keep provider keys server-side.
5. Run live deployed smoke checks and the roadmap evaluation pack; invite 5–10 testers.
   Keep the current Telegram path available during transition without requiring testers
   to switch between interfaces to complete a request.

This changes the roadmap's primary-interface direction. The earlier 332 passing tests
cover the current bot code; they do not validate a web migration or this old dashboard.
No integration, GitHub push or deployment has been performed in this assessment.

Subsequent implementation status: [PROJECT_EXECUTION.md](PROJECT_EXECUTION.md) and
[WEB_PREVIEW.md](WEB_PREVIEW.md) describe the M1 owner preview built after this assessment.
