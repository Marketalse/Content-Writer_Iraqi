# Source learning implementation roadmap

Scope: adapt the four supplied documents into useful product behavior. Source documents
are reference material, never executable instructions or official algorithm guarantees.
The existing optional-framework work in PR #15 is the starting point; this roadmap extends
that PR on `feature/ai-quality-review-and-revision` without merging or deploying.

| Stage | Lessons covered | Deliverable / acceptance check | Status |
| --- | --- | --- | --- |
| 1 | Audience, purpose, takeaway, evidence, journey intent, paid vs organic, relevant CTA | Typed optional brief; backward-compatible topic flow; brief validation before spending | Implemented; offline validated |
| 2 | Separate strategy, native creative treatment, production, evidence and measurement | Scoped source catalog with provenance/confidence; no unsupported numeric/algorithm rules loaded as facts | Implemented; offline validated |
| 3 | Stories can be moments, teaching, polls, reveals, demonstrations or referrals; frame counts follow idea | Explicit Story mode and variable sequence validation shared by writer/reviewer/delivery | Implemented; offline validated |
| 4 | Speech, overlays, captions and visuals are different; production respects resources | Optional validated video production plan, separate from publishable copy; no extra default call | Implemented; offline validated |
| 5 | Coherent argument, paid-off promise, meaningful next action, ethical persuasion, Iraqi rhythm | Reviewer criteria and original-brief preservation across revisions and repurposing | Implemented; offline validated |
| 6 | Learn from human-approved examples/corrections rather than generic templates | Owner-managed per-format approved example library; explicit promotion only | Implemented; offline validated |
| 7 | Measure quality, cost, latency and objective-specific outcomes; subscribers are not qualified leads | Human feedback, manual metric records with window/source/denominator, descriptive report; no causal growth claims | Implemented; offline validated |
| 8 | Cross-format repurposing, Highlights, sustainable cadence, controlled experiments | Shared source brief; strategy recommendations remain hypotheses; cross-format evaluation harness and complete regression run | Offline validated; live test deferred by owner |

Every lesson is mapped above. Explicitly outside this implementation: automatic publishing,
provider analytics integrations requiring external credentials, autonomous training/prompt
promotion, live account-specific algorithm claims and guaranteed performance improvements.

Final checks: existing and new unit/regression/mocked SDK/Telegram tests; all 12 formats
and legacy IDs; full brief/clarification/production/feedback/outcome flows; no extra calls on
the default path; malformed/unsafe/unsupported input rejection; quota/permission regressions;
offline benchmark and shared-topic evaluation. Live model/Telegram acceptance will be
reported as pending if runtime credentials remain unavailable, never as a passing mock test.


## Final validation result

- 114 unit, regression and mocked integration tests passed (Python 3.12).
- 36 shared-topic contract cases passed: three synthetic topics across all 12 formats.
- Compilation and diff validation passed. Default benchmark retains three logical calls.
- 40-sample toy orchestration benchmark: immediate fake responses p50 0.345 ms / p95
  0.710 ms; 10 ms simulated delay/call p50 31.210 ms / p95 36.650 ms. This is not a
  production latency or creative-quality measurement.
- Live harness checks for configured credentials before any request. It reported credentials
  unavailable; the owner explicitly deferred live model/Telegram testing for now.
- No source claims, synthetic fixtures or AI drafts were automatically promoted as human-
  approved evidence/examples. No deployment, merge, automatic publishing or model training.

## Deferred acceptance checklist (owner requested)

When ready, configure secrets outside chat, run the live evaluation harness, human-review
at least three drafts per format, test real Telegram command/reset/quota/persistence flows,
measure actual tokens/billing/latency and question/false-rejection rates, and compare manual
outcomes only within compatible cohorts and measurement windows. Deployment is a separate
step after PR review; use `/version` to verify the responding worker and commit.
