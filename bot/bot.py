"""Telegram bot that writes Iraqi-dialect content with Claude.

Flow:
  /start  -> pick a format (story / carousel / reel / LinkedIn)
  send a topic as a text message -> bot replies with the generated content
  /format -> change format, /cancel -> reset

Environment variables (see .env.example):
  TELEGRAM_BOT_TOKEN  required, from @BotFather
  ANTHROPIC_API_KEY   required (or any credential the SDK resolves)
  ALLOWED_CHAT_IDS    optional, comma-separated chat IDs allowed to use the bot
"""

import logging
import os

from anthropic import AsyncAnthropic, APIStatusError, APIConnectionError
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from prompts import FORMATS, build_system_prompt

load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
log = logging.getLogger("iraqi-content-bot")

MODEL = "claude-opus-5-5"
MAX_TOKENS = 4000
TELEGRAM_LIMIT = 4000  # Telegram hard limit is 4096; keep a margin

claude = AsyncAnthropic()  # resolves ANTHROPIC_API_KEY from the environment

_allowed = {
    int(x) for x in os.getenv("ALLOWED_CHAT_IDS", "").split(",") if x.strip()
}

# Cache the system prompts once: they are constant for the life of the process.
SYSTEM_PROMPTS = {fmt: build_system_prompt(fmt) for fmt in FORMATS}


def _allowed_chat(update: Update) -> bool:
    if not _allowed:
        return True  # no allowlist configured -> open bot
    return update.effective_chat is not None and update.effective_chat.id in _allowed


def _format_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"fmt:{key}")]
        for key, (label, _) in FORMATS.items()
    ]
    return InlineKeyboardMarkup(buttons)


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
        "هلا بيك! 👋 اختار نوع المحتوى، وبعدين دزلي الموضوع كتابةً.",
        reply_markup=_format_keyboard(),
    )


async def cmd_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    await update.message.reply_text("شنو نوع المحتوى؟", reply_markup=_format_keyboard())


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    context.chat_data.pop("format", None)
    await update.message.reply_text("تمام، صفّرنا كلشي. /start حتى تبدي من جديد.")


async def on_format_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _allowed_chat(update):
        return
    key = query.data.removeprefix("fmt:")
    if key not in FORMATS:
        return
    context.chat_data["format"] = key
    label = FORMATS[key][0]
    await query.edit_message_text(
        f"تمام، اخترت {label}. هسة دزلي الموضوع (شنو تريد تكتب عنه؟)."
    )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    fmt = context.chat_data.get("format")
    if not fmt:
        await update.message.reply_text(
            "گبل شي اختار نوع المحتوى 👇", reply_markup=_format_keyboard()
        )
        return

    topic = update.message.text.strip()
    status = await update.message.reply_text("عاد أكتبلك… ⏳")

    try:
        response = await claude.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            # Stable system prompt is cached; the per-request topic goes in messages.
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPTS[fmt],
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": f"الموضوع: {topic}"}],
        )
    except APIConnectionError:
        log.exception("Anthropic connection error")
        await status.edit_text("ماكدرت أوصل للسيرفر، جرب مرة ثانية بعد شوية.")
        return
    except APIStatusError as e:
        log.exception("Anthropic API error %s", e.status_code)
        await status.edit_text("صار خطأ بالـ API. جرب مرة ثانية.")
        return

    usage = response.usage
    log.info(
        "fmt=%s in=%s out=%s cache_read=%s cache_write=%s",
        fmt,
        usage.input_tokens,
        usage.output_tokens,
        usage.cache_read_input_tokens,
        usage.cache_creation_input_tokens,
    )

    if response.stop_reason == "refusal":
        await status.edit_text("ما گدرت أكمل هذا الطلب. جرب موضوع ثاني.")
        return

    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        await status.edit_text("ما طلع شي، جرب تعيد صياغة الموضوع.")
        return

    await status.delete()
    for part in _chunks(text):
        await update.message.reply_text(part)
    await update.message.reply_text(
        "تريد نعيده بشكل ثاني؟ دزلي ملاحظتك، أو /format حتى تغير النوع."
    )


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("format", cmd_format))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CallbackQueryHandler(on_format_chosen, pattern=r"^fmt:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
