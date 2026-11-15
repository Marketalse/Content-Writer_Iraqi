# System, repository and database map

## Runtime flow

Web: `web/index.html` + `web/workshop.js` → `bot/webapp.py` (session, admission, polling)
→ `bot/web_service.py` (request context and delivery boundary) → `bot/pipeline.py`
→ `bot/revision.py` (routing/research/writer/review/repair orchestration)
→ final delivery checks → `bot/web_store.py` → readable result/history.

Telegram: `bot/bot.py` (commands, choices, access) → shared prompt/pipeline/review engine
→ Telegram delivery. Both paths must preserve mandatory gates and bounded model use.

`bot/prompts.py` builds prompts from knowledge/format rules. `bot/llm.py` owns provider calls,
fallback and usage estimates. `quality.py`, `format_contracts.py`, `reviewer.py`,
`delivery_policy.py` and `output_layout.py` check/review/render artifacts. Research-dependent
requests cannot silently use a fallback that lacks the required search capability.

## Repository responsibilities (current physical paths)

| Path | Responsibility | Change when |
|---|---|---|
| `web/` | Browser screens and progress snapshot | User interface changes |
| `bot/bot.py`, `webapp.py`, `web_service.py` | Channel adapters/application boundary | Commands, API or access behavior changes |
| `bot/pipeline.py`, `revision.py`, `llm.py` | Orchestration/provider boundary | Execution, budgets or provider behavior changes |
| Other `bot/` modules | Content domain, quality, topics, storage | A specific domain behavior changes |
| `knowledge/` | Voice, examples, dialect, hooks, registries, source lessons | Editorial knowledge changes |
| `formats/`, `guidelines/` | Human-readable native-format and dialect guidance | Format/voice requirements change |
| `tests/` | Offline regression evidence | Runtime behavior changes |
| `scripts/` | Build, evaluation and verification commands | Development/verification tools change |
| `docs/project/` | Current brief, decisions, roadmap, tracker | Priority/status/evidence changes |
| Other `docs/` | Feature design, historic reviews and deployment references | Supporting detail changes |
| `.agents/skills/` | Optional instructions for coding assistants | Development workflow changes |
| `.claude/` | Claude-specific development configuration | That tool's setup changes |
| `supabase/migrations/` | Future database design | Multi-user milestone begins |
| `.github/workflows/`, `render.yaml`, `vercel.json` | CI and deployment configuration | Release infrastructure changes |

Keep these paths now: flat imports, prompt file lookups, tests and startup commands depend
on them. Later, after acceptance, migrate incrementally to a Python package with adapters,
application, domain and infrastructure directories. First add package import checks; then
move one boundary per PR. A visual map gives clarity now without a risky large rename.

## Database: current versus proposed

**Current web preview:** SQLite `STATE_DIR/web-preview.sqlite3`; demo uses
`STATE_DIR/web-demo.sqlite3`. `jobs` contains `id`, unique `request_id`, `created`, `state`,
`payload`, `context`, `result`, `parent_id`. The parent links edits/continuations logically;
there is no SQL foreign key on this SQLite column. One active job, one process, one owner.
Sessions/tasks are in memory; restart clears sessions and marks unfinished jobs interrupted.

**Current Telegram:** `pilot.py` stores pilot configuration at `STATE_DIR/data/pilots.json`;
`postlog.py` appends `STATE_DIR/logs/posts.jsonl`. Without STATE_DIR these resolve under the
repository. Its feedback reach export is `knowledge/feedback/reach_log.csv`.
Web and Telegram do not yet share a creator account database.

**Future Supabase proposal:** Auth user → profile → voice profile/examples and jobs;
job → feedback; profile → consented pooled corpus. All private rows use row-level security;
pooled rows have no client policy. SQL exists but has not been applied or wired into runtime.

Before applying it: enforce that `feedback.job_id` belongs to `feedback.user_id` (the current
policy checks only the feedback user); verify two-user isolation and approved-profile
immutability/versioning; specify permitted job states, parent/idempotency fields, migration
of current history, retention/deletion and backend-only mutations. These are design review
requirements, not confirmed production leaks. Defer pooled learning until consent and
withdrawal behavior is demonstrated.

## Skills versus product knowledge

Coding skills are instructions an assistant may read. They do not run services or improve
runtime output automatically. Product knowledge is loaded by prompts/registries; model
roles are executed by the pipeline. A skill install is not a shipped feature.

| Skill category | Installed names | Recommended use |
|---|---|---|
| Everyday minimum | `karpathy-guidelines`, `diagnosing-bugs`, `tdd`, `pr` | Small scope, reproduce a bug, regression, reviewable change |
| Understand/design | `ask-matt`, `codebase-design`, `domain-modeling`, `wayfinder`, `research`, `wizard`, `wait-what`, `improve-codebase-architecture` | Only for a specific unanswered design question |
| Specify/plan | `grill-me`, `grill-with-docs`, `grilling`, `loop-me`, `to-questionnaire`, `to-spec`, `to-tickets` | Turn a bounded requirement into criteria and tickets |
| Implement/review | `implement`, `implement-spec`, `prototype`, `code-review`, `setup-pre-commit`, `git-guardrails-claude-code` | Follow the selected task's workflow |
| Writing/teaching | `writing-for-agents`, `writing-shape`, `writing-fragments`, `writing-beats`, `teach`, `scaffold-exercises` | Documentation or learning tasks |
| Session/operations | `handoff`, `claude-handoff`, `chief-of-staff`, `triage`, `retro` | Explicit session handoff or project operations |
| Other-stack/setup | `setup-ts-deep-modules`, `migrate-to-shoehorn`, `setup-matt-pocock-skills` | Park unless that stack/setup is actually involved |

Preserve installations; use fewer at once. Read a selected skill before applying it.
No additional providers, plugins or orchestration framework is needed for the Story MVP.

## Tools and responsibility

Owner: priorities, provider budget/secrets, source applicability and voice acceptance.
Coding assistant: trace code, implement one card, tests, safe errors and evidence.
GitHub: version history, PR review and CI. Render: Python runtime and durable storage.
Vercel: static frontend and same-origin proxy. SQLite: owner-preview persistence.
Supabase: future identity/storage proposal. Model: draft/review assistance; owner retains
publication responsibility. No component continuously manages progress from Markdown.

## Optimization order

Measure before optimizing: accepted-script rate, owner editing effort, total provider calls,
actual cost and p50/p95 latency. Then fix the largest observed cause. Keep retry/cost limits,
existing prompt caching and clear research routing. Defer caching new artifacts, parallel
model calls and infrastructure changes until measurements show a user benefit.
