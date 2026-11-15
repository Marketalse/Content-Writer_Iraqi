# Get this project on track

Reviewed baseline: `main` at `2ebfc52`, 15 November 2026 (Baghdad).

**Product:** help an Iraqi Arabic creator turn one topic into a useful, reviewed script that sounds like them, then edit and copy it for manual publication.

**Do first:** prove the existing single-owner Instagram Story journey with real outputs. Finish M1 live acceptance before creator accounts, more formats, pooling or more tools.

## Read in this order

1. [Brief and MVP](BRIEF.md): user, problem, vision, scope and proof-of-concept gates.
2. [What happened to main](MAIN_HISTORY.md): dated evolution and evidence.
3. [System and repository map](SYSTEM_MAP.md): code, logic, storage, knowledge and skills.
4. [Roadmap](ROADMAP.md): dependencies, relative timeline and decision gates.
5. [Kanban cards](KANBAN.md): actionable tasks, owners and acceptance criteria.
6. [Developer workflow](DEVELOPER_WORKFLOW.md): setup, environment, tests and daily routine.
7. [Tracker CSV](tracker.csv): portable task source; import/map columns into your chosen board.

The existing [execution board](../PROJECT_EXECUTION.md) retains historical M1 checklists.
This recovery plan sets the current priority order. Existing feature documents remain reference
material; they do not authorize adding every proposed feature. The in-app progress screen
is a manually maintained snapshot, not a live task manager.

## Current evidence

- 355 offline tests passed on Python 3.12.14 at the reviewed baseline.
- Dependency consistency, static frontend build and audit verification passed.
- 10 local desktop/mobile demo browser checks passed; zero paid model calls.
- Public Render `/health` reported demo mode; Vercel health/config requests timed out
  from this environment. Authenticated production behavior remains unverified.
- Supabase creator tables are a proposal, not an applied database or working account system.
- Live provider output, model availability/pricing and authenticated production generation
  require separate verification. Unit tests use fixtures/mocks.

## Operating rule

Keep one task in progress. A new feature goes into Backlog until the current gate passes.
Move a card to Done only when its acceptance evidence is recorded. A blocked live test is
Blocked, not Done. The owner decides product priorities and approves output quality;
the coding assistant implements small changes and supplies test evidence.
