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
4. بتلگرام: `/start` ← نوع المحتوى ← المنصة ← الستايل/الزاوية ← البنية ← الموضوع.
   Story: Instagram أو TikTok. Carousel: Instagram أو TikTok أو LinkedIn (مستند).
   فيديو قصير: Instagram Reel أو TikTok Video. LinkedIn: بوست أو مقال.
   باقي فورمات Instagram تبقى ضمن «فورمات إضافية». [تفاصيل التدفق والبنى](docs/CONTENT_NAVIGATION.md).

## الأوامر

| الأمر | الوظيفة |
|---|---|
| `/start` | بداية + اختيار النوع |
| `/format` | تغيير النوع |
| `/cancel` | تصفير الاختيار |
| `/diagnose ID` | تشخيص محاولة سابقة بدون توليد جديد، للحساب المعني أو صاحب البوت |
| `/version` | رقم نسخة البوت والفرع والفورمات للتشخيص |

## ملاحظات

- الموديل: `claude-sonnet-5-5`. الـ system prompt ثابت ومُخزّن بالكاش (`cache_control`)، فالطلبات المتكررة أرخص وأسرع. راقب `cache_read` بالـ logs.
- تقييد الاستخدام: حط `ALLOWED_CHAT_IDS` بالـ `.env` حتى ما يستعمله أي أحد.
- لتعديل النبرة أو القواعد، عدّل ملفات `guidelines/` و `formats/`. ما تحتاج تغيّر الكود.
- الحالة (اختيار النوع) محفوظة بالذاكرة، فإذا انتهى التشغيل ينمسح.

## AI quality review

See [Phase 2 architecture, configuration, tests and rollout](docs/AI_QUALITY_ENGINE.md).
The bot independently reviews native drafts and can revise weak sections once by default.
Failed or incomplete reviews are withheld from Telegram delivery. Publication remains manual.

Offline checks: `python -m unittest discover -s tests -v` after installing `bot/requirements.txt`.

Optional [copywriting frameworks and brief clarification](docs/FRAMEWORKS.md) use the existing analyst call while preserving native format contracts.

See the [source-learning roadmap](docs/LEARNING_ROADMAP.md) and [workflow/commands/testing guide](docs/SOURCE_LEARNING_GUIDE.md) for optional briefs, Story treatments, video production, human-reviewed examples and outcome tracking.

The [short Story flow](docs/STORY_FLOW.md) offers entertaining, educational, everyday-life, audience-question and question-answer styles before asking for a topic.
