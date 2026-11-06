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
- Spelling: **ك not گ, ج not چ** (كال، هيج).
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
- Hooks must pass `knowledge/hooks/hooks_ar.yaml` rules: spoken line ≤ 2 seconds, on-screen ≤ 6 words.
- Run the AI-phrase check (`knowledge/copywriting/ai_phrases_ar.yaml`) on every draft before delivery.
