"""Telegram bot that writes Iraqi-dialect content.

Flow:
  /start -> format (story / carousel / reel / LinkedIn) -> angle -> topic (text)
  The bot replies with the caption and logs the post. /published <id> marks it as published.
  /format changes the format, /cancel resets.

Environment variables (see .env.example):
  TELEGRAM_BOT_TOKEN  required
  ANTHROPIC_API_KEY   required (writer and checker)
  NOUS_API_KEY        optional (fallback)
  OWNER_CHAT_ID       your Telegram chat ID: unlimited access and /pilot commands
  ALLOWED_CHAT_IDS    optional, comma-separated chat IDs with unlimited access
  Pilot users are added with /pilot add (see bot/pilot.py)
"""

import logging
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from pipeline import run_pipeline  # noqa: E402
from build_info import build_info  # noqa: E402
from quality import check  # noqa: E402
from briefs import Brief, parse_brief_input, render_brief  # noqa: E402
from production import validate_plan, render_plan  # noqa: E402
from editorial import feedback, record_result, report, approve_example, remove_example, register_experiment  # noqa: E402
from pilot import add as pilot_add, check as pilot_check, list_text, quota_text, set_active, is_owner  # noqa: E402
from postlog import log_post, mark_published  # noqa: E402
from prompts import ANGLE_BUTTONS, ANGLES, FORMATS, build_system_prompt  # noqa: E402

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
# httpx logs every request URL, and the Telegram token is part of that URL. Keep it out of logs.
for noisy in ("httpx", "httpcore", "telegram.request"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("iraqi-content-bot")

TELEGRAM_LIMIT = 4000  # Telegram hard limit is 4096; keep a margin

_allowed = {int(x) for x in os.getenv("ALLOWED_CHAT_IDS", "").split(",") if x.strip()}
SYSTEM_PROMPTS = {fmt: build_system_prompt(fmt) for fmt in FORMATS}


def _chat_id(update: Update) -> int:
    return update.effective_chat.id


def _allowed_chat(update: Update) -> bool:
    """Owner and allowlisted chats are unlimited. Pilots are checked again before each generation."""
    cid = _chat_id(update)
    if is_owner(cid) or cid in _allowed:
        return True
    from pilot import get_pilot
    return bool(get_pilot(cid) and get_pilot(cid).get("active"))


def _format_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"fmt:{key}")]
        for key, (label, _, _) in FORMATS.items()
    ])


def _angle_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data=f"ang:{key}")]
        for key, text in ANGLE_BUTTONS.items()
    ])


def _to_html(text: str) -> str:
    """Telegram HTML: escape the text, then turn **bold** into <b>bold</b>."""
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)


def _chunks(text: str, size: int = TELEGRAM_LIMIT):
    """Bound UTF-16 units (emoji count twice), preserving plain text exactly."""
    if size < 2:
        raise ValueError("chunk size must be at least two UTF-16 units")
    while text:
        units = 0
        cut = 0
        for char in text:
            width = 2 if ord(char) > 0xFFFF else 1
            if units + width > size:
                break
            units += width
            cut += 1
        if cut < len(text):
            newline = text.rfind("\n", 0, cut)
            if newline >= 0:
                cut = newline + 1
        yield text[:cut]
        text = text[cut:]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    await update.message.reply_text(
        "هلا بيك! 👋 اختار نوع المحتوى، وبعدين الزاوية، وبعدين دزلي الموضوع كتابةً.",
        reply_markup=_format_keyboard(),
    )


async def cmd_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    context.chat_data.pop("format", None)
    context.chat_data.pop("angle", None)
    context.chat_data.pop("pending_clarification", None)
    context.chat_data.pop("content_brief", None)
    await update.message.reply_text("شنو نوع المحتوى؟", reply_markup=_format_keyboard())


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    context.chat_data.clear()
    await update.message.reply_text("تمام، صفّرنا كلشي. /start حتى تبدي من جديد.")


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"رقم حسابك: {_chat_id(update)}\nارسله لصاحب البوت حتى يفعّلك.")


async def cmd_brief(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    raw = update.message.text.split(maxsplit=1)
    try:
        if len(raw) == 1:
            text = render_brief(context.chat_data.get("content_brief", Brief()))
            for part in _chunks(text):
                await update.message.reply_text(part)
            return
        if raw[1].strip() == "reset":
            context.chat_data.pop("content_brief", None)
        else:
            brief = parse_brief_input(raw[1])
            if context.chat_data.get("format"):
                brief.validate_format(context.chat_data["format"])
            context.chat_data["content_brief"] = brief
        context.chat_data.pop("pending_clarification", None)
        await update.message.reply_text("تم تحديث البريف. هسه دز الموضوع، أو /brief حتى تشوف الإعدادات.")
    except (ValueError, TypeError):
        await update.message.reply_text("صيغة البريف مو صحيحة. مثال:\n/brief\nالجمهور: أصحاب المحلات\nالهدف: تعليم\nالستوري: شرح")


async def cmd_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    try:
        _, pid, decision, reason = update.message.text.split(maxsplit=3)
        feedback(pid, _chat_id(update), decision, reason)
        await update.message.reply_text("تم تسجيل تقييمك. التقييم ما يغير النص أو قواعد البوت تلقائياً.")
    except (ValueError, TypeError):
        await update.message.reply_text("الصيغة: /feedback رقم_المنشور accept أو reject وبعدها سبب التقييم")


async def cmd_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    try:
        _, pid, raw = update.message.text.split(maxsplit=2)
        if len(raw) > 3000:
            raise ValueError('outcome too long')
        record_result(pid, _chat_id(update), json.loads(raw))
        await update.message.reply_text("تم تسجيل النتيجة كمعلومة يدوية، بدون افتراض إن المحتوى وحده سببها.")
    except (ValueError, TypeError):
        await update.message.reply_text('الصيغة: /results رقم_المنشور {"metric":"replies","value":4,"denominator":200,"window_hours":24,"source":"manual_insights"}')


async def cmd_experiment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    try:
        raw = update.message.text.split(maxsplit=1)[1]
        if len(raw) > 3000:
            raise ValueError('experiment too long')
        register_experiment(_chat_id(update), json.loads(raw))
        await update.message.reply_text("تم تسجيل الفرضية. قارن نفس فترة القياس؛ ما نعتبر النتيجة دليل سببي تلقائياً.")
    except (ValueError, TypeError, IndexError):
        await update.message.reply_text('الصيغة: /experiment {"baseline_post_id":"ID1","variant_post_id":"ID2","variable":"opening","hypothesis":"افتتاحية أوضح","window_hours":24}')


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    for part in _chunks(json.dumps(report(_chat_id(update)), ensure_ascii=False, indent=2)):
        await update.message.reply_text(part)


async def cmd_example(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(_chat_id(update)):
        return
    try:
        raw = update.message.text.split(maxsplit=1)[1]
        if raw.startswith('remove '):
            removed = remove_example(raw.split(maxsplit=1)[1].strip(), _chat_id(update))
            await update.message.reply_text("تم الحذف." if removed else "ما لكيت المثال.")
        else:
            header, text = raw.split('\n', 1)
            selection, reason = header.split('|', 1)
            fields = selection.split()
            identifier = approve_example(fields[0], fields[1] if len(fields) > 1 else 'moment',
                                         text, reason.strip(), _chat_id(update))
            await update.message.reply_text("تم اعتماد المثال: " + identifier)
        for fmt in FORMATS:
            SYSTEM_PROMPTS[fmt] = build_system_prompt(fmt)
    except (ValueError, TypeError, IndexError):
        await update.message.reply_text("الصيغة: /example story moment | سبب اعتماد المثال\nالنص بنفس بنية الفورمات. للحذف: /example remove رقم_المثال")


async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Report the responding worker's build, without credentials or user content."""
    if not _allowed_chat(update):
        return
    fmt = context.chat_data.get("format", "story")
    brief = context.chat_data.get("content_brief", Brief())
    system = build_system_prompt(fmt, brief=brief) if fmt in FORMATS else ""
    info = build_info(system)
    info["story_mode"] = brief.story_mode
    info["production_mode"] = str(brief.production).lower()
    await update.message.reply_text(
        "نسخة البوت اللي تجاوبك:\n" + "\n".join(f"{k}={v}" for k, v in info.items())
        + f"\nselected_format={fmt}")


async def cmd_quota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        await update.message.reply_text("الحساب مو مفعّل للتجربة. ارسل /id لصاحب البوت.")
        return
    await update.message.reply_text(quota_text(_chat_id(update)))


async def cmd_pilot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner only: /pilot add <chat_id> <name> [posts] [usd] | list | stop <chat_id> | resume <chat_id>"""
    if not is_owner(_chat_id(update)):
        return
    args = context.args or []
    if not args or args[0] == "list":
        await update.message.reply_text(list_text())
        return
    try:
        if args[0] == "add":
            cid, name = int(args[1]), args[2]
            posts = int(args[3]) if len(args) > 3 else 10
            usd = float(args[4]) if len(args) > 4 else 1.0
            pilot_add(cid, name, posts, usd)
            await update.message.reply_text(f"تم تفعيل {name} ({cid}): {posts} منشور، ${usd:.2f}")
        elif args[0] in ("stop", "resume"):
            ok = set_active(int(args[1]), args[0] == "resume")
            await update.message.reply_text("تم." if ok else "هذا الرقم مو مسجل.")
        else:
            await update.message.reply_text("الأوامر: add, list, stop, resume")
    except (IndexError, ValueError):
        await update.message.reply_text("الصيغة غلط. مثال: /pilot add 123456 Sara 10 1.0")


async def cmd_published(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    pid = " ".join(context.args).strip() if context.args else ""
    if not pid:
        await update.message.reply_text("اكتب الرقم هكذا: /published 20260101120000")
        return
    ok = mark_published(pid)
    await update.message.reply_text(
        "تم التسجيل كمنشور ✅" if ok else "ما لكيت هذا الرقم بالسجل."
    )


async def on_format_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _allowed_chat(update):
        return
    key = query.data.removeprefix("fmt:")
    if key not in FORMATS:
        return
    context.chat_data.pop("content_brief", None)
    context.chat_data["format"] = key
    context.chat_data.pop("angle", None)
    context.chat_data.pop("pending_clarification", None)
    await query.edit_message_text(
        f"تمام، اخترت {FORMATS[key][0]}. هسة اختار الزاوية:",
        reply_markup=_angle_keyboard(),
    )


async def on_angle_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _allowed_chat(update):
        return
    key = query.data.removeprefix("ang:")
    if key not in ANGLES:
        return
    context.chat_data.pop("pending_clarification", None)
    context.chat_data["angle"] = key
    await query.edit_message_text(f"الزاوية: {ANGLE_BUTTONS[key]}. هسة دزلي الموضوع كتابةً.")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    fmt = context.chat_data.get("format")
    angle = context.chat_data.get("angle")
    if not fmt:
        await update.message.reply_text("گبل شي اختار نوع المحتوى 👇", reply_markup=_format_keyboard())
        return
    if not angle:
        await update.message.reply_text("اختار الزاوية 👇", reply_markup=_angle_keyboard())
        return

    cid = _chat_id(update)
    ok, msg = pilot_check(cid)
    if not ok:
        await update.message.reply_text(msg)
        return

    topic = update.message.text.strip()
    pending = context.chat_data.pop("pending_clarification", None)
    resuming = bool(pending and pending["format"] == fmt and pending["angle"] == angle)
    if resuming:
        topic = (pending["topic"] + "\nسؤال التوضيح: " + pending["question"]
                 + "\nإجابة المستخدم: " + topic)
    brief = context.chat_data.get("content_brief", Brief())
    try:
        brief.validate_format(fmt)
    except ValueError:
        await update.message.reply_text("إعدادات البريف ما تناسب الفورمات. عدل /brief أو استخدم /brief reset.")
        return
    system = build_system_prompt(fmt, brief=brief) if "content_brief" in context.chat_data else SYSTEM_PROMPTS[fmt]
    status = await update.message.reply_text("عاد أكتبلك… ⏳")
    try:
        run = await run_pipeline(fmt, system, topic, ANGLES[angle],
                                 clarification_allowed=not resuming, brief=brief)
    except Exception:
        log.error("pipeline failed (%s)", type(sys.exc_info()[1]).__name__)
        await status.edit_text("صار خطأ بالاتصال بالموديل. جرب مرة ثانية بعد شوية.")
        return

    checked = run.checked
    # Enforce structure at the final delivery boundary, independently of pipeline status.
    # This guards against a future regression returning a wrongly accepted legacy layout.
    if checked.status == "accepted":
        delivery_failures = check(fmt, checked.text, story_mode=brief.story_mode)
        if checked.story_mode != brief.story_mode:
            delivery_failures.append("Story mode mismatch")
        if brief.production:
            try:
                validate_plan(checked.production_plan, checked.text, brief.duration_seconds)
            except (ValueError, TypeError):
                delivery_failures.append("invalid production plan")
        if delivery_failures or checked.refused:
            checked.failures = delivery_failures or ["writer refused"]
            checked.status = "blocked"
    runtime = build_info(system)
    log.info("generation build=%s source=%s prompt=%s quality=%s",
             runtime["commit"], runtime["source"], runtime["prompt"], checked.status)
    log.info("fmt=%s angle=%s provider=%s attempts=%s calls=%d cost=$%.5f",
             fmt, angle, checked.provider, checked.attempts, len(run.calls), run.cost_usd)

    usage_known = (all(c.usage_known for c in run.calls)
                   and all(t["status"] == "ok" for t in run.timings))
    pid = log_post({
        "chat_id": cid, "format": fmt, "angle": angle, "topic": topic, "provider": checked.provider,
        "attempts": checked.attempts, "failures": checked.failures,
        "quality_status": checked.status, "review_history": checked.review_history,
        "build": runtime, "planning": checked.planning,
        "objective": brief.purpose, "story_mode": brief.story_mode,
        "journey_stage": brief.journey_stage, "distribution": brief.distribution,
        "production_mode": brief.production,
        "elapsed_ms": run.elapsed_ms, "stage_timings": run.timings,
        "usage_known": usage_known,
        "quota_cost_usd": round(run.cost_usd if usage_known else max(run.cost_usd, 0.25), 6),
        "calls": len(run.calls), "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens, "cost_usd": round(run.cost_usd, 6),
    }, event="clarification" if checked.clarification else "generated")

    if checked.clarification:
        context.chat_data["pending_clarification"] = {
            "topic": topic, "format": fmt, "angle": angle, "question": checked.clarification}
        await status.edit_text(checked.clarification)
        return

    if checked.status != "accepted":
        await status.edit_text("⚠️ المسودة تحتاج مراجعة؛ ما اجتازت فحوص الجودة.\n"
                               + "\n".join(checked.failures)[:2500])
        return

    await status.delete()
    for part in _chunks(checked.text):
        await update.message.reply_text(part)
    if checked.failures:
        await update.message.reply_text("⚠️ تحقق يدوي قبل النشر:\n- " + "\n- ".join(checked.failures))
    if checked.production_plan:
        for part in _chunks(render_plan(checked.production_plan)):
            await update.message.reply_text(part)
    if checked.owner_note:
        await update.message.reply_text("📝 ملاحظة لك (لا تنشرها):\n" + checked.owner_note)
    await update.message.reply_text(
        f"رقم المنشور: {pid}\nبعد ما تنشره اكتب: /published {pid}\n"
        "تريد نعيده بشكل ثاني؟ دزلي ملاحظتك، أو /format حتى تغير النوع."
    )


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("format", cmd_format))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("published", cmd_published))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("quota", cmd_quota))
    app.add_handler(CommandHandler("version", cmd_version))
    app.add_handler(CommandHandler("brief", cmd_brief))
    app.add_handler(CommandHandler("feedback", cmd_feedback))
    app.add_handler(CommandHandler("results", cmd_results))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("experiment", cmd_experiment))
    app.add_handler(CommandHandler("example", cmd_example))
    app.add_handler(CommandHandler("pilot", cmd_pilot))
    app.add_handler(CallbackQueryHandler(on_format_chosen, pattern=r"^fmt:"))
    app.add_handler(CallbackQueryHandler(on_angle_chosen, pattern=r"^ang:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    runtime = build_info()
    log.info("bot started format_contract=%s commit=%s branch=%s source=%s",
             runtime["format_contract"], runtime["commit"], runtime["branch"], runtime["source"])
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
