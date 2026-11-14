# Project execution board

Updated 14 November 2026 (Baghdad). Goal: a creator supplies a topic and treatment,
selects a platform/feature, and receives an organized script in their own voice.
Primary interface: web. One shared editorial engine; Telegram remains available.

## Milestones

| Milestone | Goal | Status and exit check |
|---|---|---|
| M1 — Owner web preview | One complete Instagram Story journey | Implemented; 351 offline tests and desktop/mobile demo checks passed; live model/deployment acceptance remains pending |
| M2 — Creator voice and identity | Independent creators have separate confirmed voice profiles | Planned; two distinct creators must never share private examples/history |
| M3 — Editorial reliability | Match failures to bounded repairs | Existing controls partial; recurring voice/format/research examples need calibrated recovery |
| M4 — Hosted release operations | Durable and observable multi-user web service | Preview persistence exists; Vercel/backend deployment, account authorization and multi-user operations pending |
| M5 — Acceptance evaluation | Validate real outputs, not just unit tests | Planned; 60-case pack and human ratings before opening beta |
| M6 — Invited beta | 5–10 creators test for seven days | Planned; daily feedback/incident review and explicit expansion decision |

## M1 task checklist

- [x] T1.1 Record product goal, milestone order and completion evidence.
- [x] T1.2 Adapt the Workshop visual palette/sidebar/card interaction into a focused page.
- [x] T1.3 Topic + current Story treatment registry + fixed Instagram Story destination.
- [x] T1.4 Call the existing research/writer/reviewer pipeline through a web application boundary.
- [x] T1.5 Revalidate native structure, intent, fresh artifact identity and quality gates at delivery.
- [x] T1.6 Show readable copy, source links, safe failure messages and request references.
- [x] T1.7 Request an edit; preserve original topic and rerun research/review on the result.
- [x] T1.8 Continue clarification and validated failed-topic advice through the normal engine.
- [x] T1.9 Owner preview sessions; server-side keys; origin/body guards and redacted errors.
- [x] T1.10 SQLite history, duplicate-start protection, one active job, daily admission cap.
- [x] T1.11 Mark interrupted jobs on restart; never silently restart paid work.
- [x] T1.12 Explicit no-cost demo, isolated from live generation and live job storage.
- [x] T1.13 Full offline regression suite (351 tests) and ten desktop/mobile demo checks passed.
- [x] T1.14 Configure PR/main CI to install web dependencies and run the full suite.
  Actual release outcomes are tracked separately by GitHub checks and the release report.
- [ ] T1.15 Owner live acceptance on a deployed preview, including edit and source verification.

## Next implementation slice

M2 identity + private voice profiles, followed by the hosted frontend/backend connection.
Keep a Story-first scope until the full journey is accepted; then extend native rendering
and the UI to Reel/Post. Do not change the existing Telegram deployment just to preview
this web UI. No further model providers or coding plugins are needed for M1.

## Acceptance and status rules

Milestones are complete only with their stated evidence. Offline tests establish
regression behavior; a demo establishes interface behavior with fixtures; neither
establishes live model quality or deployed availability. Keep live acceptance separate.

The web Project progress screen reads `web/progress.json`; it is a release-maintained
snapshot, not an automatic project manager. Request progress/history come from the
job API and update during a run. CI verification reports remain separate from human
acceptance results. Update this board and the snapshot with each implementation PR.

Proposed beta gates: >=95% supported technical completion, >=80% human voice/usefulness
ratings at 4/5 or better, no unresolved critical privacy/factual/safety defects, and clear
failure outcomes. Measure latency/cost before agreeing live service targets. Full details:
[BETA_RELEASE_ROADMAP.md](BETA_RELEASE_ROADMAP.md).
