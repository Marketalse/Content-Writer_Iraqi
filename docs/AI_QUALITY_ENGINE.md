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

Factual integrity, safety, topic preservation and voice preservation are mandatory
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
