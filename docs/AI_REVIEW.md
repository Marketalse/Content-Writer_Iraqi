# AI workflow review — 2026-11-10

Scope: local research-before-writing implementation, its validation and delivery wiring,
and coding-agent instructions. This is a focused review, not a full security or factual audit.

## Findings

### Medium — preference-only questions still require search evidence

In `bot/research.py`, `RESEARCH_SYSTEM` says a pure preference question needs no factual
claim, but `parse_research` rejects every ready result without sources and a search count.
`bot/bot.py:on_text` enables research for every topic. Consequently, a valid neutral
audience question can be withheld if research returns no cited evidence even though
there is no empirical claim to verify. This is a confirmed mismatch in the AI-written
implementation, not a provider outage.

Reproduction: construct a `Result` with a valid ready JSON summary explaining that the
topic is a preference question, no sources and no search requests; `parse_research`
raises `ValueError: research lacks cited evidence`.

Status: reported, not changed in this instruction-file task. A correction needs an explicit,
tested distinction between topics requiring evidence and questions containing no factual
premise; factual currency/regulatory claims must continue requiring official evidence.

### Live readiness blocker — credentials absent in this execution context

Presence-only checks found neither `ANTHROPIC_API_KEY` nor `TELEGRAM_BOT_TOKEN`.
Live hosted search, actual model support, organization search permissions and Telegram
polling have not been exercised. This does not establish whether production has credentials.
Passing offline tests does not establish live readiness; earlier statements that installation
was complete refer only to local files and offline validation.

### Limitation — source relevance and freshness remain AI judgments

`parse_research` checks citation presence and official hostname eligibility for detected
financial/regulatory topics. It does not deterministically prove that a cited decision is
current or supports a specific number. Prompts instruct the researcher and reviewer to
check dates, units and applicability. Those checks can still make mistakes; the provided
1320-to-1520 exchange-rate claim remains unverified in this session.

## Validation and state

- Current complete offline run: `.venv/bin/python -m unittest discover -s tests` —
  213 tests passed; search responses were synthetic fixtures. `git diff --check` passed.
- Current preference-only reproduction: rejected as described above.
- Credential check: names/presence only; no values displayed or stored.
- Agent skill installed locally, copied unchanged from the requested repository.
- `CLAUDE.md` provides instructions for Claude Code; `AGENTS.md` exposes the same review
  workflow to Codex. Neither file starts a service or monitors model output continuously.
- Application changes and instruction files remain local; no deployment or push performed.

## PROJECT BREAKER audit — 10 November 2026

The later audit distinguishes clean GitHub main `6c07e4e7e3c54b5ac3fd596b91723514fce9942a`
from the dirty local checkout based on `719210a0a65aae092745b4640035c3f569cd8199`.
Main passed 206/206 offline tests; the unfinished local facilitator snapshot passed
202/213, with 7 assertion failures and 4 errors. The earlier 213-pass result above
predates the paused facilitator edits and is not the current checkout's result.

See the [full audit report](/workspace/project-breaker-audit-20261110/FINAL_REPORT.md),
[defect register](/workspace/project-breaker-audit-20261110/FAILURE_REGISTER.md), and
[reproduction guide](/workspace/project-breaker-audit-20261110/REPRODUCE.md).
The audit reproduced persistence-recovery failures and batch-control defects on main,
plus local-only routing/normalization boundaries. Independent mocked routes demonstrate
that simple preference questions can now bypass research; the remaining numeric-option
routing issue is narrower than the historical finding above. No fixes were applied.
No paid API calls or real Telegram messages were made; live UAT readiness remains unverified.
Only this review-report pointer was added to the checkout during the audit.

## Audit-fix execution — 10 November 2026

The user subsequently authorized fixes for PB-01 through PB-10. The
[execution plan](FIX_EXECUTION_PLAN.md) breaks each issue into correction and validation
steps. The original audit files remain unchanged as historical evidence.

Local corrections now cover journal-tail quarantine/recovery, explicit storage errors,
atomic pilot settings with a prior valid backup and fail-closed corrupt permissions,
idempotent publication marks, strict routing/research JSON parsing, claim-aware routing,
unlabeled Story shortening, validated batch inputs, in-flight spending reservations,
updated facilitator fixtures and main/PR CI coverage. Render configuration now requests
deployment only after checks pass; actual account-level enforcement has not been tested.

Run `python scripts/verify_fixes.py` for authoritative current counts and per-issue results,
or add `--watch` for automatic verification after source/test/config changes while the
process runs. Generated `test_reports/fixes/index.html`, `REPORT.md`, `status.json` and
logs distinguish local results from external checks and source changes during a run.
They are not an always-on production monitor and do not prove deployment.

Live Anthropic/search/Telegram checks were not run. Changes remain local and uncommitted;
no deployment, paid request or real Telegram message was performed. Batch reservations
do not guarantee an exact provider bill beyond the configured observed spending stop.

## Provider credit and error reporting — 10 November 2026

The live record `20261110130105-adb94522` confirms deployment of `c8b69c0`, but
records only a facilitator error. It does not preserve the underlying provider reason,
so insufficient credit is a hypothesis for that historical attempt, not a confirmed cause.

Provider errors now carry fixed, sanitized codes plus provider and HTTP status. Explicit
low-credit / account-quota signals produce `provider_credit_exhausted`, survive stage
wrappers, and explain the billing problem in the Telegram warning and `/diagnose`.
Authentication, permission, model access, rate limits, connection failures and invalid
requests have different messages. Raw SDK response text, credentials and prompts are
not copied into diagnostic records. Confirmed credit failures do not retry or spend
against a fallback provider. Generic 400/429 responses do not imply an empty balance.

Validation uses synthetic SDK rejections and end-to-end pipeline error paths. No paid
generation was invoked to diagnose balance. Free read-only model metadata requests using
an existing Anthropic-scoped binding succeeded; that is not a balance check and does not
establish the state of the different account/key configured on Render.

## Nous fallback correction — 10 November 2026

The prior credit-notification patch explicitly stopped on insufficient Anthropic credit,
even when Nous was configured. That decision was too restrictive for the intended failover.
Two existing gaps also prevented a complete fallback run: Nous responses were always marked
as having unknown pricing, and structured prompts omitted the schema on the fallback route.

Read-only requests to https://inference-api.nousresearch.com/v1/models verified that
`anthropic/claude-sonnet-5-5` is not listed, while `anthropic/claude-sonnet-5.5` is listed.
Its published rates are $2 per million prompt tokens and $10 per million completion tokens.
The known-model pricing map is separate from Anthropic's; custom/unrecognized pricing
still blocks subsequent calls. No paid generation or account-balance query was performed.

Confirmed Anthropic credit exhaustion now permits one configured Nous fallback. After
success, the same attempt stays on Nous for later stages. The corrected default/legacy ID,
schema delivery and supported structured-output/low-effort settings are covered by tests.
Telegram reports a credit-triggered switch once. A missing fallback key is reported without
exposing its value. The historical failed record still cannot prove a balance-related cause.

The current hosted search belongs to Anthropic and is not silently emulated by Nous.
If research is required after failover, the request stops with `provider_search_unavailable`
instead of inventing evidence. Local environment bindings did not include a Nous key;
Render's actual Nous credentials and funded balance remain unverified here.


## Native writer transport and bounded structural repair — 2026-11-10

Confirmed defect: TikTok writers returned free-form text; missing native labels or
incorrect ordering stopped before any repair or independent review. Implemented
JSON field schemas for fixed-field formats (including TikTok video), canonical
rendering in contract order, and allowlisted heading case/balanced bold-wrapper
normalization. Section bodies are not rewritten by normalization. Dynamic carousel,
article, Story sequence and production envelopes keep their existing native contracts.

Fixed-field structural failures now receive at most one complete-script repair,
sharing the configured revision, call, token, time and observed-cost budgets. The
repair prompt receives exact expected/present/missing/empty/duplicate/order metadata.
Every repaired draft returns through deterministic validation, verified-fact checks
and independent review. Truncation, refusal and critical factual/safety gates remain
blocking. Setting repair_format=false disables structural repair; existing Story
length repair remains supported. Empty responses are withheld without a repair call.

Creator warnings and authorized diagnostics expose only allowlisted field names and
boolean ordering information. No unknown headings, draft bodies or provider errors
are copied into diagnostic field metadata. Regression fixtures cover both providers,
including malformed Nous JSON, decorated headings, wrong order, repeated failure,
exhausted budgets and factual uncertainty after repair. All provider responses used
for verification are synthetic; no paid API or Telegram calls were made.

Validation: 282 offline unittest tests passed; pip check and git diff --check passed.
All 39 offline format contract examples passed (semantic quality unverified).
Release CI results are recorded separately.


## Editorial score recovery — 2026-11-10

Confirmed: the engine stopped after one default edit, missing review issues, or a
non-improving reassessment. It now defaults to two editorial retries: a targeted edit
when actionable sections exist, followed by a fresh draft if quality still fails.
Without section feedback it regenerates directly. Every candidate passes native
validation, supplied-fact preservation and independent scoring plus all quality gates.
Only isolated format-identity failures can be recovered; factual, safety, topic and
voice failures still stop. Threshold 7.5 and dimension floor 6 remain unchanged.
Default manual-preview delivery is disabled. Explicit environment overrides are
preserved; Render must update older limits to enable the expanded loop.

Defaults increased to ten logical calls, 24,000 reserved output tokens and 180 seconds;
observed-spend stop remains $0.25. No infinite retries and no guaranteed acceptance.
Offline regressions cover score progression, a stalled edit followed by regeneration,
retry exhaustion, safety rejection on the final draft, and budget exhaustion before
final review. Live provider and Telegram calls were not exercised.

Verification: 288 offline regression tests passed through the no-network audit verifier;
dependency consistency and whitespace checks passed, as did 39/39 offline format
examples (semantic quality unverified). Render Blueprint and
example environment settings include the expanded loop and strict delivery defaults.


## Organized video delivery rule — 2026-11-10

TikTok video and Instagram Reel delivery previously exposed raw native transport
headings and long unformatted section bodies. Added a deterministic delivery renderer:
Arabic headings separate opening, spoken copy, filming directions and closing ask;
spoken paragraphs and shot suggestions are independently numbered with whitespace
and separators. No scene-to-speech correspondence is inferred. Reviewed wording,
placeholders and section order are preserved; no extra model call or score changes.
Native reviewed artifacts remain stored for validation, scoring and publication records.
Short Stories and other formats retain their delivery contracts. Optional detailed
production plans remain separate. Regression coverage checks video aliases, body
preservation, placeholders and existing Telegram delivery with production/manual previews.
Validation uses offline synthetic responses; no live Telegram or provider calls.

Local validation: 291 offline tests passed; pip check and git diff --check passed.


## Plain-language failure categories — 2026-11-13

Generation failures now start with a fixed Arabic category: content did not pass,
AI service/model-response problem, application/settings problem, resource limit,
or cause not yet established. Existing safe explanations, billing distinctions,
review gate reasons, field diagnostics and review IDs remain available. Authorized
/diagnose output includes failure_category. Rejected or malformed content is not
presented as proof of a coding defect. Generic response/routing/research failures
remain uncertain unless a typed provider failure identifies the service problem.

Storage and unexpected handler errors now return a simple technical message without
exposing exception text. This changes messages only; scoring, retry and delivery
approval policies remain unchanged. Local verification: 296 offline tests passed;
pip check and git diff --check passed. No live provider or Telegram calls were made.


## Spreadsheet content layers — 2026-11-13

Implemented the user-provided feature → strategy → script-structure taxonomy:
Post (6 strategies), Story (8), Reel (6), Live Topic (3 current Live treatments,
explicitly selected by the user). The destination platform/native subtype remains
an independent routing screen. Repeated explanatory rows in the workbook are not
extra options. Spreadsheet example timings/point counts are adapted to medium and
brevity rather than becoming automatic rejection rules. Selected strategies take
precedence over default creative examples; factual, safety and native-format gates
remain mandatory.

Feature/strategy/structure are validated before spending and passed consistently
to facilitator, analyst, writer, editor and independent reviewer via the brief.
They are persisted in records and available in scoped diagnostics and /version.
Back navigation clears dependent choices; stale cross-platform/strategy callbacks
are rejected. /brief reset retains menu selections for generation. Existing format
families, saved callbacks, long-form and other advanced formats remain accessible
through a separate compatibility menu. Workflow is content-layers-v3.

Offline coverage exercises all 61 feature/platform/strategy paths, all 23 strategy
placements through routing, writing and review, actual registered Telegram callback
handlers, callback payload sizes, stale clicks, authorization and selection resets.
No live provider, web-search or Telegram calls were exercised. Tests validate
contracts and wiring, not the creative quality of actual generated scripts.

Local verification: 303 offline tests passed, including the registered Telegram
Application boundary. pip check and git diff --check passed. No live deployment
claim is made; release CI and Render status are tracked separately.


## Creator voice correction — 2026-11-13

Confirmed conflicting guidance: voice.md recommended stock openings such as
«لا حبيبي», experience framing and default closing questions. The user explicitly
rejected a generated example with those features and supplied an approved direct,
metaphor-led, connected Iraqi version. The profile now treats that approved/rejected
contrast as authoritative over older inferred samples. It removes forced catchphrases,
unearned experience, slogan-by-slogan rhythm, mandatory belief flips, corporate caveats
and automatic engagement questions. It preserves concrete comparisons and natural
colloquial verbs without requiring the same metaphors or exact words on every topic.

Writer guidance prioritizes explicit calibration over historical examples. Independent
voice review compares wording and rhythm, not simply dialect markers, and asks for
specific section feedback when voice fails. The existing voice gate remains mandatory:
fail or uncertain prevents acceptance and manual-preview delivery. Factual and safety
rules remain in force; style examples are not evidence for new personal claims.

Validation: 305 offline tests passed, including calibration visibility for all 13
formats and fail/uncertain gate enforcement at high scores with manual previews enabled.
pip check and git diff --check passed. These checks establish prompt wiring and strict
delivery policy, not 100% subjective style accuracy. No live model or Telegram calls
were made. Render must load the new profile through redeployment.


Creator follow-up: added the nine explicitly supplied phrases as an optional bank,
including «لا حبيبي». They are allowed contextually, never mandatory or a checklist;
review must not fail a script solely for using one. The earlier rejected sample is
still a negative example of overall delivery, not a universal phrase ban. No invented
experience or exclusivity claim is licensed by the phrase bank.


## Senior topic adviser — 2026-11-13

Confirmed gap: a senior-model adviser had been proposed conversationally but was not
implemented. The screenshot shows a mandatory voice rejection and only the failure
message. Telegram now enables one bounded adviser call after eligible withheld
content failures. It uses the configured writer-tier model (Sonnet by default),
including the existing funded Nous route. The original topic, brief, current draft,
actual review feedback and evidence are supplied. Voice failures explicitly remain
writing/voice issues, not proof that the topic itself is bad.

The adviser returns 1–3 tightly related angles, reasons and research flags. It cannot
approve the rejected draft, promise a passing score or bypass safety. Safety or
topic-preservation failures and provider/system failures do not trigger alternatives.
Manual-preview delivery keeps its existing policy; this feature targets withheld
content. Advising shares the existing Session call, time, token, observed-spend and
known-pricing checks. Unavailable advice has a separate fixed reason, preserving the
original failure. No static suggestions are substituted for a failed model response.

Creator-only buttons use server-side suggestions, a nonce, selection snapshot and
single-use consumption. Choosing an angle re-enters normal quota, research routing,
writing, validation and independent review. It does not publish or change topic
without selection. Suggestions are stored with the attempt; diagnostics expose only
adviser status, model/provider, failure reason and count, not suggestion text.
Library/batch callers must explicitly opt in with suggest_topics=True; Telegram
opts in automatically. Regression checks use synthetic responses and the registered
Telegram Application boundary, not live provider or Telegram access.

Local verification: 317 offline tests passed; dependency consistency and whitespace
checks passed. Adviser output is capped at 1,800 reserved tokens and uses the same
Session limits as generation. Live model/Telegram behavior remains unverified.


## Opus-only failure adviser and numbered selection — 2026-11-13

Reproduced bug: a typed “1” after suggestions was treated as a fresh topic and
cleared the pending suggestions. Numbered replies (Western/Arabic digits and
“الاقتراح 1”) now select the stored topic, validate the current selection snapshot,
and resume the ordinary pipeline. Invalid option numbers preserve the choices
without spending. The existing nonce-scoped buttons remain supported and single-use.

Visible suggestions now contain natural short topic openings and a concise selection
prompt. Editorial reasons/research flags remain internal; the creator no longer sees
scoring jargon or “weakness of writing” commentary in the option list. The adviser
is instructed to preserve the creator's direct voice and original stance rather
than adding balanced corporate counterarguments or generic headings.

Only the failed-content adviser calls claude-opus-5-5, with per-call Nous fallback
anthropic/claude-opus-5.5. Normal writer, reviewer, routing and research models stay
unchanged; Session rejects explicit Opus requests for normal stages. Nous fallback
keeps Opus for advice, never silently downgrading to the normal Sonnet default.
Native Opus uses supported adaptive thinking, medium effort and structured output.

Free catalog reads on 2026-11-13 verified both model IDs and capabilities. Official
Anthropic pricing and the public Nous catalog list $4/M input and $20/M output;
Anthropic cache reads are $0.20/M and five-minute writes $5/M. Existing Session
budgets and the single 1,800-token adviser call remain in effect. No paid Opus
or other live generation was run. Offline regression suite: 321 tests passed;
pip check and git diff --check passed before the tooling installation changes.


## Requested coding tools installation — 2026-11-13

Installed all six requested packages: Karpathy, Ponytail (verified matching
DietrichGebert marketplace), Matt Pocock's 38 skills, Addy Osmani agent-skills,
ECC 2.2.3 and official-marketplace Superpowers. Claude CLI was absent; local CLI
2.1.323 was installed with an isolated writable configuration. Plugins are project
scoped; Matt skills target Codex and Claude Code. Existing Karpathy guidance and
project instructions were preserved. The public plugin registry settings, skills,
source hashes and upstream Matt license are versioned; credentials/caches are not.

ECC is configured with minimal hooks. Its production dependencies were installed
manually from the lockfile after the plugin manager declined override handling.
Ponytail's optional ledger/export are disabled. No live coding agent/model session
or bundled browser MCP was launched. Installation is not a continuous bug monitor;
reload the relevant coding agent to discover the installed packages. See
CODING_TOOLS_INSTALLATION.md and its machine-readable inventory for verification.

## Bot-compatible topic library — 2026-11-14

Confirmed compatibility gap: the rewritten spreadsheet had editorial feature/strategy
labels but no supported Telegram Excel-import path, and the legacy batch runner only
supports three formats without all content layers. Added a packaged, validated JSON
bank and `/topics` / `/topic CONT-ID` handlers rather than presenting that spreadsheet
as directly importable. The root menu links to the six-pillar library.

All 145 original IDs have valid menu-native feature/format/strategy/structure tuples.
Current compatible destinations are preserved; source recommendation conflicts are
resolved explicitly in each record's format_note. The brief carries audience, angle,
outline and research guidance as unverified editorial material, with no fabricated
citations or approved evidence. Four ambiguous topics are held; four source Used
entries require explicit rewrite confirmation; the remaining 137 are defined/unused.

Preview is free of model/quota calls. A token and full selection snapshot bind the
confirmation to the selected topic. Replay, changed settings, back navigation and
reset cannot reuse it. Confirmation invokes the existing pipeline with research and
failure advice enabled. New custom text clears previous library source material;
clarification/adviser continuations retain their relevant context. Diagnostics retain
the safe topic ID alongside the normal run ID. Existing quality/delivery gates and
Opus-only failure adviser scope are unchanged.

Verification: 332 offline tests passed, including all 145 Brief JSON round-trips,
writer/reviewer configuration, every browse page, held/used behavior, registered
Telegram dispatch, full handler-to-pipeline handoff, and stale-confirmation rejection.
`pip check` passed. Export validation: seven-sheet bot-ready Excel, CSV and JSON;
145 unique IDs; all four prior workbook sheets (including 32-column original archive)
preserved; no formulas introduced. No runtime Excel dependency was added.

Limits: no paid/live model call, live Telegram message, new source research or Render
deployment was performed. Excel upload import and dynamic chat editing of held records
are not implemented. Mapping compatibility does not guarantee a generated script's
quality score. Deployment status is reported separately after GitHub CI.

## Beta readiness planning review — 2026-11-14

Reviewed main 0eb04d6 against the requested creator-facing product. Current status:
working prototype requiring integration and live acceptance validation. A roadmap,
current-state matrix and proposed release gates are in BETA_RELEASE_ROADMAP.md.

Confirmed high-priority product gap: prompts/reviewer/adviser read the shared owner
voice; approved_examples filters by format/mode/intent without a creator identity.
This is unsuitable as independent creator voice onboarding. Existing post access is
scoped; this observation does not assert a demonstrated cross-chat history leak.

Confirmed recovery limitation: revision.execute stops on mandatory review blockers
unless can_repair_format permits format repair. Low-score revisions therefore do not
mean uncertain voice gets an editorial repair. Shared voice and limited blocker
recovery are evidence-backed design gaps; they do not prove the cause of every
historical model rejection. Multiple current/legacy entry paths and memory-only menu
state require an integration/restart acceptance plan. Existing research/fallback and
feedback implementations should be validated/reused, not reported as absent.

Rechecked: 332 offline tests passed; pip check passed. Latest recorded release/main
CI is successful. No live Telegram, provider, search, Render or human acceptance
checks were run in this review. No application, deployment, scoring or delivery
behavior changed. Roadmap targets are proposals, not measured results. Files remain
local planning documents until committed; no implementation or release was performed.


## Content Workshop interface reuse assessment — 2026-11-14

Statically reviewed Marketalse/Content_Workshop ec65d20. Confirmed reusable browser
screens for creation, progress, structured results, library and human edit tracking.
The server is explicitly local/single-user with a shared session token, threaded
memory jobs and local file storage; hosted accounts and per-creator isolation remain
work. Its committee flags research claims but does not perform external search in
that orchestration. Its unpassed-draft display, general Opus selection, scoring and
orthography differ from current requirements. Preserve the current engine's policies
through an adapter rather than merging independent loops.

Saved WEB_INTERFACE_REUSE_ASSESSMENT.md and updated the local beta roadmap with the
recommended web-first direction. No app behavior changed, no dependencies installed,
no legacy tests/browser/live APIs exercised, no merge/push/deployment. The current
bot's earlier 332-test result does not establish the old dashboard or integration
works. git diff --check passed for planning changes.

## M1 private web Story journey — 2026-11-14

Started the execution plan in PROJECT_EXECUTION.md and a release-maintained six-
milestone snapshot in web/progress.json. Adapted the Content Workshop ec65d20 palette,
sidebar/card layout and create/history/edit interactions into a smaller web interface.
New web_service.py calls the existing run_pipeline with the normal selected Story
brief, research, independent review and failure-only advice. No second generation
loop, model-selection UI or review-policy relaxation was added. The exact final text
must match its reviewed fingerprint, pass native checks, intent and mandatory gates,
and meet creative thresholds before it reaches the web copy field. Manual-review
and blocked drafts stay withheld. Edit requests preserve topic and re-enter checks;
clarification and advice use explicit parent jobs and validated actions.

webapp.py is a separate, single-owner FastAPI preview. Live mode requires a preview
password; session cookies are HttpOnly/SameSite, Secure on HTTPS. Model keys remain
server-side. Added origin/body guards, bounded sign-in attempts, safe errors and input
validation without echoing private input. SQLite jobs preserve history/idempotency;
one active job and a daily admission limit bound preview use. Interrupted jobs are
marked on restart and never silently rerun. This is separate from Telegram quotas.
Existing bot entry point and Render worker configuration were preserved.

Verified: 346 offline tests passed; pip check passed. New tests cover real ASGI routes,
private sessions, idempotency, redacted failure output, unsafe input, durable restart
handling, quota/admission behavior, exact-artifact delivery, edits, clarification and
advice context, plus the real pipeline with only model transport mocked. CI now installs
optional web requirements as well as bot requirements. Headless Chromium exercised
nine desktop/mobile interface checks against explicit demo mode: form/treatment,
sample-only output, edit submission, library reopen, six milestones, mobile submission,
no horizontal overflow and no JavaScript errors. Screenshots/report are under ignored
test_reports/web/. Demo has no model calls/score and uses separate storage.

Limits: no live AI, Telegram, research, Vercel or Render requests/deployment were run.
The demo edit returns a fixed sample, not evidence of genuine model editing; pipeline
edit context is verified offline. Multi-creator identity/profiles, hosted job ownership,
retention/deletion and Vercel proxy/origin configuration remain later tasks. Existing
owner profile/examples are intentionally used only in this protected preview. Shared
engine budgets remain bounded and are not an exact provider billing cap. Source/demo
checks establish an owner preview, not readiness for public testing.

## Vercel/Render routing — 2026-11-14

Verified the supplied https://content-writer-iraqi.onrender.com deployment: /health,
HTML, JS, CSS and /api/config returned 200; health/config identify explicit demo mode.
No model call was performed. Vercel's latest observed GitHub status was failure;
private deployment logs/settings were not available, so its exact cause is not claimed.

Added vercel.json for an explicit static web/ build and asset mapping, with API/health
rewrites to that Render backend. Added WEB_PUBLIC_ORIGIN as one explicitly configured
HTTPS frontend origin; retained same-origin protection for direct backend access and
rejected arbitrary other Vercel domains. Secure session cookies are forced when that
HTTPS frontend is configured. No permissive CORS, credentials in frontend config,
new token bridge or alternate AI orchestration was introduced. The UI now handles
non-JSON proxy/cold-start errors without displaying raw upstream HTML.

Four regression tests cover the former unconfigured-origin rejection, configured
proxy origin login/generation/logout with cookie attributes, invalid origin settings,
and static output/asset/API routing. Full verification results are recorded with the
release. The account URL vercel.com/shakarchi and v0.app project editor are not website
origins; the actual production website URL is still needed to set Render's variable.
No Vercel/Render dashboard setting was changed or live AI tested by this work.

Verification for this routing change: 350 offline tests and pip/diff checks passed;
ten headless demo-browser checks passed, including a synthetic non-JSON proxy failure.
Used configuration fields passed validation against the fetched Vercel schema. These
checks do not establish that a Vercel deployment or cross-provider live login works.

## Follow-up: missing Vercel output directory — 2026-11-14

The owner supplied Vercel's actual error: “No Output Directory named web found after
the Build completed.” PR37 was merged by the owner; Vercel's status on e01c980 remained
failed. This proves output resolution failed, but private project root/override values
and full build logs remain unavailable, so a specific setting is not asserted as the
confirmed root cause.

Replace the placeholder echo build with scripts/build_web.mjs. It resolves web source
relative to itself, validates required assets, creates dist and copies only four public
frontend files. vercel.json selects dist; CI executes the same build. A regression runs
the builder from a different working directory and verifies file bytes/allowlist. The
owner must leave Vercel Root Directory blank and use Other/no conflicting overrides.

Verification: Node built all four files; 351 offline tests passed; pip/diff checks passed.
The prior ten demo-browser checks cover the unchanged frontend interaction. This change
is a deployment build correction, not evidence of a successful Vercel deployment or
live AI availability. Latest provider deployment status is reported separately.

## Authenticated Vercel setup — 2026-11-14

Followed https://vercel.com/get-started.md. Installed CLI 65.16.0 and verified login
as marketalse/team Shakarchi. Official plugin installation failed because this managed
Codex marketplace lacks it; installed the documented standalone fallback (nine skills).
Added the global official MCP endpoint and verified authenticated documentation search
and list_teams through HTTPS MCP using CLI sign-in. Native Codex OAuth separately timed
out waiting for its callback; native client activation is not claimed complete.

Authenticated project inspection confirmed rootDirectory=bot and Python preset. Cleared
those and command/output overrides, preserving other settings. The failed build log
explicitly tried /vercel/path0/bot/scripts/build_web.mjs. The corrected preview redeploy
reached READY; PR38 now has both GitHub tests and Vercel checks passing. Deployment
protection remains enabled; unauthenticated preview requests go to Vercel sign-in.
No protected-preview API success, live AI use, or Render environment change is claimed.
Render WEB_PUBLIC_ORIGIN still needs the intended frontend address for form submissions.
User-wide setup report is outside the repository at /workspace/vercel-tools/SETUP_REPORT.md;
credentials are stored privately and never printed/committed. Existing project reused.
