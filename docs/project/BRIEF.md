# Product brief and MVP

## Problem and vision

Iraqi creators need scripts that sound natural, make useful points, and respect the intended
format. Generic generated copy and repeated manual rewriting consume time. The vision is a
web writing workspace with each creator's approved voice. Current code is an owner preview
with a shared owner voice; independent creator personalization is future work.

Primary first user: the repository owner creating Instagram Stories in Iraqi Arabic.
Success means the owner can use a reviewed script with small edits and understands why a
request was blocked. Publication stays manual.

## MVP user journey

1. Owner signs into the protected preview.
2. Enters one topic and chooses a Story treatment.
3. Engine clarifies ambiguity or researches factual claims when needed.
4. Writer generates a native Story; deterministic checks and independent review run.
5. Bounded repair happens when justified. Unsupported or failed output is withheld clearly.
6. Owner reads copy and separate sources, requests a reviewed edit, then copies the result.
7. Owner reopens history; after a restart unfinished work is marked interrupted.

## Scope decisions recommended for this recovery

| Keep active | Defer until Story acceptance | Preserve as existing compatibility |
|---|---|---|
| One owner, Instagram Story, topic + treatment | Creator accounts and Supabase migration | Telegram commands and topic library |
| Shared approved owner voice | Multi-voice onboarding and example pooling | Existing Reel/Post/LinkedIn engine routes |
| Existing research/review and bounded repairs | More providers, plugins, formats, auto-publication | Existing learning/production modules |
| History, edit, clear failure, spend measurement | Billing, growth analytics, broad beta | Existing knowledge and style rules |

This reduces active work; it does not delete previously implemented features.

## Proof-of-concept approval criteria

Proposed owner acceptance gate, separate from the larger existing beta targets:

- Run 10 controlled real Story requests: 4 subjective/everyday, 3 educational, 3 factual
  requiring verifiable sources. Include owner examples that previously failed.
- At least 9/10 complete appropriately: accepted output OR justified clarification/withholding.
  Also require at least 8 usable accepted scripts; otherwise a system that withholds everything
  could incorrectly pass. Record both rates and reasons.
- Owner rates at least 8/10 scripts at 4/5 or better for voice and usefulness; blocked cases
  count as not usable. Verify factual output against the linked source and date/applicability.
- Every displayed script passes existing mandatory review gates. Never lower gates to pass.
- Complete one edit, history reopen, duplicate submit and restart/recovery check.
- Confirm protected access, bounded calls/cost, and server-only secrets. No unresolved critical
  privacy/factual defect. Save request IDs, deployed commit, scores, time and actual cost safely.
- Owner explicitly records pass/fail and the next decision in the tracker.

These thresholds are a proposed small PoC gate, not a claim that quality has been measured.
Before running paid cases, the owner sets an explicit total test budget in provider settings;
per-request application budgets are not a hard account billing cap.

## Definition of a feature

One user outcome + one acceptance criterion + one owner + one dependency.
“Improve AI” is too broad. “Owner can edit an accepted Story and reopen the reviewed result”
is a testable feature. Every new idea must explain how it helps the current user journey.
