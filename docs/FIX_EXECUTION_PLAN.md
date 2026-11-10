# Audit fixes — execution plan

Source: `/workspace/project-breaker-audit-20261110/FAILURE_REGISTER.md`.
Work takes place in the existing checkout without resetting prior changes.
The original audit remains unchanged as before-fix evidence.

Each issue follows: reproduce → apply the smallest correction → run dedicated
regressions → run the full suite → update the generated report from actual results.

| Order | Issue | Execution steps | Completion evidence |
|---|---|---|---|
| 1 | PB-01 Journal recovery | Reproduce torn-tail/interior corruption; preserve a quarantined tail; recover only unterminated tail; surface other corruption and storage errors | JournalRecoveryTests + Telegram failure checks |
| 2 | PB-02 Pilot persistence | Validate saved settings; atomically replace files; retain prior valid backup; fail closed on corruption | PilotConfigAtomicTests |
| 3 | PB-10 Publication idempotency | Reproduce repeated marks; retain one canonical publication event | PublicationIdempotencyTests |
| 4 | PB-09 Duplicate routing keys | Reject duplicate JSON keys; keep conservative fallback and strict research parsing | RoutingParserTests |
| 5 | PB-05 Research classification | Separate neutral options/formatting counts from financial claims; retain evidence requirements for actual rates/policies | RoutingBoundaryTests |
| 6 | PB-04 Story shortening | Separate safe labeling from length acceptance; revalidate rewritten bodies; preserve ambiguity checks | StoryRepairTests |
| 7 | PB-07 Batch input validation | Reject zero/negative/excessive concurrency and non-finite/non-positive budgets before scheduling | BatchValidationTests |
| 8 | PB-06 Batch budget | Reserve in-flight work; stop on unknown pricing; release reservations safely; document billing uncertainty | BatchBudgetTests |
| 9 | PB-03 Facilitator integration | Update provider fixtures, test all routes and complete seven-call workflow, preserve final independent checks | FacilitatorRegressionTests + entire existing suite |
| 10 | PB-08 CI/deployment gate | Run CI for main/PRs; require CI checks in Render configuration; test config locally | DeploymentGateTests; live GitHub/Render confirmation remains pending |

## Automatically updated local report

```bash
.venv/bin/python scripts/verify_fixes.py
.venv/bin/python scripts/verify_fixes.py --watch
```

The runner writes `test_reports/fixes/status.json`, `REPORT.md`, `index.html` and
per-check logs atomically after each check. The HTML refreshes every five seconds.
Watch mode reruns verification after source/test/config changes while its process is
running; it does not perform coding, deploy changes or contact paid APIs. Restart it
after a machine restart. The report distinguishes local tests from external checks.

Credentials, hosted search, real Telegram messages, deployed branch protection and
actual Render behavior are not verified by offline tests. No deployment or paid
test is part of this execution. External dependencies remain visible as pending.

## Storage and cost policies

- An incomplete, unterminated journal tail is copied to a sibling `.torn-*` file
  before repair; a warning is logged. Complete malformed rows and interior corruption
  remain explicit operational errors. Append and publication operations are serialized
  within the single bot process. Multiple writers on a shared disk need a transactional
  store or interprocess locking; that deployment is not claimed supported here.
- Pilot files are validated, written via temporary files and atomically replaced.
  A prior valid `.json.bak` is retained when updating existing settings. A corrupt primary
  file is never automatically restored from an old backup because that could reactivate
  revoked permissions. An operator must inspect and explicitly recover it.
- Batch jobs reserve the configured per-run spending allowance before starting and
  release unused allowance after observed usage. Unknown usage, failed attempts or an
  allowance overrun stop further work. This is not a guarantee of an exact provider bill:
  the pipeline's per-run spend setting is an observed stop and a final call can exceed it.
  Concurrency must be an integer from 1 to 16; the batch budget must be finite and positive.
- CI now covers main pushes and all PRs. Render's documented
  [`autoDeployTrigger: checksPass`](https://render.com/docs/blueprint-spec#autodeploytrigger)
  waits for linked-branch CI. The saved file has no effect on an existing deployment
  until applied; actual GitHub protections and Render behavior remain unverified.
