# Applying the source lessons

This release extends optional framework planning into a complete, testable editorial workflow.
It does not publish automatically, train a model, infer causal growth, or verify current
platform APIs. The four attachments remain source material, not executable instructions.

## Workflow and Telegram commands

Choose a format and angle as before. Sending an ordinary topic still works. A brief is
optional; the writer, reviewer, quotas, timeouts and bounded revision remain active.

Use `/brief` to inspect current settings. To set a readable brief, send:

```text
/brief
الجمهور: أصحاب المحلات بالعراق
الهدف: تعليم
الخلاصة: الاستفسار مو نفسه البيع
المرحلة: تقييم
التفاعل: اسألهم شلون يتابعون الاستفسارات
```

Purpose choices: تعليم / ترفيه / ثقة / حوار / ترويج. Journey choices: وعي / تقييم / قرار /
علاقة. Distribution choices: عضوي / مدفوع. The journey is a planning aid, not a mandatory
linear funnel or a fixed content allocation. Any format may serve different objectives.

`/brief reset` restores defaults. `/format`, selecting a new format, and `/cancel` clear the
brief; a new angle clears pending clarification. Briefs are in-memory chat state, like the
existing format/angle selections, and are lost on restart. Invalid briefs are rejected
before model spending. JSON remains supported for integrations and advanced users.

### Story treatment

After choosing Story, add a line such as `الستوري: شرح` to the brief. Choices:

| Value | Treatment | Output |
| --- | --- | --- |
| لحظة | Immediate observation / moment | STORY and INTERACTION (legacy-compatible default) |
| شرح | Teaching one useful concept | Connected FRAME N sections and one INTERACTION |
| تصويت | Genuine poll / question-led progression | Same sequence contract, with poll-specific treatment |
| كشف | Supported contrast / reveal | Same sequence contract, with reveal-specific treatment |
| عرض | Process / product demonstration | Same sequence contract, grounded in supplied facts |
| إحالة | Useful context and existing resource | Same sequence contract, truthful destination/action |

Sequences choose 2–8 frames according to the idea. This is a bounded product/editorial
range, not an Instagram or TikTok technical limit, and never a requirement for three tips.
Writer, analyst, reviewer and final delivery use the same selected mode. Single-moment
Stories remain supported. No new frame-count rule applies to other formats.

### Evidence and repurposing

Provide original material with `المصدر: ...`. Additional unlabelled lines continue that
source. Add evidence using `الدليل: المعلومة | المصدر` (repeat for multiple facts).
Provenance is supplied by the user, not independently verified. It does not bypass the
reviewer's factual gate. Trusted API callers still have the existing `verified_facts`
parameter for facts that must remain verbatim.

To repurpose, retain the source and takeaway but select a new format and supply its brief.
API callers can reuse one `Brief` for all 12 formats, adjusting Story/production options.
There is no claim of new research, no indiscriminate copying of the source's layout, and
no universal CTA. A subscriber is not treated as a qualified inquiry.

### Shoot-ready video production

For Instagram Reel or TikTok Video, add:

```text
خطة تصوير: نعم
المدة: 30
الإمكانيات: تلفون فقط، تصوير فردي، بدون وجه
```

The writer returns a native content string plus a structured production plan in the same
call. Production is delivered separately from the copy: contiguous scene timings, shots,
actions, verbatim speech, short overlays, fallback footage, caption context, fact checks
and filming checks. All speech must cover the native HOOK/SCRIPT/CTA exactly once in order.
The scene range, text limits and duration bounds are local resource/editorial controls.
The independent reviewer assesses both content and production for claims, voice, safety,
feasibility, duration and promise delivery. Directions are not proof of rights or consent.

Revision must return a matching updated plan and pass the same validation/review again.
Malformed plans or stale speech are withheld. Ordinary generation does not include this
additional output. Production may require more tokens inside the same configured writer
cap; truncation blocks delivery rather than silently dropping sections.

## Explicit human feedback and approved examples

```text
/feedback POST_ID accept السبب
/feedback POST_ID reject السبب
```

Feedback records human opinion, including disagreements with engine decisions. It never
changes acceptance gates, prompts, thresholds, model weights or dictionary entries by itself.
Only the post's chat or the configured owner can assess that record.

The owner can explicitly approve an example or corrected text:

```text
/example story moment | سبب اعتماد الصياغة
STORY: هسه خل نشوف شنو يحتاج زبونك.
INTERACTION: شنو رأيك؟
```

Use the native content structure and an appropriate format/mode. `/example remove ID`
removes an example. Approved samples are stored under `STATE_DIR/data/reviewed_examples.json`.
Only the latest two matching format/mode examples enter a prompt, within the existing
example character cap. Approval requires native structural validity and a human reason;
it is not an external fact verification. Example facts are never evidence for new briefs.
New samples are not seeded as human-approved by the software or evaluation harness.
Removing/approving refreshes in-process prompt caches. No other chat can promote examples.

## Outcomes and experiment ledger

For an existing post, record a manual observation:

```text
/results POST_ID {"metric":"replies","value":4,"denominator":200,"window_hours":24,"source":"manual_insights"}
```

Metric names must suit the profile or a recognized objective measurement. Values must be
finite and nonnegative. Window and source are required; denominator is optional and stored
explicitly. `ad_spend` and `attributed_revenue` require currency, such as `"currency":"IQD"`.
No currency conversion, ROAS-to-profit inference, action-to-unique-person inference, or
automatic outcome ingestion occurs. Accounts/feature-specific availability remains to be
verified before an official provider integration.

Register a comparison:

```text
/experiment {"baseline_post_id":"ID1","variant_post_id":"ID2","variable":"opening","hypothesis":"افتتاحية أوضح تجيب ردود مرتبطة بالموضوع","window_hours":24}
```

Variables: opening, cta, visuals or narrative. Records must be distinct and match native
format, Story mode, objective, journey stage and distribution. Registration stores the
hypothesis/window; it does not prove only one variable changed, randomize exposure,
select a winner, or infer causation. Compare matching measurement windows and sources
manually, with sample sizes, before proposing a change.

`/report` returns this chat's quality/usage summary, latest human feedback, disagreement
counts, revision count, p50/p95 latency, estimated cost, unknown usage count, separate
cohorts, recent manual outcomes and experiment records. Paid and organic cohorts remain
separate. It is a descriptive report, not a growth forecast. Email subscriptions and
qualified inquiries remain separate metrics.

Events persist in `STATE_DIR/data/editorial_events.jsonl`; generated/clarification usage
retains its original JSONL store. Feedback/outcome/experiment commands make no AI calls
and do not consume generation quota. Data is not automatically deleted or synchronized
to an external service. Back up the persistent disk; this implementation assumes one
worker and does not provide multi-process transactional state or automatic retention.

## Knowledge and reviewer policy

`knowledge/source_lessons.toml` separates source provenance from selected lessons. It
records the uploaded compilation, BrandGhost, the commercial third-party TikTok article,
and Orbit's practitioner guidance, with scope and confidence status. `checked_at` is empty:
no claim is made that a live official source was checked. Small format/distribution-specific
subsets enter prompts; entire source documents and their embedded commands do not.

Included: audience intent, native variety, useful interactions, resource context, Highlights
as an editorial option, sustainable cadence, production distinctions, ethical persuasion,
repurposing and objective-specific measurement. Not promoted into rules: fixed daily Story
counts, 40/40/20 allocation, three-second guarantees, 40% sound-off statistics, caption
engagement optima, conversion thresholds, technical hashtag limits or recommendation
eligibility. Those require appropriate evidence and current official verification.

Reviewer policy asks whether reasoning connects, the opening is paid off, facts are
supported, Iraqi voice is natural, the medium is respected, filming is feasible, and the
next action is appropriate/real. 4Cs remain review criteria, not a content template.

## Test and evaluation procedure

```bash
python -m unittest discover -s tests -v
python -m compileall -q bot tests scripts
python scripts/evaluate_formats.py --mode offline --output /tmp/content-contracts.json
python scripts/benchmark_quality.py
```

The 36 offline shared-topic cases cover three topics across all 12 formats using explicitly
synthetic drafts and mocked reviews. They test routing, structure, bounded calls and data
handoff. They do **not** validate semantic quality, real Iraqi authenticity, factual accuracy,
actual latency, billing, performance improvement or growth. Human score fields stay empty.
Synthetic fixtures are not promoted into the approved example library.

After credentials are configured through secret settings, run:

```bash
python scripts/evaluate_formats.py --mode live --limit 12 --max-usd 3 --output /tmp/live-drafts.json
```

The harness makes model calls only: it does not send Telegram messages, publish or change
pilot/example state. It stops at the observed-cost budget with a reservation before the
next run, and on unknown usage; provider billing can still exceed an estimate for the
current call. Review the saved drafts manually for character, coherence, voice, evidence,
promise delivery and next action. Then test the actual deployed Telegram commands,
quotas/restarts and persistence. `/version` identifies the running commit and source hash.


Final offline verification: **114 tests passed**, plus **36/36 cross-format contract cases**,
compilation and diff validation. Live testing was explicitly deferred by the owner after
credentials were found unavailable; it is not counted as passed or required before code
review. Human feedback and real audience results are still needed to establish improvement.
