# Content Workshop — rules for Claude sessions

A copywriting committee (Analyst → Strategist → Writer → Dialect Guard → Critic) that turns one
topic into Baghdadi-Iraqi content for Instagram and TikTok, at Simple / Medium / Complex levels.
Formats: short video, long video story, story question stickers, posts.

## Dialect rules (agreed with the owner)

- Language of all audience-facing text: **Baghdadi Iraqi**.
- **The Iraqi word sheet is the source of truth.** Google Sheet "Iraqi Dilect words"; repo copy
  `knowledge/dialect/iraqi_words.csv`.
  If a formal Arabic word has an entry, use the Iraqi word. **Not in the sheet = standard Arabic is fine.**
- Rows where Iraqi and Arabic are the same (e.g. يظن، إنه، أداة) are fine as-is.
- Spelling: **گ and چ are used on purpose** (گدر، أگلكم، چيبس، أحچي), same as the owner's posts. Both forms are fine; do not "correct" گ or چ to ك or ج.
- Egyptian, Gulf and Levantine words are blocked (`knowledge/dialect/other_dialects.yaml`, `enabled: true`).

## Growing the word sheet (always do this)

Whenever a new Iraqi word appears — in generated content, in the owner's edits, **or in conversation
with the owner** — add it to the review queue (`knowledge/dialect/new_words.csv`) instead of the sheet.
Show the owner the pending list and only add it to `iraqi_words.csv` after they say yes. Then give
them the rows to paste into the Google Sheet (the Drive connector can read the sheet but cannot edit cells).

## Working rules

- Never invent numbers, results, clients or quotes in scripts; use `{{رقمك}}` placeholders.
- Nothing is ever posted automatically. The owner records and posts.
- Model calls go through one module only (default `claude-opus-5-5`).
- Select the platform/format contract from `bot/format_contracts.py`. Hook references are optional for videos; never impose hook, point-count or CTA requirements on every format.
- Run the AI-phrase check (`knowledge/copywriting/ai_phrases_ar.yaml`) on every draft before delivery.

- Model calls go through `bot/llm.py` only. Main model: `claude-sonnet-5-5` (Anthropic SDK).
  Fallback: Nous Portal (OpenAI-compatible), approved by the owner for fallback use only.
  The fallback is used only on connection errors, 429 and 5xx from Anthropic.
