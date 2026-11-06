"""Telegram bot that writes Iraqi-dialect content.

Flow:
  /start -> format (story / carousel / reel / LinkedIn) -> angle -> topic (text)
  The bot replies with the caption and logs the post. /published <id> marks it as published.
  /format changes the format, /cancel resets.

Environment variables (see .env.example):
  TELEGRAM_BOT_TOKEN  required
  ANTHROPIC_API_KEY   required (writer and checker)
  NOUS_API_KEY        optional (fallback)
  ALLOWED_CHAT_IDS    optional, comma-separated chat IDs allowed to use the bot
"""

import logging
import os
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
from postlog import log_post, mark_published  # noqa: E402
from prompts import ANGLES, FORMATS, build_system_prompt  # noqa: E402

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
# httpx logs every request URL, and the Telegram token is part of that URL. Keep it out of logs.
for noisy in ("httpx", "httpcore", "telegram.request"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("iraqi-content-bot")

TELEGRAM_LIMIT = 4000  # Telegram hard limit is 4096; keep a margin

_allowed = {int(x) for x in os.getenv("ALLOWED_CHAT_IDS", "").split(",") if x.strip()}
SYSTEM_PROMPTS = {fmt: build_system_prompt(fmt) for fmt in FORMATS}


def _allowed_chat(update: Update) -> bool:
    if not _allowed:
        return True
    return update.effective_chat is not None and update.effective_chat.id in _allowed


def _format_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"fmt:{key}")]
        for key, (label, _, _) in FORMATS.items()
    ])


def _angle_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data=f"ang:{key}")]
        for key, text in ANGLES.items()
    ])


def _chunks(text: str, size: int = TELEGRAM_LIMIT):
    while text:
        if len(text) <= size:
            yield text
            return
        cut = text.rfind("\n", 0, size)
        if cut <= 0:
            cut = size
        yield text[:cut]
        text = text[cut:].lstrip("\n")


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
    await query.edit_message_text(f"الزاوية: {ANGLES[key]}. هسة دزلي الموضوع كتابةً.")


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

    topic = update.message.text.strip()
    status = await update.message.reply_text("عاد أكتبلك… ⏳")
    try:
        run = await run_pipeline(fmt, SYSTEM_PROMPTS[fmt], topic, ANGLES[angle])
    except Exception:
        log.exception("pipeline failed")
        await status.edit_text("صار خطأ بالاتصال بالموديل. جرب مرة ثانية بعد شوية.")
        return

    checked = run.checked
    log.info("fmt=%s angle=%s provider=%s attempts=%s calls=%d cost=$%.5f",
             fmt, angle, checked.provider, checked.attempts, len(run.calls), run.cost_usd)

    if checked.refused:
        await status.edit_text("ما گدرت أكمل هذا الطلب. جرب موضوع ثاني.")
        return
    if not checked.text:
        await status.edit_text("ما طلع شي، جرب تعيد صياغة الموضوع.")
        return

    pid = log_post({
        "format": fmt, "angle": angle, "topic": topic, "provider": checked.provider,
        "attempts": checked.attempts, "failures": checked.failures,
        "calls": len(run.calls), "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens, "cost_usd": round(run.cost_usd, 6),
    })

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
    app.add_handler(CallbackQueryHandler(on_format_chosen, pattern=r"^fmt:"))
    app.add_handler(CallbackQueryHandler(on_angle_chosen, pattern=r"^ang:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
