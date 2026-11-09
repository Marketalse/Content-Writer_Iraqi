# Phase 2 — AI Content Quality & Revision Engine

Implemented on `feature/ai-quality-review-and-revision`. Human review is still required
before publication. Nothing in this engine publishes content or promises growth.

## Architecture audit

The repository contains a polling Telegram app, synchronous JSON/JSONL pilot state,
a platform registry, a knowledge-driven writer prompt, CLI/batch entry points and one
LLM transport module. The ZIP in `knowledge/` is a source export, not runtime code.
There are no additional dependencies for the engine.

Before this change:

- `pipeline.py` called an analyst, a structurally checked writer and a dialect guard.
  Both retry paths asked for a rewrite without providing the previous draft.
- The dialect rewrite was never reassessed for dialect. Critical factual and safety
  issues had no explicit assessment contract. Failures were delivered with a warning.
- `quality.py` enforced native format labels but missed duplicate/order/empty-slide cases.
- Refused or empty runs returned before cost logging. Allowlisted users could pass the
  Telegram permission check but fail the separate pilot check.
- The SDK could retry internally, truncation was not exposed, and fallback usage had
  no accounting. Long HTML chunks could grow after escaping or split markup.
- Post IDs used second precision and could collide. CI only watched selected modules.

## Modules and contracts

- `reviewer.py`: seven dimensions, 12 distinct editorial criteria and weighting profiles;
  strict JSON scores, gate outcomes and section-specific feedback. Weighting and criteria
  are local editorial hypotheses. They are not official ranking factors.
- `revision.py`: validated settings, per-run budgets, timeouts, strict section parsing,
  deterministic patch application and independent reassessment.
- `pipeline.py`: retains `Run`, token/cost properties and the four positional arguments.
  Optional keyword arguments accept settings and trusted `(fact_text, provenance)` pairs.
- `quality.py`: retains `check`, `split_owner_note`, `Checked` and `generate_checked`.
  The latter delegates to the same bounded engine, without a separate analyst call.
- `llm.py`: remains the only provider transport. SDK automatic retries are disabled;
  existing fallback eligibility (connection errors, 429, 5xx) is retained. Truncation,
  refusal, cache usage and known/unknown pricing are explicit.
- Telegram: existing commands and callbacks remain. Accepted drafts are delivered in
  plain-text chunks bounded to 4,000 UTF-16 units. Owner notes remain separate.
  Every completed pipeline run is logged before delivery, including unsuccessful runs.

`Checked.status` is one of:

| Status | Meaning | Telegram delivery |
| --- | --- | --- |
| `accepted` | Native structure, all AI gates pass, weighted score and dimension floors pass | Draft text and manual publication reminder |
| `blocked` | Structural/truncation failure, missing verified fact, or failed/uncertain gate | Withhold content; explain failed checks |
| `needs_review` | Low creative score or incomplete assessment/resource limit | Withhold content; explain failed checks |

Metadata includes per-attempt score history, dimension scores, gate decisions, section
issues, stage durations, total elapsed time, calls, tokens and estimated cost. Draft text
remains available in `Run.checked.text` for trusted CLI callers; it is not newly stored
in JSONL. This release does not introduce an approval queue or a Telegram fact-verification UI.

## Review and revision policy

Scores: hook, storytelling value, platform fit, audience relevance, Iraqi dialect,
CTA effectiveness, originality. Instants do not require an artificial CTA. Articles
emphasize evidence and useful analysis; videos emphasize an honest opening and payoff;
Stories emphasize immediacy and interaction. Standard Arabic words without a dictionary
replacement are allowed. Natural voice matters more than artificially inserting letters.

Factual integrity, safety, topic preservation, voice preservation and format identity are mandatory
`pass` / `fail` / `uncertain` gates. No creative score overrides a failed or uncertain gate.
Uncertain or failed critical gates go to human review, rather than asking a model to
cosmetically erase a factual/safety objection. Invalid native structures also stop early,
saving reviewer calls. A caller can correct the brief and generate again.

An under-threshold draft with actionable feedback can receive one section patch by default.
The revision prompt includes the exact original draft, current sections, original topic,
angle, verified facts and feedback. A patch may only replace named weak sections; unlisted
section bodies are copied deterministically. New headers, empty replacements, new sections
and malformed patches are rejected. The resulting draft is structurally checked and independently
reviewed again. No-op/non-improving reassessments do not trigger further revisions.

Verified fact text must remain verbatim in every candidate. The reviewer also checks meaning
and consistency. A provenance string is caller-supplied evidence metadata, not external
verification. Ordinary brief facts remain explicitly user supplied. Analyst notes and voice
examples are style/context, never evidence. Counts, list numbering and hypothetical examples
are not automatically treated as empirical claims. There is no blanket numeric ban.

## Configuration

All settings are optional environment variables, read per run. Invalid values fail before
calls. Hard validation ceilings prevent accidental unlimited settings.

| Variable | Default | Allowed |
| --- | --- | --- |
| `QUALITY_THRESHOLD` | 7.5 | 0–10 |
| `QUALITY_DIMENSION_FLOOR` | 6.0 | 0–10; every positively weighted dimension |
| `QUALITY_MAX_REVISIONS` | 1 | 0–2 |
| `QUALITY_MAX_CALLS` | 5 | 1–7 logical transport calls |
| `QUALITY_TIMEOUT_SECONDS` | 120 | 1–300 total deadline |
| `QUALITY_CALL_TIMEOUT_SECONDS` | 45 | 1–120; also bounded by remaining total deadline |
| `QUALITY_MAX_COST_USD` | 0.25 | 0.001–1; stop before next call at observed estimated spend |
| `QUALITY_MAX_INPUT_CHARS` | 100000 | 1000–150000 per combined system/user request |
| `QUALITY_MAX_TOTAL_OUTPUT_TOKENS` | 15000 | 100–30000; reserve requested maxima before calls |
| `QUALITY_WRITER_TOKENS` | 4000 | 100–8000; also applies to revision patches |
| `QUALITY_REVIEW_TOKENS` | 1800 | 100–3000 |
| `QUALITY_ANALYST` | true | true/false; false saves one call |

Defaults: 3 logical calls for an accepted first draft; up to 5 with a revision. Without
analyst: 2 or 4. A failing structural check skips the reviewer. A call may attempt the
configured fallback once; therefore provider attempts can exceed logical calls. No SDK
automatic retries occur. The session timeout covers primary and fallback together.

The dollar threshold is an **observed-cost stop**, not a prepaid billing cap: the current
request may cross it, and cancellation cannot guarantee that a provider did not bill a
request. Input size, requested output tokens, call count and timeouts provide separate
bounds. Existing model prices are estimates and must be checked against actual billing.
Unknown model/fallback pricing stops subsequent calls. Tokens from fallback responses are
retained when available; unknown cost is never represented as a known free call.

Pilot preflight retains the $0.25 reservation. Usage includes all completed generation
attempts, even refusals/blocked drafts. Incomplete or unknown usage reserves at least
$0.25 against the pilot quota through `quota_cost_usd`, separately from measured
`cost_usd`. Reconcile reservations against provider billing. Owner/allowlisted access
remains unlimited. JSON files assume a single Telegram worker; multi-process atomic
reservations require a transactional store before horizontal scaling.

## Verification — 2026-11-08

Python 3.12, installed repository requirements, no live credentials:

- `python -m unittest discover -s tests -v`: **52 tests passed**, 1.338 seconds.
- `python -m compileall -q bot tests scripts`: passed.
- `git diff --check`: passed.
- Existing eight format regressions retained. Additional cases cover all formats/legacy
  routing, schema rejection, weighted thresholds, independent critical gates, targeted
  patches, preserved verified facts, refusal, truncation, timeout/deadline, call/input/output/
  cost limits, unknown pricing, non-improvement, concurrent session isolation, mocked SDK
  transport, Telegram access, callbacks/reset, owner administration, quotas and long delivery.

Run `python scripts/benchmark_quality.py` to reproduce the offline orchestration benchmark:

| Samples | Fake delay per logical call | Calls/run | p50 | p95 |
| --- | --- | --- | --- | --- |
| 40 | 0 ms | 3 | 0.330 ms | 1.860 ms |
| 40 | 10 ms | 3 | 31.050 ms | 32.530 ms |

These measurements isolate local work and simulated waiting. They do not measure real
provider latency, production throughput, factual accuracy, prompt-injection resistance,
dialect quality or growth. No live Anthropic, Nous, Telegram, or load test was performed.
An independent model call can still miss facts or safety issues; it is not a fact-checking
service or a guarantee of safe publication. Originality scoring is not plagiarism detection.

## Pilot rollout and remaining work

1. Keep this change on its development branch for PR review. Do not change Render's
   deployment branch or enable publishing as part of this change.
2. On a separately configured pilot, manually assess at least three outputs per format
   against a human rubric, including ordinary counts, sourced statistics, unsupported
   claims, creator voice, and adversarial instructions inside briefs. Calibrate thresholds
   from false accepts/rejects rather than increasing scores to hide failures.
3. Check real p50/p95 latency, refusal/blocked rate, review JSON validity, revisions,
   cache effectiveness, actual bill and article truncation. Articles can use a higher
   writer cap only within the configured output and cost bounds.
4. Verify existing commands with the real bot and inspect persisted quotas after restart.
   Unit mocks cannot establish deployment health or the availability of configured model IDs.

## Recommended implementation sequence after this engine

1. **Controlled automated improvements:** human-labelled evaluation fixtures and pilot
   calibration first; typed structured draft schemas and deterministic rendering second;
   provenance records and an explicit approval queue next. Extend surgical repair to
   recoverable structural errors only after schema contracts are stable.
2. **Performance analytics:** add platform/format/objective/variant IDs, consent and retention
   policy, then manual outcome capture or verified official analytics integrations. Keep
   reach denominators, windows, sample sizes and data sources. Measure quality, cost,
   cache hits and latency independently of reach.
3. **Experiments:** record hook/CTA/narrative variants within the same platform and format,
   with baselines and comparable measurement windows. Avoid causal claims from correlations.
4. **Continuous learning:** propose changes from human-approved corrections and sufficiently
   supported experiments. Run held-out regressions, cost/latency budgets, canary rollout and
   rollback before promoting prompt/rubric changes. Never silently train on private briefs
   or auto-publish. Publishing API permissions and media constraints remain separate work.


## Format identity correction — native-v2

The shared formula library, general hook library, universal hook/CTA checklist and
cross-format examples created conflicting conditioning. Writer prompts now load
only common voice/dialect/safety material, relevant examples, and the selected
format contract as the final instruction. `bot/format_contracts.py` defines 12
individual creative treatments used by both writer and reviewer. Old universal
caption/three-point format documents are retired or replaced by native references.
The additional `format_identity` gate blocks a generic lesson hidden behind correct
native labels. Explicitly requested lists remain valid when appropriate to the format.

Regression validation: 59 tests pass, including prompt isolation for all 12 formats,
scoped examples, legacy layout rejection, disguised-template gate failure and native
contract preservation during revision. These mocked tests establish prompt/routing
behavior; live creative variety still needs human evaluation.

After merge, deploy the merged commit from `main` and restart the Telegram worker.
Confirm its startup log contains `format_contract=native-v2`. Prompt strings are
built at process startup, so editing files without restarting cannot update a
running worker. A merge alone does not prove that Render deployed that commit.
No deployment branch or publishing integration is changed by this correction.


## Runtime diagnosis and final delivery validation

A reported Story screenshot used the exact retired bilingual emoji headers. The
repository Render Blueprint and deployment guide still named the old
`claude/festive-meitner-3m5y3a` branch; that branch's `bot/prompts.py` explicitly
loads its universal `caption.yaml`. These are confirmed repository findings.
The actual running Render service/commit was not inspected, so this does not
establish which process sent the screenshot.

The Blueprint now targets `main`. `/version` reports the responding worker's safe
build metadata, source and selected-prompt fingerprints, and selected format.
Startup/generation logs and post metadata include matching build identity. Secrets
and prompt contents are never included. Unknown commits are reported as unknown.
The delivery boundary rechecks structural validity even when a pipeline result
claims acceptance, and the exact retired header combination is rejected even if
embedded inside native sections.

Validation: 68 tests passed, including a screenshot-layout fixture, pipeline early
rejection, forced-accepted-result delivery rejection, build identity redaction,
version command permissions and Blueprint branch/start-command checks. Compilation
and diff validation passed. Live Render/Telegram behavior remains unverified.


## Optional framework planning

See [framework configuration, clarification flow and validation](FRAMEWORKS.md).
Frameworks are optional internal planning tools, never shared output templates.
The analyst cap is now 600 tokens. A `needs_clarification` result asks one essential-fact
question before drafting; its usage affects dollar quota but not post quota.

## Reliable review responses (November 2026)

The live attempt `20261109093637-f430fe9b` completed analyst, writer and review calls,
passed native validation, then ended with no saved assessment. Its pre-diagnostics record
cannot distinguish an empty, refused, truncated or malformed review; it does establish
that no valid review was available. No creative or mandatory gate failure can be inferred.

Anthropic documents [Haiku 5.5 adaptive thinking defaults](https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide):
thinking can consume a small output budget before text appears. The project's analyst and
review budgets were small and had no explicit effort control. The provider also documents
[structured JSON responses](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
including exceptions for refusal and token limits. These support the implementation below;
they do not prove which exception happened in the historical attempt.

- Request `output_config.effort=low` for analyst/review calls using the documented Haiku 5.5
  model. Writer/revision calls receive no new effort override.
- Request a stable JSON schema for reviewer scores, every mandatory gate, and weak-section
  feedback on this project's documented Claude Haiku/Sonnet 5.5 API models. The schema
  travels through SDK `extra_body` for compatibility with older SDK argument signatures.
  Unknown model overrides do not receive speculative provider options.
- Keep all local validation: finite scores 0–10, every gate present with a valid value,
  bounded issues and exact section names. Numeric/string bounds unsupported by the API's
  schema subset remain local. Duplicate keys are rejected rather than allowing a later
  `pass` to overwrite an earlier `fail`.
- Keep review feedback compact and the schema stable across topics; this avoids generating
  a new provider schema for every article heading or slide count. Schema characters are
  included in the per-call input budget. API schema compilation can add first-use latency;
  mocked tests do not measure this or prove real editorial quality.
- Keep the configured 1,800-token review default, existing total/cost/time limits, call
  count and revision bounds. No recovery call, hidden retry, fence-stripping acceptance,
  missing-gate defaults or provider-error fallback without the schema was added.
- `QUALITY_STRUCTURED_REVIEW=true` is the default. A deliberate compatibility override
  to `false` changes only the provider request; strict local review validation stays on.
- Store stop reason, thinking-block count, actual structured-output/effort flags and
  per-stage token counts, without storing thinking content. Specific safe parser codes
  identify invalid JSON, review fields, scores, gates, issues and duplicate keys.

Validation includes schema and SDK request checks, synthetic thinking-only truncation,
a real pipeline-to-SDK-boundary replay with three successful logical calls, explicit
compatibility mode, refusal/budget regression cases and local mandatory-gate checks.
Live verification remains necessary: after deploying, generate the same Story once and
inspect the new `/diagnose ID` output if it fails. The older diagnostic record cannot gain
new stop-reason fields retroactively.

Verification for this update: **180 tests passed**, compile and whitespace checks passed,
and 39/39 offline format fixtures passed. The mock orchestration benchmark (40 samples,
10 ms synthetic transport per call) retained three calls: p50/p95 31.82/34.06 ms without a
selected narrative, 31.64/33.74 ms with a selected Story narrative. Mean input characters
across calls were 18,721 and 19,825 respectively, including the schema. These numbers do
not measure live schema compilation, provider thinking, latency, tokens or writing quality.

## User-authorized manual-review drafts and constrained planning

The live Reel `20261109103012-a578eac4` completed five calls and one revision. Both
reviews passed every mandatory gate; its creative score rose from 7.000 to 7.133,
remaining below 7.5. This is a valid quality result, not a reviewer transport error.
The same record confirms an analyst truncation: 600 tokens, a thinking block and no
text, followed by the existing neutral planning fallback.

The user explicitly chose: **show a clearly labeled manual-review draft when all
mandatory gates pass; keep the creative threshold unchanged.**

`QUALITY_SHOW_REVIEW_DRAFTS=true` implements that delivery policy. The final assessment
must pass every factual/safety/topic/voice/format gate. The only outstanding failures may
be creative thresholds or non-improving creative revision, and a fingerprint binds that
assessment to the exact current text and production plan. Any subsequent change invalidates
eligibility. A pending revision without completed reassessment is not deliverable. Native
structure, Story mode/intent and production validity are checked again at Telegram delivery.

Eligible drafts retain `quality_status=needs_review` and the creative failure code. The log
records `delivery_status=manual_review`; accepted and withheld output remain distinguishable.
Every content chunk and associated production-plan chunk carries an explicit unapproved
manual-review warning and score. The bot does not offer `/published` for these drafts, and
the existing publication marker still accepts only engine-accepted records. Human feedback
can be recorded without changing the engine approval state. No automatic publishing or new
manual-approval command was added. Set `QUALITY_SHOW_REVIEW_DRAFTS=false` to restore withholding.

The analyst now requests its own compact, stable JSON schema through the same provider
transport as the reviewer. Required plan fields and short editorial beats fit the existing
600-token allocation; framework/format/purpose permissions and essential-clarification
validation remain local. `QUALITY_STRUCTURED_ANALYST=false` preserves explicit compatibility
mode. Refused, empty, truncated or invalid plans still fall back neutrally without another
AI call; the fixed fallback reason is recorded and available in `/diagnose`.

Validation covers the reported Reel score vectors, all critical-gate failures/uncertainties,
missing/stale reviews, changed production plans, budget-stopped reassessment, strict delivery
mode, labeled long Telegram chunks, final structural gates, preserved publication state,
planner schema/API arguments and one-question clarification. All **196 tests pass**, alongside
39/39 offline format cases, compile and whitespace checks. The normal three-call path and
five-call single-revision path retain their limits. Mock replay does not establish improved
live creative scores or guaranteed planner completion; those need deployment verification.

Updated mock benchmark: 40 samples/scenario, three calls, 10 ms simulated call delay;
p50/p95 31.73/32.52 ms for default selection and 31.60/32.65 ms for selected Story
narrative. Mean input characters across calls: 19,847 / 20,951 including planner schema.
This measures local orchestration only; live schema cold-start latency, thinking use and
creative quality remain to be checked after deployment.

## Isolated format repair

An explicit `format_identity=fail` with every other gate passing and actionable section
issues may use the existing bounded revision slot. The format gate remains mandatory for
both approved and manual-review delivery; no candidate is shown before fresh all-gate
reassessment. Uncertain format, failed/uncertain factual/safety/topic/voice gates, missing
issues and exhausted budgets still withhold. Verified facts remain protected exactly.
`QUALITY_REPAIR_FORMAT=false` preserves the previous immediate-stop behavior. See
[the exact installment-topic test](INSTALLMENT_TOPIC_TEST.md) for evidence and limitations.
