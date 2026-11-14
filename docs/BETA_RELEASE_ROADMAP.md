# Roadmap to a creator-tested release

Updated: 2026-11-14. Reviewed application baseline: `0eb04d6`.
Status: working prototype; integration and live acceptance validation required before closed beta.
This document defines the beta roadmap. Current implementation evidence and task status
are tracked in [PROJECT_EXECUTION.md](PROJECT_EXECUTION.md). M1 owner web preview now
has offline/browser-demo verification; live acceptance and later milestones remain pending.

## Web interface direction — assessment update

The creator prefers the earlier Content Workshop browser interface. Static review
of that repository at ec65d20 found reusable creation, progress, structured-results,
library and feedback screens. Recommended direction: adapt those screens as the
primary interface around the current shared writing engine; retain Telegram as an
optional channel. Its local single-user HTTP server is not a hosted account backend.
See [reuse assessment](WEB_INTERFACE_REUSE_ASSESSMENT.md) for concrete reuse decisions,
policy conflicts and migration slices. Integration is not implemented or live-tested.
R1 should now establish the web journey/application boundary; R2 adds creator-owned
voice profiles. Authentication and isolation are prerequisites for independent testers.

## Product promise

A creator provides a topic, chooses a writing treatment, platform and feature, and
receives a readable, structured script that reflects their saved voice.
The bot handles structure, research decisions, drafting, bounded editing and checking.
The creator should not need to understand prompts, reviewer gates or diagnostic JSON.

Distinguish these concepts in both the interface and code:
- Creator voice: vocabulary, rhythm, directness, humor, approved examples and dislikes.
- Writing treatment: how-to, opinion, story, question, problem/solution, etc.
- Destination: platform plus its supported feature, such as Instagram Reel.
- Script structure: an internal progression selected to fit those choices.

## Where we are now

| Area | Observed today | Release gap |
|---|---|---|
| Core generation | Structured writer fields, validation and Telegram delivery implemented | Validate the whole experience with real creators |
| Navigation | Current layers plus legacy callbacks and optional commands coexist | One clear primary journey; internal structure should normally be automatic |
| Voice | Shared owner voice file; shared owner-approved examples | Per-creator onboarding, versioned profiles and isolation |
| Research | Claim routing, search and evidence checks implemented | Live source/date checks and explicit handling when research is unavailable |
| Quality | Independent review; score target 7.5, dimension floor 6; up to two revisions | Calibrate against human judgment and recover appropriately from repairable gate failures |
| Recovery | Format repair, fresh drafts, failure advice and provider fallback exist | One consistent recovery policy; voice uncertainty currently stops before editing |
| Topic library | 145 mapped ideas: 137 defined/unused, four held, four used | Keep optional; separate the owner's topics from other creators' private work |
| Session state | Menu/brief selections held in chat memory; attempt history stored | Restart recovery, request identity and duplicate-start handling need release validation/design |
| Provider fallback | Anthropic to Nous implemented; search capability differs | Exercise actual deployed failure paths and communicate missing capabilities |
| Feedback | Feedback/results commands and owner-approved examples exist | Simple creator feedback tied to their request and profile; no automatic global learning |
| Engineering checks | 332 offline tests pass; latest recorded main CI passed | Live smoke tests, human voice acceptance and deployment verification outstanding |

No percentage-complete estimate is given: live success, voice-match and latency rates
have not been measured. Existing functionality does not establish release readiness.
The original November 10 failure register is historical; it is not an up-to-date list
of unfixed defects. Its ten audit groups have subsequent regression coverage.

## Recommended first beta scope

Invite 5–10 Iraqi Arabic content creators. Start with Instagram Story, Reel and Post
(single image/carousel), promoting only routes that pass acceptance testing. Preserve
other implemented routes but keep them outside the default beta menu until evaluated.
This is proposed scope, not a change already applied to the bot.

Keep: topic entry, saved voice, compatible platform/feature choices, simple treatment
selection, research when justified, readable scripts, targeted edits, feedback and
clear recovery messages. Keep the topic library optional.

Defer: additional providers, public registration, bulk generation, advanced analytics,
new channels, scheduling/publishing and additional coding-tool installations.
Live outlines and other platforms can follow after the core journey is stable.
Python remains suitable; this review found no evidence that changing language would
solve the observed editorial/reliability problems.

## Milestones and completion checks

| ID | Status | Work in execution order | Complete when |
|---|---|---|---|
| R0 | Baseline reviewed; scope proposed | Freeze feature additions, record deployed version/settings, agree beta routes and failure categories | One release checklist and an explicit scope; Render version matches intended commit |
| R1 | Planned | Unify the creator journey and selection state | Topic → treatment → compatible destination → preview/generate works through one primary path; no conflicting selections or stale starts |
| R2 | Missing per-creator capability | Add saved voice onboarding and profile isolation | Three to five supplied samples produce an editable voice summary; creator confirms it; writer, editor, reviewer and adviser use the same profile version |
| R3 | Partial implementation | Consolidate research, quality and recovery policy | Each failure takes its intended bounded action; no unchanged retry loop, unreviewed delivery or weakened factual/safety gate |
| R4 | Partly implemented; live validation pending | Make sessions, provider failures and release operations dependable | Restart/duplicate/fallback tests pass; clear user outcomes and operator diagnostics agree; deployed smoke tests pass |
| R5 | Not started | Run a fixed evaluation pack and calibrate human/model review | Candidate meets the proposed release gates below, with all failed cases recorded and retested |
| R6 | Not started | Run a seven-day invited beta, then decide whether to expand | Feedback, incidents, costs and human acceptance are reviewed; recurring blockers are fixed before broader testing |

R1 and R2 come first. Evaluate each vertical slice from Telegram input to output;
do not wait until every module has been changed before checking integration.
Do not replace the existing orchestration or introduce a multi-agent framework unless
an observed, measured limitation requires it.

### R1 — One understandable journey

1. Let the creator enter their topic first and retain it while choosing options.
2. Separate voice identity from treatment; show compatible platform/feature options.
3. Select the script progression automatically; expose advanced controls optionally.
4. Show a concise request summary before spending; allow correction without losing topic.
5. Use one validated request record across writing, revision, advice and delivery.
6. Keep old buttons compatible through the same validation path; remove conflicting
   documentation and entry points as part of the migration.

Test: new/repeat user, every beta route, Back/Cancel, changed selection, old buttons,
manual topic/library topic, adviser selection and duplicate confirmation.

### R2 — Each creator's voice

1. Collect creator-provided examples and explicit dislikes; distinguish real personal
   experiences from style examples that must not become claims in new content.
2. Save a creator-scoped profile and confirmed summary, with a profile version.
3. Pass that same version to all content-producing/checking stages, including advice.
4. Let creators correct the profile and remove their examples. Persist across restarts.
5. Scope examples and topics to their owner. Make any public sample library explicitly
   shared and opt-in; never default new creators to the owner's private examples.

Test: two deliberately different voices, separate chats, restart, profile change,
correction/deletion and no cross-creator access. Human approval is the voice benchmark;
a model gate cannot establish a 100% match on its own.

### R3 — Recover according to the actual problem

| Observed problem | Intended action |
|---|---|
| Missing essential topic detail | Ask one targeted question and retain the request |
| Current regulation, rate, statistic or checkable premise | Retrieve relevant dated evidence, prefer official sources where required, and distinguish dates/jurisdiction |
| Research cannot support a claim | Request a source/clarification or offer an explicitly changed angle for creator confirmation |
| Unambiguous heading decoration | Normalize without changing the content |
| Missing field, excessive length or wrong native layout | One targeted structural repair, then validate and independently review |
| Low creative score or repairable voice mismatch | Edit using specific evidence/examples; use a fresh draft if an edit stalls; recheck the actual final artifact |
| Uncertain voice/format review | Obtain an actionable explanation and apply a bounded repair where justified; do not convert uncertainty to pass |
| Unsafe content or unresolved factual failure | Withhold affected output and explain the required change |
| Provider credit/auth/rate/connection issue | Use an eligible configured fallback; otherwise show the actual service category, not “bad topic” |
| Budget/revision limit reached | Stop clearly; offer existing related-topic advice only when eligible and affordable |

Start with the existing bounded limits rather than infinite “until pass” retries.
Measure whether budgets leave room for useful repair/advice before changing them.
Opus remains limited to failed-content topic advice. Choosing its suggestion re-enters
the normal workflow; the adviser must not become a general writer or automatic pass.

### R4 — Dependable operation

Persist the request/profile/selection needed to resume safely. Define retry and
idempotency behavior so the same Telegram action does not trigger duplicate paid work.
Verify per-creator authorization, quotas and data deletion. Treat provider capability
and billing failures separately from quality failures. Preserve concise user messages
plus safe operator codes and request references. Keep technical JSON in diagnostics.

Verify Render's running commit, storage and one polling consumer; exercise provider
and research failures in a controlled environment. Check main CI/deployment gating,
rollback to a known-good release, redacted logs and restore procedures. No need to
add a third provider before the current two paths are validated.

### R5 — Measure readiness

Create a fixed pack of at least 60 requests spanning beta features, distinct voice
profiles, treatments and factual/nonfactual topics. Include previously reported failures:
Nous malformed output, truncated analysis, voice uncertainty, format uncertainty,
weak revisions, source/date conflicts and suggestion-to-generation continuation.
Test format compliance deterministically and voice/usefulness with people.

Proposed gates for an eligible, supported request set:
- At least 95% complete without an unhandled application or transport failure.
- At least 90% of ordinary supported requests reach a reviewed deliverable within
  the agreed bounds. Log legitimate content blocks separately; never weaken gates
  to increase this number.
- At least 80% of creator assessments rate both voice and usefulness 4/5 or higher.
- Every delivered script has the required final checks; no known critical source,
  privacy, safety or wrong-creator-voice incident remains open.
- Every observed failure has an understandable user outcome and request reference.
- Measure end-to-end latency and cost (including repairs, fallback and advice).
  Set and record p95 targets and affordable per-request/daily limits before live beta.
- No unresolved high-severity defect; every fixed recurring failure has a regression case.

These are proposed acceptance targets, not measured current results. Offline test
passes alone do not satisfy them. Provider availability is external, so the release
must handle outages clearly rather than promise zero failures.

### R6 — Invited testing

Give 5–10 creators a short onboarding guide and allow a small daily quota. Run for
seven days with a named maintainer and pause/rollback procedure. Gather one-click
ratings for voice, structure and usefulness plus optional corrections. Avoid forcing
creators to inspect diagnostics to report a bad script.

Review rates and failure categories daily. Fix the most frequent underlying cause,
add its regression case and rerun the evaluation pack. Broaden access only after
release gates are met. Do not optimize for FQS alone if creators reject the output.

## Progress reporting

Maintain this milestone table with status, evidence and the deployed commit. For each
implementation PR, record what failed before, what changed, checks performed and what
remains unvalidated. Keep automated CI reports for engineering checks and a separate
human evaluation log. Markdown does not update itself; automatic metrics need explicit
collection/reporting implementation.

## Immediate next execution slice

R1: document one request schema and acceptance journey, reproduce selection/state
failures, unify the main route, then prove one complete Story and Reel journey.
R2 follows with creator-owned voice profiles before inviting independent creators.
This was the planning baseline; see PROJECT_EXECUTION.md for subsequent implementation progress.
