# Creator profiles, invited testing and pooled learning

Status: design proposal, 14 November 2026. Nothing here is built or deployed yet.
The schema is in `supabase/migrations/0001_creator_profiles.sql` and has not been applied.

## Owner decisions (14 November 2026)

- Anonymized creator data may be pooled to improve the shared Iraqi-dialect knowledge.
- First test group: 5–10 creators, invited by the owner. No open sign-up.

## How a creator uses it

1. **Invite.** The owner invites the creator by email from Supabase Auth. Public sign-up is off.
2. **Onboarding.** Three short questions (content type, audience, goal), then the creator
   pastes 3–5 of their own published posts.
3. **Voice approval.** The system drafts a tone summary from those posts. The creator edits
   or approves it. Nothing is written in their voice before approval.
4. **Consent.** A separate, plain-language choice: allow anonymized copies of their examples,
   accepted drafts and edits to improve the shared dialect knowledge. Off by default; can be
   withdrawn at any time, which deletes their pooled rows.
5. **Writing.** Topic + treatment in, reviewed script out, using only that creator's profile.
6. **Feedback.** A 1–5 rating and the creator's edited version. This is the main learning signal.

## Data rules

- Every table is private to its creator through row-level security.
- `pooled_corpus` has no client access at all. Only the backend writes to it, after
  removing names, handles, phone numbers and links, and only for creators with consent.
- Pooled rows keep an internal contributor reference so withdrawal and account deletion
  remove them. That reference is never shown to anyone and never sent to a model.
- "Anonymized" here means scrubbed text with hidden origin. Distinctive wording can still
  be recognizable, so the consent text must say so.
- Pooled text is used for dialect vocabulary and phrasing, never as another creator's voice.

## Architecture

- **Vercel:** static frontend (existing), plus Supabase sign-in in the browser.
- **Supabase:** Auth (invite-only), Postgres tables above.
- **Render:** existing FastAPI backend. It verifies the Supabase session token, loads the
  creator's voice profile, and calls the existing `run_pipeline`. Model keys stay server-side.
- **Telegram bot:** unchanged; stays on the owner's voice.

## Build order

1. Apply the migration; disable public sign-up; invite the owner as first user.
2. Backend: replace the single preview password with Supabase token verification; move
   jobs from SQLite to the `jobs` table.
3. Engine: pass a creator's voice profile into prompts and review instead of the shared
   `knowledge/voice/voice.md` (the M2 gap recorded in `AI_REVIEW.md`).
4. Frontend: sign-in, onboarding, voice approval, consent, feedback.
5. Pooling job: scrub and copy consented text; review a sample by hand before any use.
6. Invite 5–10 creators.

## Not decided yet

- Exact consent wording (Arabic), and whether a privacy notice is needed for Iraqi users.
- Per-creator daily limits and who pays for model usage during the test.
- How pooled text feeds the engine (curated word list vs. retrieved examples).
