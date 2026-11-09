# Deploy the bot on Render (no terminal, no VPS)

## What it costs
- Render Hobby workspace: free.
- Background worker (the bot runs 24/7): about $7 a month (Starter). Free instances sleep
  after 15 minutes idle, so they cannot keep a Telegram bot listening.
- Disk for pilot limits and the post log: $0.25 a month per GB (1 GB is set).
- Model costs: the Anthropic bill (see docs/pilot_and_pricing.md).

## Steps
1. Stop the bot on your Mac (`Ctrl+C` in its terminal). Only one copy can run per Telegram token.
2. Go to render.com, sign in with GitHub, and allow access to `Marketalse/Content-Writer_Iraqi`.
3. Click **New -> Blueprint**, pick the repo and the branch `main`.
   Render reads `render.yaml` and shows the worker, the disk, and the settings.
4. Fill in the four secret values when asked:
   - `TELEGRAM_BOT_TOKEN`: from @BotFather (use a new one if the old token was ever shared)
   - `ANTHROPIC_API_KEY`: from console.anthropic.com
   - `OWNER_CHAT_ID`: your Telegram chat ID (send /id to the bot)
   - `NOUS_API_KEY`: optional, leave empty if you have none
5. Click **Apply**. Render builds and starts the worker. Open its **Logs** tab and look for
   `bot started`.
6. Send `/start` to the bot in Telegram to check it answers.

## Where secrets go
Only in Render: the service's **Environment** tab. Never in a file in the repo, never in chat.
`.env` is git-ignored and is only for running on your own computer.

## Updating
Each merged update to `main` redeploys automatically when the service tracks the repository Blueprint (`autoDeploy: true`).
Existing service settings must also use `main`; changing a file alone does not confirm that Render applied it.

## Pilot data
Pilot limits (`data/pilots.json`) and the post log (`logs/posts.jsonl`) are written to the
disk at `/var/data` (env `STATE_DIR`). They survive redeploys. Back them up by copying the
files from the disk before you delete the service.


## Identify the worker answering Telegram

Send `/version` from an authorized chat. It reports the runtime contract version,
Render commit/branch (or `unknown`), source fingerprint, selected format and prompt
fingerprint. It does not report credentials. Compare `commit` to the commit displayed
in the Render deployment, rather than relying solely on a `native-v2` log line.

Required settings for this repository: **Branch `main`**, **Start Command
`python bot/bot.py`**. The previous Blueprint pointed at
`claude/festive-meitner-3m5y3a`; that branch still loads the exact universal emoji
caption template. A successful redeploy of that branch can therefore reproduce the
old layout. This is a repository configuration finding, not proof of a live service's settings.

If `/version` is unknown after deploying the commit that adds it, the responding
worker is not serving this entry point/version. Check the responding Telegram bot's
username and the service/repository/start command; also check for another worker or
local process using the same token. Do not share the token in diagnostics. Multiple
pollers normally produce Telegram conflict errors. The main Story validator rejects
Hook/Content/CTA captions before reviewer calls, and the delivery boundary revalidates
accepted content before sending it.

## If a merged update still shows the old menu

First collect evidence without sharing credentials:

1. In the bot chat, send `/version` and copy the complete response. If it does not answer,
   record that fact. The workflow-repair build reports `workflow=platform-flow-v2`.
2. In Render, open the worker, then **Events** and the latest successful deployment.
   Copy the deployed commit ID. A merge on GitHub is not proof that the worker deployed it.
3. In the worker **Settings**, copy the linked repository, branch and Start Command.
   They should be `Marketalse/Content-Writer_Iraqi`, `main`, and `python bot/bot.py`.
4. Compare the worker's deployed commit with the responding bot's `/version` commit.
   Compare the startup `bot=@...` identity with the Telegram chat username.
5. Only after identifying a mismatch, fix the actual service setting or deploy the intended
   merged commit using Render's manual deployment control. Recheck `/version`, then `/start`.
   If the menu remains old, investigate other services/local processes using the same token.
   Stop only the duplicate process you have identified; do not delete its persistent disk.

For a passing menu smoke test, `/start` shows content families. Story opens Instagram/TikTok;
Carousel opens Instagram/TikTok/LinkedIn document; Video opens Instagram/TikTok; LinkedIn
opens Post/Article. Continue through style, three structure choices and topic. Use Back to
change platform and confirm downstream choices are reset. Startup logs and local tests
alone do not establish that the live worker serves these menus.

No bot token or model key is needed to share these diagnostics. Do not paste Render's
Environment tab. For direct inspection, use an already authenticated shared browser session;
logging into an account is a user action, and passwords/login codes stay outside chat.
A second process must not poll the production Telegram token for testing. The automated
workflow tests use a simulated Bot API transport instead.
