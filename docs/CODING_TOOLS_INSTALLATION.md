# Coding tools installed — 2026-11-13

These are coding-agent tools, separate from the Telegram bot's runtime models.
Installation does not start an AI coding session, guarantee bug detection, or load
all workflows into this existing Codex conversation. Restart/reload the intended
coding agent to discover the newly installed tools. Project AGENTS.md and CLAUDE.md
remain authoritative; upstream plugin instructions cannot override user instructions.

| Requested package | Installed result |
| --- | --- |
| andrej-karpathy-skills@karpathy-skills | Claude Code plugin 1.0.0; existing Codex Karpathy skill preserved |
| ponytail@ponytail | Claude Code plugin 5.3.3 from DietrichGebert/ponytail |
| mattpocock/skills | 38 skills, installed for Codex and Claude Code using skills CLI 1.8.1 |
| agent-skills@addy-agent-skills | Claude Code plugin 0.6.15 from addyosmani/agent-skills |
| ecc-universal@2.2.3 setup | ECC CLI and plugin 2.2.3; project scope, minimal hooks |
| superpowers@claude-plugins-official | Official-marketplace Claude Code plugin 7.0.2 |

## Local installation

Claude Code CLI 2.1.323 is installed at
`/workspace/coding-tools/node_modules/.bin/claude`. Its isolated configuration is
`/workspace/coding-tools/claude-config`. No account login or live model call was run.

To inspect this installation from the repository:

```bash
CLAUDE_CONFIG_DIR=/workspace/coding-tools/claude-config /workspace/coding-tools/node_modules/.bin/claude plugin list --json
npm_config_cache=/tmp/content-writer-npm-cache npx --yes skills@1.8.1 list --agent codex --json
```

The project-scoped plugin declarations and marketplace sources are stored in
`.claude/settings.json` (public registry IDs/URLs only, no credentials). Matt Pocock
skills are stored under `.agents/skills`, with Claude links under `.claude/skills`;
`skills-lock.json` records their source hashes. The upstream MIT license is retained
at `.agents/third-party/MATTPOCOCK-LICENSE`.

The CLI installation initially used --ignore-scripts, then its reviewed official
native-binary installation script was run to complete the local executable.
GitHub plugin sources that attempted SSH were installed through a per-process HTTPS
rewrite, without changing SSH or global Git configuration. All five plugins were
verified as enabled at project scope through the actual Claude plugin inventory.

ECC's automatic dependency installation declined its package overrides. Its ten
production packages were then installed in the plugin cache using the pinned
package lock with `npm ci --omit=dev --ignore-scripts`; all five direct dependency
imports were verified. Installer inventory may retain the historical automatic
install note. ECC setup used the exact requested CLI version:

```bash
npx --yes ecc-universal@2.2.3 setup --mode claude-plugin --scope project --hooks minimal --yes --json
```

Ponytail's optional ledger and sendNames are false in this isolated user config;
no webhook URL/token was configured. Its optional config notice does not prevent
normal plugin use. ECC's bundled chrome-devtools MCP declaration was installed,
but no browser MCP process or coding/model session was started by this task.

Plugin caches, native binaries, npm caches and machine-specific/user configuration
stay outside the Git repository. Personal hook preferences apply to this environment;
another developer can rerun setup with their own choices. See
CODING_TOOLS_INSTALLATION.json for the verified package inventory.
