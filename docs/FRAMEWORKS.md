# Optional copywriting frameworks

This adapts selected ideas from the supplied `FRAMEWORKS.md`. The attachment referenced
an external TOML and service implementation that were not supplied. Definitions below
are local editorial choices, not a reproduction of that implementation, its owner's
mapping, its prices, or its word limits.

## What is implemented

`knowledge/frameworks.toml` contains PAS, BAB, FAB, AIDA, QUEST and ACCA, their internal
planning steps, content-purpose permissions and independent permissions for all 12
formats. Python's standard-library `tomllib` loads and validates the registry; there
is no new dependency. Update TOML and restart the worker to apply configuration changes.

| Format | Permitted optional tools |
| --- | --- |
| Instagram Story / TikTok Story | None |
| Instagram Instants | None |
| Instagram Live | None |
| Instagram Broadcast | None |
| Instagram Reel | PAS, BAB, FAB, AIDA |
| TikTok Video | PAS, BAB, FAB |
| Instagram Post | PAS, FAB, AIDA, BAB |
| Instagram Carousel | QUEST, ACCA, BAB, FAB |
| TikTok Photo Carousel | BAB, FAB |
| LinkedIn Post | PAS, BAB, QUEST, ACCA |
| LinkedIn Article | QUEST, ACCA |

The format permission is only the first filter. The analyst identifies the audience's
actual need and content purpose, then may choose a framework allowed by both. For example,
a product post may use FAB, whereas a LinkedIn case study may use BAB. A short video is
not automatically an ad. Every format can choose **none**. Unknown purposes become neutral
`unspecified`, not Educational; unknown/disallowed frameworks become `none`, not the first
choice. An intentionally empty routing list is valid.

The existing analyst call returns a bounded JSON plan: audience need, objection, purpose,
optional framework, short logic chain and optional missing-fact/question pair. The writer
receives the validated plan and only the chosen framework's steps. It receives no mandatory
framework headings, fixed point count, shared word limit or forced formal connectors.
Moment/caption/community logic chains have at most two links; developed pieces at most
four. These links are internal reasoning, never an instruction to print a numbered list.

Native contracts remain authoritative. Writer and revision prompts keep this priority,
and the independent reviewer retains all factual/safety/format-identity gates. The 4Cs
(clarity, concision, compelling value and credibility) are criteria across existing review
dimensions, not a new output layout or another model call. Revision receives the same
planning notes while preserving the original brief and verified facts.

## Missing information and clarification

A model confidence number does not decide whether the bot writes. The analyst asks one
focused Iraqi Arabic question only for an essential missing fact, such as an actual case
study result or a price explicitly requested in an offer. A short educational topic can
still be drafted. Invented statistics, quotations, experience and results remain prohibited.

For a valid clarification request, the pipeline returns `needs_clarification`, with no
writer/reviewer calls and no draft. Telegram asks the question and keeps the original topic,
format and angle in chat memory. The next reply is attached to that brief. Only one
clarification round is allowed; unresolved essentials after the answer are blocked rather
than starting a question loop. `/format`, new format/angle selection, or `/cancel` clears
the pending question. This chat state is in memory, like existing format selection, and
does not survive a worker restart.

Analyst cost is logged under a `clarification` usage event. It consumes dollar allowance
but not post allowance and cannot be marked published. Actual drafting retains the
existing generation accounting. No external content page or draft is saved for a question.
The batch CLI records the question as `needs_clarification` in its index; the single-run
CLI prints it. CLI callers can pass `clarification_allowed=False` for a noninteractive run.

## Failure and resource behavior

Malformed, refused or truncated plans fall back to neutral planning, without forwarding
raw malformed text or making a repair call. The writer and independent reviewer still
apply mandatory gates. Invalid TOML configuration fails before model calls.

The analyst output cap increases from 400 to 600 tokens to accommodate structured planning.
All existing per-call/total deadlines, input limits, output reservation limits and cost
stops still apply. Normal acceptance uses three logical calls; a surgical revision uses
up to five; a clarification uses one. `QUALITY_ANALYST=false` disables analyst planning
and retains the two-call writer/reviewer path. More input/output tokens can increase cost
within the same call count; no efficiency or growth improvement is claimed without a pilot.

The selected framework, purpose and fallback flag are logged with the generation metadata.
Stage timings now include input character counts and requested output token limits.
`/version` source fingerprints include the planner and framework TOML.

## Verification

- 84 tests pass, retaining all 68 earlier regressions.
- New tests cover format/purpose intersections, neutral fallbacks, malformed JSON,
  configuration validation, short-format planning, 4Cs review policy, unchanged call counts,
  missing-fact early exit, one-round clarification, original-brief preservation, reset behavior,
  and separate post/cost quota accounting.
- Compilation and `git diff --check` pass.
- Offline benchmark, 40 samples per scenario, three calls/run: immediate fake responses
  p50 0.540 ms / p95 1.670 ms; 10 ms simulated delay per call p50 31.265 ms / p95 31.970 ms.
  The toy benchmark uses a minimal writer prompt; it does not measure production tokens,
  model latency, real cost or creative improvement. Run `python scripts/benchmark_quality.py`.

Live model/Telegram evaluation remains necessary. Compare human-rated coherence, native
character, unnecessary-question rate, factual rejection rate, tokens and latency with a
baseline before extending the library. PASTOR, StoryBrand, Star-Story-Solution, SLAP and
ambiguous 4Ps/PPPP variants are deliberately not added without an agreed use and definition.
