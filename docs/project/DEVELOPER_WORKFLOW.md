# Developer workflow and environment

## Start with a free local demo

From repository root, with Python 3.12 and Node available:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r bot/requirements-web.txt
cp .env.example .env
WEB_DEMO=1 WEB_PREVIEW_PASSWORD= WEB_PUBLIC_ORIGIN= .venv/bin/python bot/webapp.py
```

Open http://127.0.0.1:8877. Demo returns a labelled sample and does not call a model. Leave
live password/origin empty in demo. In environments where Python 3.12 is `python3`, use that
executable. Stop with Ctrl+C. Do not treat demo edits as proof of model editing quality.

## Environment categories

| Category | Settings | Required when |
|---|---|---|
| Local sample | `WEB_DEMO=1`; empty `WEB_PREVIEW_PASSWORD` and `WEB_PUBLIC_ORIGIN` | No-cost demo |
| Protected owner web | `WEB_DEMO=0`, strong 32–200 character `WEB_PREVIEW_PASSWORD`, `ANTHROPIC_API_KEY` | Real web writing |
| Hosted web | Exact HTTPS `WEB_PUBLIC_ORIGIN`, `WEB_HOST=0.0.0.0`, host-provided `PORT`, durable `STATE_DIR` | Vercel proxy/Render web deployment |
| Telegram | `TELEGRAM_BOT_TOKEN`, provider key; `OWNER_CHAT_ID` / `ALLOWED_CHAT_IDS` as appropriate | Existing bot/access policy |
| Quality budgets | Existing `QUALITY_*` values | Preserve defaults; tune only against evidence |
| Optional fallback | `NOUS_API_KEY`, base URL and model | Only if a tested fallback is needed |
| Model overrides | `ANTHROPIC_MODEL`, `ANTHROPIC_FAST_MODEL` | Verify provider availability and price handling first |
| Future identity | Supabase settings | Not implemented in this preview; do not add speculative keys |

`.env.example` contains placeholders/defaults only. Actual secrets belong in ignored `.env`
or hosting secret settings. Never use frontend variables for model keys. `.gitignore`
prevents future untracked files being added; it does not erase previously committed secrets.
Only `.env.example` is tracked in the reviewed tree; this is not a full history secret scan.

The checked-in model identifiers and token-price tables are assumptions needing live
verification. Changing to an arbitrary model can fail price/budget validation; test provider
compatibility and accounting together. No paid model requests are part of this cleanup.

## Live owner preview (after a test budget is set)

Set WEB_DEMO=0, provider key and random preview password in private settings. Locally start
`.venv/bin/python bot/webapp.py`; hosted web needs `WEB_HOST=0.0.0.0`, persistent STATE_DIR
and exactly one worker. Set the exact public HTTPS origin for Vercel. Verify `/health`
reports `owner-preview`, unauthenticated `/api/config` returns 401, sign-in works, then run
the PoC cases. Do not paste secret values into issues, screenshots or review reports.

`render.yaml` configures the Telegram worker only. Provision/verify a separate web service
using web requirements and `python bot/webapp.py`; the existing Vercel rewrites expect
`https://content-writer-iraqi.onrender.com`. A health response establishes mode/availability,
not AI quality. Back up private state before changes. Keep prior release/settings for rollback.

## One-card development loop

1. Choose one Ready card; state expected user behavior and acceptance evidence.
2. Inspect entry point, prompt, storage, checks and delivery; reproduce a reported bug first.
3. Make the smallest change. Read AGENTS.md/CLAUDE.md and applicable local skill.
4. Run focused checks and repository checks below; inspect the diff for secrets/unrelated edits.
5. Record result/limitations, request review, and merge only after acceptance. Deployment and
   live acceptance remain distinct from a merged PR. Update card and progress evidence.

```bash
.venv/bin/python -m pip check
.venv/bin/python -m unittest discover -s tests -v
node scripts/build_web.mjs
git diff --check
```

CI also runs `python scripts/verify_fixes.py`, producing ignored report files. Optional browser
check: install Playwright in the venv, use Chromium, run demo then
`.venv/bin/python scripts/verify_web_browser.py`. It refuses live mode. Preserve the
independent reviewer and factual gates when fixing failures.

## Daily routine for a new vibe coder

Ask the assistant: “Implement card CW-___ only. First explain current behavior and how you
will prove acceptance. Preserve unrelated features. Report files changed, checks and limits.”
Read the resulting diff and try the user journey before accepting it. End by recording
what passed, what failed and the next single card. Put new ideas in Backlog.
