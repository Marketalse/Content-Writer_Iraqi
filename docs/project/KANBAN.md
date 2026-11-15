# Kanban cards

Snapshot: 15 November 2026 (Baghdad). Source: [tracker.csv](tracker.csv). WIP limit: one.

Statuses describe this recovery plan; Done requires evidence, and Backlog means deferred.

## Ready

### CW-03 — Verify protected hosted web configuration

P0 · Owner + assistant · PoC · 1 day

Depends on: CW-01.

Acceptance: Separate Render web service, durable storage, one worker, exact origin, deployed SHA; owner-preview health and unauthenticated 401 verified.

Evidence/blocker: No dashboard credentials or deployment changes in this cleanup

## In progress

No cards.

## Review

No cards.

## Blocked

### CW-04 — Run and rate 10 real Story requests

P0 · Owner · PoC · 1 day

Depends on: CW-02;CW-03.

Acceptance: BRIEF PoC gate met; request IDs, source verification, ratings, time and costs recorded.

Evidence/blocker: Needs protected service, private provider settings and explicit total test budget

### CW-05 — Verify live edit/history/restart/idempotency

P0 · Owner + assistant · PoC · 0.5 day

Depends on: CW-03.

Acceptance: One reviewed edit, history reopen, duplicate submit and restart recovery demonstrated.

Evidence/blocker: Offline coverage exists; live evidence pending

## Backlog

### CW-06 — Fix the most frequent measured Story failure

P1 · Assistant · Reliability · 1–2 days

Depends on: CW-04.

Acceptance: Reproduction, minimal fix and regression; owner rerates failing example successfully.

Evidence/blocker: Choose specific failure from live results; do not speculate

### CW-07 — Measure cost and latency per useful script

P1 · Owner + assistant · Reliability · 0.5 day

Depends on: CW-04.

Acceptance: Record accepted rate, editing effort, p50/p95 latency and actual provider cost; agree targets.

Evidence/blocker: Price tables/model identifiers require live validation

### CW-08 — Record owner MVP acceptance decision

P0 · Owner · PoC gate · 0.5 day

Depends on: CW-04;CW-05;CW-06;CW-07.

Acceptance: Owner records pass/fail against BRIEF gate; unresolved blockers have cards.

Evidence/blocker: CW-06 may be closed with evidence no fix needed

### CW-09 — Review proposed creator schema and isolation

P1 · Assistant · Identity · 1 day

Depends on: CW-08.

Acceptance: Feedback ownership, job states/idempotency, voice versions and two-user isolation defined/tested before migration.

Evidence/blocker: Draft SQL unapplied

### CW-10 — Implement invite-only identity and private jobs

P1 · Assistant · Identity · 3–5 days

Depends on: CW-09.

Acceptance: Backend verifies identity; two accounts cannot read/update each other; history migration and rollback tested.

Evidence/blocker: No public signup

### CW-11 — Implement approved creator voice end to end

P1 · Owner + assistant · Identity · 3–5 days

Depends on: CW-10.

Acceptance: Collect examples; approve version; writer/reviewer/editor/adviser use same private profile.

Evidence/blocker: Do not mix shared dialect with private creator voice

### CW-12 — Verify operations and retention for beta

P1 · Owner + assistant · Beta readiness · 2–3 days

Depends on: CW-10;CW-11.

Acceptance: Durable jobs, quotas, safe errors, restart/rollback, deletion and operator metrics verified.

Evidence/blocker: Remain single process until job ownership supports concurrency

### CW-13 — Run 60-case human acceptance evaluation

P1 · Owner · Beta readiness · 2–3 days

Depends on: CW-12.

Acceptance: Existing beta gates measured: 95% technical completion, 80% human 4/5 ratings; critical issues resolved.

Evidence/blocker: Add one new format only after Story passes

### CW-14 — Run seven-day invited pilot

P2 · Owner · Beta · 7 days

Depends on: CW-13.

Acceptance: 5–10 invited creators; daily feedback/cost/incident review; expansion decision recorded.

Evidence/blocker: Accounts and private voice required

### CW-15 — Evaluate pooled learning proposal

P3 · Owner · Later · Unscheduled

Depends on: CW-14.

Acceptance: Separate consent, scrubbing, withdrawal and deletion demonstrated before any pooling.

Evidence/blocker: Defer; not needed to prove product

### CW-16 — Consider physical Python package reorganization

P3 · Assistant · Later · Unscheduled

Depends on: CW-08.

Acceptance: Only if justified: import checks, one module boundary per PR, deployment compatibility preserved.

Evidence/blocker: Current cleanup maps paths without moving runtime files

## Done

### CW-01 — Record baseline and recovery map

P0 · Owner + assistant · Reset · 0.5 day

Depends on: None.

Acceptance: 355 offline tests, pip check and static build pass; current scope and history mapped.

Evidence/blocker: Baseline 2ebfc52; review 2026-11-15

### CW-02 — Verify local Story demo in desktop and mobile

P0 · Assistant · Reset · 0.5 day

Depends on: CW-01.

Acceptance: Browser smoke checks pass; create/edit/history/demo labels and no mobile overflow.

Evidence/blocker: 10 desktop/mobile browser checks passed in explicit local demo; zero paid model calls, 2026-11-15
