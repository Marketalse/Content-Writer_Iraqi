# Editorial topic library

The 145 rewritten source topics are packaged as a versioned JSON bank in
`knowledge/topics/bot_topics.json`. The IDs are preserved. Each entry has a native
publication format, feature, strategy, structure, audience, angle and three outline
beats. These are editorial inputs, not finished scripts or verified evidence.

## Creator workflow

1. Run `/topics` or tap **مواضيع المحتوى** in `/start`.
2. Choose a pillar, then a topic. Alternatively run `/topic CONT-568`.
3. Review the displayed format, strategy, structure and angle.
4. Confirm writing. This resumes the existing pipeline, including routing, research
   when needed, structural checks, independent review, bounded revision and delivery.

Browsing and previewing do not call models or charge generation quota. Confirmation
is single-use, bound to a selection snapshot and a random token. Selecting another
entry, returning to the library, changing settings or resetting invalidates the
old confirmation. A newly typed custom topic drops the previous library material;
clarification answers and adviser selections retain the relevant brief.

The current destination is preserved if it belongs to the topic's feature. Otherwise
the topic's recorded destination is selected. The exported default resolves conflicting
source recommendations by retaining the primary platform where it supports the chosen
feature, then trying secondary/additional platforms, then a valid feature default.
`format_note` records the choice. The legacy batch runner is unchanged.

## Readiness and limits

- 137 entries are defined and unused according to the supplied source metadata.
- Four are held: CONT-261 (undefined BB), CONT-473 (oil category), CONT-179
  (unidentified case/person), CONT-46 (owner's actual experience).
- Four are marked Used. They remain accessible with an explicit rewrite confirmation.
- A hold does not start generation. Clarify and update its bank record before use;
  the library does not automatically edit its JSON through chat.
- Original status `Verified` does not establish factual accuracy. The bank supplies
  no approved evidence or official figures. Research/factual gates remain unchanged.
- The Excel workbook is a planning/copy-paste companion. Uploading Excel documents
  to Telegram does not import them. The shipped JSON is the runtime source.
- The portable CSV contains layer IDs and `/brief` commands; it is not the old
  `topics_batch.py` input schema. Excel tooling is not a runtime dependency.
- These mappings prevent incompatible selections, not all model/quality failures.
  Current tone, factual, safety and quality gates still apply without guaranteed passage.

## Maintaining the bank

Use schema version 1, unique CONT IDs and all fields defined by `Topic` in
`bot/topic_library.py`. Keep `hold`/`published` JSON booleans. `load_topics` rejects
unknown fields, duplicate keys/IDs, excessive sizes and invalid feature/format/
strategy/structure combinations. `Topic.brief()` produces the normal validated Brief.
Run the full offline test suite after edits. Regenerate the export when changing
IDs or selections. The bank is versioned with the app; deploy the new commit to
make changes available on Render. Chat selections remain in memory only.

No live Telegram delivery, paid model call or new factual research was performed
for this conversion. Offline tests exercise the registered Telegram handlers with a
Bot API double and verify every topic against writer/reviewer configuration.
