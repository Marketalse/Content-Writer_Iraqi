# What happened to main

Evidence: `git log --reverse`, first-parent history, current modules and documentation.
Baseline `2ebfc52` on 14 November 2026; reviewed 15 November (Baghdad).
41 pull-request merge commits appear on the first-parent line after the initial commit.
This is an evolution analysis, not evidence of a production incident or broken deployment.

| Date | Direction and representative commits | Consequence |
|---|---|---|
| Nov 6 | `55ddb92`: dialect guides + Telegram writer; `fadb4de`: embedded knowledge; `dc29cb3`: published voice examples | Clear original product: owner's Iraqi content writer |
| Nov 6 | `a9de4ca`: checks/retry; `b334f4e`: universal Hook/Content/CTA; `57469a1`: pipeline/formulas/logging | Delivery and quality became intertwined; a universal template was imposed |
| Nov 6 | `ed4004c`: pilot/pricing; `9730fc0`: batch topics; `805f6ca`: Render worker | Operations and commercialization arrived very early |
| Nov 8 | `51618df`, `b1ea8ae`, `5a30001`: twelve native platform profiles | Scope broadened; native contracts replaced universal structure |
| Nov 8–9 | `b8c9efb`, `b1873cb`, `a6aa1a1`, `daf5675`: independent review, format identity, source learning and intent-first Story | More reliable controls, but many routing and planning concepts for one user task |
| Nov 9–10 | `7548372`, `035ec77`, `0653a9c`, `fd2bc89`, `34b5c49`: transport, storage/CI, credit failover, structural repair, editorial loops | Much work shifted to correcting interactions among new layers |
| Nov 13 | `98eeebe`: feature/strategy/structure layers; `9102973`: voice calibration; `d4464ad`: topic adviser; `af83b61`: coding skills | Expanded choices, voice controls and development tooling |
| Nov 14 | `f18bf8c`: topic library; `59ae4e3`: web-first Story preview | Interface pivot from Telegram-first to web-first with the same engine |
| Nov 14 | `8f938a6`, `9246c44`, `96c78a0`: Vercel bridge/build/auth hardening | Additional deployment surface: frontend + Python backend |
| Nov 14 | `a815d90` merged as `2ebfc52`: creator profiles and draft SQL | Multi-user product design begins before recorded M1 live acceptance |

## Diagnosis

The original goal survived, but the active plan expanded faster than acceptance evidence.
There are multiple planning documents, a manually maintained progress snapshot, broad engine
support, and a narrower web UI. These describe different scopes and are easy to confuse.
No evidence from the offline suite establishes that current production generation fails;
355 baseline tests pass. The missing proof is one accepted live end-to-end owner journey.

## Concrete inconsistencies to resolve

- README still opens with the Telegram architecture while the execution board says web is
  primary. New navigation makes the current product and legacy support explicit.
- Execution board says M1 live acceptance is pending, but its next slice starts M2. Recovery
  changes that order: finish acceptance first.
- `render.yaml` provisions a Telegram worker, while `vercel.json` points to a separate Render
  web backend. A worker cannot serve those HTTP requests; verify the separate service.
- `WEB_PREVIEW.md` suggested demo connection checks with `WEB_PUBLIC_ORIGIN`; `create_app`
  rejects that combination. Demo must have both live origin/password empty; configure them
  together only when switching to protected live mode.
- Supabase SQL is unapplied design. It must not be counted as implemented creator accounts.

No history rewrite, runtime file relocation, database migration or deployment is needed for
this organizational cleanup. New feature decisions should pass through the Story gate.
