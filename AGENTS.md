# Coding workflow

Follow the review and reporting instructions in [CLAUDE.md](CLAUDE.md).

Use the project-local [karpathy-guidelines skill](.agents/skills/karpathy-guidelines/SKILL.md)
when writing, reviewing or refactoring code. Read it before starting applicable work.
State material assumptions, prefer the simplest sufficient change, preserve unrelated work,
and verify the requested behavior with focused checks.

The skill is copied unchanged from
https://github.com/Marketalse/andrej-karpathy-skills at commit
`2c606141936f1eeef17fa3043a72095b4765b9c2`.
It supplies instructions for coding agents; it does not run a service or automatically fix bugs.

## Development and validation

Use the existing checkout; do not create a Git worktree unless explicitly requested.
From the repository root, use the Python 3.12 virtual environment:

```bash
.venv/bin/python -m pip check
.venv/bin/python -m unittest discover -s tests -v
git diff --check
```

For bug fixes, reproduce the reported failure with a focused test, apply the smallest
correction, and rerun the relevant checks. Report limitations separately from passing tests.
Offline tests do not establish that live Telegram, Anthropic or web-search access works.
Credentials belong in ignored local configuration or secure environment settings;
never print or commit credential values.
