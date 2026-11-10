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
