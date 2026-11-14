# Content-Writer_Iraqi

مولّد محتوى باللهجة العراقية (ستوري، كاروسيل، ريلز، لينكدإن) مربوط بتلگرام، مبني على Claude API.

## البنية

```
guidelines/iraqi_dialect_style_guide.md   دليل اللهجة والنبرة (مشترك لكل الفورمات)
formats/stories/guide.md                  قواعد الستوري
formats/carousels/guide.md                قواعد الكاروسيل
formats/reels/guide.md                    قواعد الريلز
formats/linkedin/guide.md                 قواعد لينكدإن
bot/prompts.py                            يبني الـ system prompt من الملفات أعلاه
bot/bot.py                                بوت تلگرام + استدعاء Claude
```

## التشغيل

1. **أنشئ بوت:** كلّم [@BotFather](https://t.me/BotFather) في تلگرام، سوّ `/newbot`، وخذ التوكن.
2. **جهّز المفاتيح:**
   ```bash
   cp .env.example .env
   ```
   عبّي `TELEGRAM_BOT_TOKEN` و `ANTHROPIC_API_KEY` بملف `.env`.
3. **ثبّت وشغّل:**
   ```bash
   cd bot
   pip install -r requirements.txt
   python bot.py
   ```
4. بتلگرام: `/start` ← نوع المحتوى (Post / Story / Reel / Live Topic) ← المنصة ← استراتيجية المحتوى ← بنية السكربت ← الموضوع.
   ثلاث طبقات للمحتوى؛ المنصة اختيار للنشر. فورمات إضافية والاختيارات السابقة تبقى متاحة من القائمة.
   Story: Instagram أو TikTok. Carousel: Instagram أو TikTok أو LinkedIn (مستند).
   فيديو قصير: Instagram Reel أو TikTok Video. LinkedIn: بوست أو مقال.
   باقي فورمات Instagram تبقى ضمن «فورمات إضافية». [تفاصيل التدفق والبنى](docs/CONTENT_NAVIGATION.md).

## الأوامر

| الأمر | الوظيفة |
|---|---|
| `/start` | بداية + اختيار النوع |
| `/format` | تغيير النوع |
| `/topics` | مكتبة المواضيع: المحور ← الموضوع ← تأكيد الكتابة |
| `/topic CONT-568` | تحميل موضوع بإعداداته وزاويته قبل تأكيد الكتابة |
| `/cancel` | تصفير الاختيار |
| `/diagnose ID` | تشخيص محاولة سابقة بدون توليد جديد، للحساب المعني أو صاحب البوت |
| `/version` | رقم نسخة البوت والفرع والفورمات للتشخيص |

## ملاحظات

- الموديل: `claude-sonnet-5-5`. الـ system prompt ثابت ومُخزّن بالكاش (`cache_control`)، فالطلبات المتكررة أرخص وأسرع. راقب `cache_read` بالـ logs.
- تقييد الاستخدام: حط `ALLOWED_CHAT_IDS` بالـ `.env` حتى ما يستعمله أي أحد.
- لتعديل النبرة أو القواعد، عدّل ملفات `guidelines/` و `formats/`. ما تحتاج تغيّر الكود.
- الحالة (اختيار النوع) محفوظة بالذاكرة، فإذا انتهى التشغيل ينمسح.

## AI quality review

Telegram first decides whether your request needs research, direct writing, a style-only
rewrite, or clarification. Neutral audience questions and subjective rewrites can skip
search while retaining independent review. Factual research uses up to two Anthropic searches.
Enable web search for the Anthropic organization associated with `ANTHROPIC_API_KEY`.
For Iraqi exchange rates and regulatory topics, the bot requires an official primary source,
checks dates and rate applicability, and sends source links separately from the script.
If sources are missing or the premise cannot be supported, it asks for clarification or
withholds writing with a reason. Web search adds $0.01 per search plus model token costs.
See [research and review policy](docs/AI_QUALITY_ENGINE.md#review-and-revision-policy).

With `NOUS_API_KEY` configured, exhausted Anthropic credit can fail over to Nous for
routing, writing and review. The default Nous ID is `anthropic/claude-sonnet-5.5`;
the older repository spelling ending in `5-5` is normalized automatically. The attempt
stays on Nous after failover, keeps all checks and uses separately verified token-price
estimates. Unknown custom pricing stops further calls. Anthropic's hosted search tool
is not available through this fallback; research-dependent requests stop with a clear reason.

See [Phase 2 architecture, configuration, tests and rollout](docs/AI_QUALITY_ENGINE.md).
The bot independently reviews native drafts and can revise weak sections once by default.
Failed or incomplete reviews are withheld from Telegram delivery. Publication remains manual.

Offline checks: `python -m unittest discover -s tests -v` after installing `bot/requirements.txt`.

Optional [copywriting frameworks and brief clarification](docs/FRAMEWORKS.md) use the existing analyst call while preserving native format contracts.

See the [source-learning roadmap](docs/LEARNING_ROADMAP.md) and [workflow/commands/testing guide](docs/SOURCE_LEARNING_GUIDE.md) for optional briefs, Story treatments, video production, human-reviewed examples and outcome tracking.

The [short Story flow](docs/STORY_FLOW.md) offers entertaining, educational, everyday-life, audience-question and question-answer styles before asking for a topic.

## Audit fixes and verification

See the [execution plan](docs/FIX_EXECUTION_PLAN.md). Run
`python scripts/verify_fixes.py` to regenerate the issue-by-issue report and full test results,
or add `--watch` to automatically recheck after code, test or deployment-config changes.
Open `test_reports/fixes/index.html` for a page that refreshes every five seconds.
Generated reports are ignored by Git; CI uploads them as the `audit-fix-report` artifact.
Watch mode only runs while its process is alive. Offline success is separate from live
credentials, actual GitHub/Render settings and deployment.

عند حجب مسودة لأسباب تحريرية، البوت يستشير الموديل المتقدم ضمن الحدود المتبقية
ويقترح زوايا قريبة. اختار اقتراح حتى نعيد الكتابة والفحوصات؛ الاقتراح مو ضمان
لاجتياز الجودة. إذا المستشار ما گدر يشتغل، البوت يوضح السبب.

## مكتبة المواضيع

المواضيع المنقحة مرفقة في `knowledge/topics/bot_topics.json`، مع معرفاتها الأصلية.
`/topics` يفتح المكتبة، و`/topic CONT-568` يحمّل الموضوع مع الميزة والاستراتيجية
والبنية والبريف. تبقى منصة النشر الحالية إذا تناسب ميزة الموضوع؛ وإلا تُستخدم
الصيغة الصالحة المحددة في السجل. اختيار الموضوع يعرض معاينة، وزر التأكيد فقط يبدأ
المسار المعتاد للبحث عند الحاجة والكتابة والمراجعة. [التفاصيل وحدود الاستيراد](docs/TOPIC_LIBRARY.md).

## Web preview and execution plan

The first web milestone supports Instagram Story through the existing writing engine,
with private preview sign-in, history, clarification, related-topic choices and reviewed
edit requests. [Run the owner preview](docs/WEB_PREVIEW.md).
[Goals, milestones and tasks](docs/PROJECT_EXECUTION.md) track progress toward invited
creator testing. Demo mode is sample-only; multi-creator accounts and voice profiles
are subsequent milestones.
