# Short Story intent flow

The main Story button now opens a dedicated intent menu before asking for the topic:

1. **ترفيهي** — a light relatable observation or contrast.
2. **معلومة بسيطة** — one useful educational insight delivered directly.
3. **موقف من الحياة** — a concise everyday-life issue or observation.
4. **سؤال للجمهور** — one genuine question directed to viewers, suitable for replies or a sticker.
5. **جواب على سؤال** — a direct answer to the question supplied by the user.

Instagram and TikTok Story buttons show an approximate 30-second duration. Each choice
sets the corresponding intent and purpose in the brief. The next message asks for a topic,
situation or question as appropriate. Other formats keep their own existing angle menu.
Old angle callbacks remain recognized; stale Story callbacks cannot select a style for a Reel.
Changing format or cancelling clears old selections as before.

## Copy and length

The five short intents use one internal `STORY:` field containing the full spoken script.
Telegram strips that transport label and sends clean copy. It does not print Hook, Content,
CTA, numbered points, or add a generic closing. An educational answer need not end in a
question. Asking the audience and answering a question are distinct treatments.

Explanations target about 35–65 spoken words, with less for a simple question; there is no
minimum padding requirement. A deterministic ceiling of 75 spoken words and 800 characters
bounds short single Stories, including legacy single-Story drafts. These are local editorial
limits, not platform constraints or exact duration guarantees. Actual delivery speed varies.

The retired emoji triad, labelled three-tip stack and numbered three-step lesson are blocked
for short Stories. A question may have genuine poll options; the independent reviewer still
rejects a disguised lesson, invented facts or irrelevant interaction. The prior exact retired
bilingual caption layout also remains blocked. Longer multi-frame Story modes remain an
explicit `/brief` option, separate from the default short-intent flow.

## Shared policy and scoring

`story_styles.py` defines the choices once. Keyboard routing, analyst policy, writer contract,
reviewer instructions and delivery validation carry the same `story_intent`. No extra model
call is introduced. A normal analyst/writer/reviewer run still uses three logical calls.

For entertaining, educational, everyday and answer-question short intents, CTA has zero
creative-score weight; the reviewer must not penalize an appropriate absence of a closing
ask. Audience-question intent still assesses the relevance of that interaction. All factual,
safety, topic, voice and format-identity gates remain mandatory regardless of scores.

The intent is logged and included in reports/outcomes/experiment cohorts and `/version`.
Approved examples are filtered by format, mode AND intent to prevent old templates from
conditioning the new short copy. Owner syntax supports the optional third selection field:

```text
/example story moment educational | معلومة وحدة وحچي طبيعي
STORY: قبل لا تختار موقع محلك، راقب إذا الناس اللي تمر تحتاج فعلاً المنتج اللي تبيعه.
```

Legacy examples without an intent remain in the `auto` cohort; they do not enter the five
new intent prompts. This is explicit human approval, not automatic learning.

## Verification and rollout

Run the full suite, compilation and shared-topic contract evaluation. New cases cover all
five choices, distinct ask/answer instructions, CTA weighting, short bounds, template rejection,
legacy callbacks, stale buttons, intent-specific examples, revision reassessment and the
complete mocked format → style → topic → pipeline → plain-copy delivery flow.

Live model/Telegram quality testing remains deferred by the owner. Offline mocks verify
contracts and routing, not actual creative quality or audience attention. Review/merge this
PR first, then deploy the intended commit from main and use `/version` to identify the worker.
Manual pilot: try the same topic with all five styles; read scripts aloud, check length and
meaning, and verify no forced question or generic tip stack appears. Record `/feedback`.

Validation on this branch: **131 tests passed**, compilation and diff checks passed, and
**36/36** existing cross-format contract cases passed. Story-specific tests include the
full mocked three-call Telegram pipeline and explicit brief-style overrides. The existing
long-message chunk test now uses a real article-shaped fixture rather than an oversized
Story, because short Story bounds intentionally reject such output.
