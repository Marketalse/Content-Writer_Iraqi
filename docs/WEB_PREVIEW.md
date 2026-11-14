# Owner web preview — M1

This is a single-owner preview, not a multi-creator account system. Instagram Story is
the only supported web route. The current owner voice, existing pipeline, review gates,
provider fallback and failure-only Opus adviser remain in effect. Telegram is unchanged.

## Run locally / in a separate preview service

Install `bot/requirements-web.txt` using Python 3.12. Start `python bot/webapp.py`.
The default listener is 127.0.0.1:8877. Set PORT and WEB_HOST for a controlled hosted
preview. Keep exactly one process/worker; job admission is durable, but execution is
in-process and does not support multi-worker ownership yet.

For real generation set WEB_PREVIEW_PASSWORD to a unique random value of at least
32 characters in secure environment settings. Use the same settings for provider keys;
the browser never receives those keys. Sign in through the page. Sessions expire in
12 hours and restart/sign-in invalidates earlier sessions. HTTPS is required when
hosting so the session cookie is Secure. Preview password is not an API provider key.
Do not put credentials in URLs, frontend variables, source files or GitHub.

WEB_DAILY_LIMIT defaults to 20 admitted jobs per UTC day, including edits/clarifications.
One job may be active at a time. This is independent of Telegram's pilot quota and
uses existing per-run time/call/spend limits; it is not a hard provider billing cap.
Every retry/edit consumes another job unless it reuses the same idempotency key.
No automatic retries on crash. The preview owner must control both interfaces' use.

SQLite lives under STATE_DIR (default ignored `data/`). Back it up privately; it holds
topics and checked results. Restart changes unfinished jobs to interrupted. Unknown
exceptions are redacted, and blocked drafts never enter API results/history. The real
pipeline's final-artifact hash, full review gates and deterministic checks are required
before the copy field is populated. Below-threshold drafts are withheld in this preview.

## No-cost demo

Set WEB_DEMO=1 before starting. All model calls are bypassed even if credentials are
present; output is a labelled static sample with no score/calls/spend. It uses a separate
web-demo.sqlite3 store and no sign-in. This mode is for interface evaluation only;
keep its data disposable. It does not demonstrate genuine research, editing or FQS.
Never mix demo and live processes/stores. Changing demo content does not change prompts.

## API and frontend

- POST /api/session; DELETE /api/session — owner-preview session.
- GET /api/config — supported treatments, fixed destination and demo status.
- POST /api/jobs — request UUID, topic/strategy; optional parent + exactly one edit,
  clarification answer or stored-suggestion index.
- GET /api/jobs and /api/jobs/{id} — safe results and up to 30 recent requests.
- GET /health — availability/mode only, not a provider or quality health check.

POST /api/jobs requires a request UUID. Replays with identical input return the same
job; different input with that UUID is rejected. The UI keeps the UUID across an
uncertain submit. After a lost connection/reload use My drafts before starting again.

The server currently serves static files from web/ at the same origin as the API.
The visual palette and shell are adapted from Marketalse/Content_Workshop ec65d20;
its committee, desktop key/updater controls and scoring policy are not copied.

Vercel can host these static frontend assets. Connect it only once there is a controlled
backend URL, using same-origin rewrites for /api/* and /assets/* (or matching build
paths). Run the Python generation backend separately on Render with persistent storage;
do not put the current in-process long-running jobs in Vercel request handlers. No
Vercel project, Render web service, deployment or cross-origin access was created here.
Existing Render worker continues to run Telegram as configured.

## Before inviting independent creators

Implement accounts, per-creator ownership and confirmed profile versions; remove
implicit owner-library access; validate storage retention/deletion; use hosted job
ownership/concurrency controls; add reliable operator metrics; complete controlled
live provider/research tests and human voice acceptance. Do not advertise this owner
preview as the completed multi-user product.

## Repeatable browser checks

`scripts/verify_web_browser.py` requires the optional Playwright package and Chromium.
It refuses any server whose /health mode is not demo. With the demo at port 8877, run
`python scripts/verify_web_browser.py` using a browser-equipped environment. Its nine
checks and screenshots go to ignored `test_reports/web/`. Browser dependencies are
not needed by the application or the offline CI suite. They were installed separately
under /tmp for this verification. Headless checks do not exercise a signed-in desktop
or the user's own browser.


## Vercel → Render connection

The root `vercel.json` now builds a static frontend from `web/` into `dist/`, rewrites `/assets/*`
to its emitted static files, and proxies `/api/*` plus `/health` to
`https://content-writer-iraqi.onrender.com`. All AI orchestration stays on Render;
Vercel needs no Anthropic key for this architecture. The browser uses relative API
paths so its session cookie remains on the frontend origin. No public CORS is enabled.

In Vercel use this repository, root directory blank, and the **Other** framework
preset. The repository config declares the static output/build/install commands.
Remove conflicting dashboard overrides if Vercel asks. Use the production website
URL from **Visit** or **Domains**, not the Vercel account/project dashboard URL.

On Render add `WEB_PUBLIC_ORIGIN=https://your-exact-production-site.vercel.app`
(or the exact HTTPS custom domain) and redeploy the new backend commit. No path,
query, fragment, credentials or wildcard. Only that explicit origin plus the backend's
own origin may submit forms. Other preview domains are deliberately rejected; update
the setting if changing the primary frontend domain. A configured HTTPS public origin
also forces Secure session cookies even when a reverse proxy terminates TLS upstream.

Keep `WEB_DEMO=1` during connection checks. Verify the public Vercel `/health` returns
`{ "status": "ok", "mode": "demo" }`, then test Create/history/edit from that frontend.
Only later enable protected live mode. On 14 November the supplied Render `/health`,
HTML, JS, CSS and demo config returned 200; this proves the deployed demo responds,
not live AI quality. The Vercel side still needs deployment and the exact origin setting.
The code change alone cannot modify either provider's dashboard environment settings.

The UI handles non-JSON proxy errors with a safe starting/unavailable message instead
of showing HTML or a JSON parsing exception. The Free Render instance can cold-start
and has no durable disk, so it remains suitable only for disposable demo testing.


### Fix: Vercel cannot find its output directory

The reported build error was “No Output Directory named web found.” The checked-in
build now runs `node scripts/build_web.mjs`, which creates `dist/` and verifies/copies
only index.html, CSS, JavaScript and the progress snapshot. vercel.json selects dist
as output, and CI runs the same build. It resolves source paths relative to its own
location rather than assuming the command's working directory.

Vercel project settings must use the repository root (Root Directory blank), Framework
Preset Other, and no conflicting build/output overrides. If overrides must be enabled,
Build Command is `node scripts/build_web.mjs` and Output Directory is `dist`.
Deploy the latest commit after changing settings, not an earlier failed deployment.
The reported error establishes a missing resolved build directory, not whether a
specific dashboard root setting or stale commit caused it; those private values
have not been inspected here.
