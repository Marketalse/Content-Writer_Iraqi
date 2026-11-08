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
    await update.message.reply_text("شنو نوع المحتوى؟", reply_markup=_format_keyboard())


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    context.chat_data.clear()
    await update.message.reply_text("تمام، صفّرنا كلشي. /start حتى تبدي من جديد.")


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"رقم حسابك: {_chat_id(update)}\nارسله لصاحب البوت حتى يفعّلك.")


async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Report the responding worker's build, without credentials or user content."""
    if not _allowed_chat(update):
        return
    fmt = context.chat_data.get("format", "story")
    info = build_info(SYSTEM_PROMPTS.get(fmt, ""))
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
    context.chat_data["format"] = key
    context.chat_data.pop("angle", None)
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
    status = await update.message.reply_text("عاد أكتبلك… ⏳")
    try:
        run = await run_pipeline(fmt, SYSTEM_PROMPTS[fmt], topic, ANGLES[angle])
    except Exception:
        log.error("pipeline failed (%s)", type(sys.exc_info()[1]).__name__)
        await status.edit_text("صار خطأ بالاتصال بالموديل. جرب مرة ثانية بعد شوية.")
        return

    checked = run.checked
    # Enforce structure at the final delivery boundary, independently of pipeline status.
    # This guards against a future regression returning a wrongly accepted legacy layout.
    if checked.status == "accepted":
        delivery_failures = check(fmt, checked.text)
        if delivery_failures or checked.refused:
            checked.failures = delivery_failures or ["writer refused"]
            checked.status = "blocked"
    runtime = build_info(SYSTEM_PROMPTS[fmt])
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
        "build": runtime,
        "elapsed_ms": run.elapsed_ms, "stage_timings": run.timings,
        "usage_known": usage_known,
        "quota_cost_usd": round(run.cost_usd if usage_known else max(run.cost_usd, 0.25), 6),
        "calls": len(run.calls), "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens, "cost_usd": round(run.cost_usd, 6),
    })

    if checked.status != "accepted":
        await status.edit_text("⚠️ المسودة تحتاج مراجعة؛ ما اجتازت فحوص الجودة.\n"
                               + "\n".join(checked.failures)[:2500])
        return

    await status.delete()
    for part in _chunks(checked.text):
        await update.message.reply_text(part)
    if checked.failures:
        await update.message.reply_text("⚠️ تحقق يدوي قبل النشر:\n- " + "\n- ".join(checked.failures))
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
