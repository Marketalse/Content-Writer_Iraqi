# Installment-selling Reel test

Topic: **شلون تبيع بالأقساط بدون ما تضيع فلوسك**

Target: Instagram Reel, `demo` narrative. Live Claude execution is pending workspace
credentials. The results below are **offline protocol replay**, using explicitly synthetic
drafts/reviewer responses. They are not the deployed model's text, proof of creative quality
or evidence of a successful live generation.

## What the production evidence establishes

Record `20261109105201-1666d7e1` completed planning without fallback and received a valid
review. Factual integrity, safety, topic and voice gates passed; `format_identity` failed.
The record does not include the actual draft or free-text review reasons, so the exact
creative defect cannot be established from that diagnostic alone.

The code did establish one workflow limitation: any failed gate immediately stopped the
pipeline, including an isolated, actionable format failure. Thus it never used the configured
revision slot to improve presentation. This is reproducible independently of the topic.

## Bounded fix and checks

An isolated explicit `format_identity=fail` can now use the existing section-revision slot
only when every other mandatory gate passes and the reviewer supplies valid section issues.
Uncertainty, factual/safety/topic/voice failures and missing issues still stop the pipeline.
The changed candidate must pass native checks, verified-fact preservation and a fresh full
independent review. A high score cannot override a failed format gate. No failed/unreviewed
candidate is eligible for manual draft delivery. `QUALITY_REPAIR_FORMAT=false` restores the
previous stop behavior. The default revision/call/token/cost limits remain unchanged.

The demonstration guidance now asks for a concrete visible worked illustration and matching
speech/action; generic advice with generic B-roll is insufficient. Topic wording that suggests
zero loss must be framed as risk reduction, not a guaranteed financial result.

| Synthetic protocol replay | Result | Logical calls | What it proves |
|---|---|---:|---|
| Format repair disabled | Blocked at first format failure | 3 | Previous early-stop control flow |
| Format repair enabled | Revised and accepted after mock all-pass review | 5 | Bounded patch and complete reassessment path |

Both fixture drafts pass native-section validation. Their creative assessments are synthetic.
Normal valid drafts still use three calls; format repair adds two calls within the existing
five-call one-revision budget, so it can increase latency and spend compared with early rejection.
No higher budget or automatic extra retry was introduced.

The full **206-test** suite passes, including failure/uncertainty of other gates, missing
review issues, disabled/exhausted revision slots, a failed second format review with score 10,
verified-fact removal, budget-stopped reassessment and manual-only delivery after all gates
pass below threshold. Offline cross-format cases remain 39/39; compile and whitespace checks pass.

## Inspect the illustrative copy

The fixture at `tests/fixtures/installment_reel_demo.json` contains the complete before/after
copy and scoped patch. It is authored test data, not a live provider output. The revised version
shows an explicitly hypothetical installment-payment tracker: create payment/date/status
columns, update a payment's status on hypothetical receipt, and mark an overdue payment.
It uses no customer data, prices, interest rates, jurisdiction-specific legal claims or promised
collection results. The audience can see the demonstrated process instead of generic shop footage.

Illustrative spoken excerpt:

> هذا مثال افتراضي: هاي طلبية بالأقساط، وهذا سجل متابعة دفعاتها بعد الترتيب. خل نسويه سوا.
> نكتب الدفعة المتفق عليها، موعدها، وحالتها: مدفوعة لو بعدها. من نستلم دفعة بالمثال، نغيّر
> حالتها ونحدّث الباقي حسب اللي انقبض فعلاً.

The full script explicitly says tracking does not guarantee collection or remove late-payment risk.

## Reproduce

```bash
python scripts/test_topic.py --mode offline --no-format-repair --output /tmp/installments-before.json
python scripts/test_topic.py --mode offline --output /tmp/installments-after.json
python scripts/test_topic.py --mode live --max-usd 0.25 --output /tmp/installments-live.json
```

Live mode requires `ANTHROPIC_API_KEY` in the workspace's secret settings. Never paste it in
chat or commit it. The command runs the real pipeline for this exact topic/format/structure,
without Telegram messages or publishing. It uses the existing observed-spend stop, not an exact
billing guarantee; per-call limits, max five logical calls, timeouts and output budgets also apply.
If no key is configured, the command exits before contacting a model. Inspect live content,
review history and factual limitations before considering the test successful.

The live command was also attempted in this workspace on November 9. It exited at preflight
with code 2 because `ANTHROPIC_API_KEY` was unavailable; no provider request was made. The
user selected configuring a key, but that selection is not a configured secret. The live
result therefore remains pending and must not be inferred from the offline accepted result.
