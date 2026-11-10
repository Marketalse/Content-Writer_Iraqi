# Project instructions for Claude Code

Read [AGENTS.md](AGENTS.md) and the project-local
[Karpathy guidelines](.agents/skills/karpathy-guidelines/SKILL.md) before coding or reviewing.
Apply their principles: explicit assumptions, simple implementations, focused changes,
and verification of the requested behavior. Preserve unrelated uncommitted work.

This file is agent guidance, not executable code or a background monitor. It does not
change the Telegram bot's runtime prompts, start Claude Code, or guarantee error detection.

## Review and reporting

When asked to diagnose the project or after making a behavior change:

1. Trace the relevant production entry point through prompts, validation, review,
   retries and delivery. Compare actual behavior with the user's requirement.
2. Reproduce suspected defects with a focused test or minimal command. Distinguish
   confirmed failures, design limitations, missing credentials and untested hypotheses.
3. Review AI-written code as critically as other code. Check factual evidence,
   source dates and applicability, format contracts, retry bounds, usage accounting,
   failure messages and secret handling where relevant to the change.
4. Fix defects within the user's authorized task; preserve independent review and
   required factual/safety gates. Do not hide failures by weakening checks.
5. Run the appropriate checks in AGENTS.md. Never claim a live service works based
   solely on mocked tests, a PID, an open port, or the existence of this file.
6. Report findings to the user, including severity, affected file/function, evidence,
   practical impact, and what remains unresolved. State plainly if a previous AI
   claim was stronger than the evidence. If no defect is found, state the review scope
   and limitations rather than claiming the code has no bugs.

For a project review, update [docs/AI_REVIEW.md](docs/AI_REVIEW.md) with dated evidence.
Do not overwrite unrelated user notes. Record commands and result counts, whether
live APIs were exercised, and whether changes are local, committed or deployed.
Never write credential values, raw provider errors, private prompts or personal data
into the report. These reports are written when an agent performs a review; no
continuous monitoring or autonomous execution is configured by this Markdown file.
