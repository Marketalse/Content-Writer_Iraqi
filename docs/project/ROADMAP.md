# Recovery roadmap and timeline

This is a proposed relative schedule for a beginner working part-time, not a deadline promise.
Day 1 is when work resumes. A gate can extend the schedule; do not begin the dependent phase
because a calendar date arrived. Track actual start/finish and evidence in `tracker.csv`.

| Window | Phase | Exit evidence | Next phase depends on |
|---|---|---|---|
| Days 1–2 | Baseline and product reset | Local demo works; code/build/tests recorded; scope agreed | Existing baseline |
| Days 3–5 | Owner Story proof of concept | Protected deployment and 10-case owner acceptance | Correct backend/origin/storage and test budget |
| Week 2 | Fix measured reliability issues | Reproduced failures corrected, rerated outputs, costs measured | PoC findings |
| Weeks 3–4, only after acceptance | Creator identity and voice | Two isolated accounts; approved voice used consistently | M1 pass and schema review |
| Following 1–2 weeks | Invited beta readiness | Durable jobs, quotas, retention, rollback, 60-case evaluation | Private identity and reliability gates |
| Following 7 days | 5–10 creator pilot | Daily feedback/cost review; expansion decision | Existing beta quality/privacy gates |

First work session: open START_HERE; run demo; open one tracker card; write its expected
outcome. Second: verify protected hosted Story path and record deployed commit. Third: run
controlled real examples, rate them and choose the most frequent failure to fix.

Freeze new formats, learning pools and providers until the owner gate passes. After Story
acceptance, extend one format at a time. Keep the existing 60-case evaluation targets of
95% supported technical completion and 80% human voice/usefulness ratings at 4/5 or better;
these are targets, not current results.

## How to maintain the tracker

`tracker.csv` is the task source for this recovery plan; KANBAN.md is its readable snapshot.
Columns: Backlog → Ready → In progress → Review → Done, with Blocked explicit. Limit In
progress to one. Owner is a role until a real person accepts assignment. Estimates are
rough effort, not commitments. Dependencies are card IDs; never mark a dependency complete
without evidence. Update the CSV and Markdown together in each change. The existing web
progress JSON remains a coarse release snapshot; synchronize it when milestones change.

For GitHub Projects: create a board with Status, Priority, Owner, Phase and Estimate fields;
create one issue per card and copy its acceptance criteria/dependencies. Map CSV columns
through your chosen import tool; this CSV is portable data, not a promise of native GitHub
Projects CSV import. No remote issues or project have been created by this cleanup.
