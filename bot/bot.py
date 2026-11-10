"""Telegram bot that writes Iraqi-dialect content.

Flow:
  /start -> content family -> platform/subtype -> style -> narrative -> topic (text)
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
from dataclasses import replace

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

from diagnostics import diagnostic_report, failure_message
from delivery_policy import manual_review_eligible, manual_review_warning
from pipeline import run_pipeline  # noqa: E402
from build_info import build_info  # noqa: E402
from quality import check, render_story_copy  # noqa: E402
from briefs import Brief, parse_brief_input, render_brief  # noqa: E402
from production import validate_plan, render_plan  # noqa: E402
from editorial import feedback, record_result, report, approve_example, remove_example, register_experiment  # noqa: E402
from pilot import add as pilot_add, check as pilot_check, list_text, quota_text, set_active, is_owner  # noqa: E402
from postlog import log_post, mark_published  # noqa: E402
from content_choices import FAMILIES, structure_options, get_structure, family_for_format
from prompts import ANGLES, FORMATS, build_system_prompt, angle_options, angle_description  # noqa: E402
from story_styles import STORY_STYLES, STORY_ANGLE_KEYS, is_story  # noqa: E402

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
        [InlineKeyboardButton(label, callback_data=f"fam:{key}")]
        for key, (label, _) in FAMILIES.items()
    ])


def _platform_keyboard(family: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(FORMATS[key][0], callback_data=f"fmt:{key}")]
        for key in FAMILIES[family][1]
    ] + [[InlineKeyboardButton("↩️ أنواع المحتوى", callback_data="fam:root")]])


def _structure_keyboard(fmt: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(item.label, callback_data=f"str:{fmt}:{item.id}")]
        for item in structure_options(fmt)
    ] + [[InlineKeyboardButton("↩️ الستايل / الزاوية", callback_data="back:structure")]])


def _clear_selection(data: dict) -> None:
    for key in ('family', 'menu_stage', 'format', 'angle', 'structure_id',
                'pending_clarification', 'content_brief'):
        data.pop(key, None)


def _angle_keyboard(fmt: str | None = None, *, scoped: bool = False) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data=f"pick:{fmt}:{key}" if scoped else f"ang:{key}")]
        for key, text in angle_options(fmt).items()
    ] + ([[InlineKeyboardButton("↩️ المنصة / النوع", callback_data="back:angle")]] if scoped else []))


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
    _clear_selection(context.chat_data)
    await update.message.reply_text(
        "الخطوة 1/5 — نوع المحتوى\nهلا بيك! 👋 اختار النوع، بعدها المنصة والستايل والبنية، وبعدين الموضوع.",
        reply_markup=_format_keyboard(),
    )


async def cmd_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    _clear_selection(context.chat_data)
    await update.message.reply_text("الخطوة 1/5 — شنو نوع المحتوى؟", reply_markup=_format_keyboard())


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
            if not brief.structure_id and context.chat_data.get('structure_id'):
                brief = replace(brief, structure_id=context.chat_data['structure_id'])
            if context.chat_data.get("format"):
                brief.validate_format(context.chat_data["format"])
            context.chat_data["content_brief"] = brief
            if brief.structure_id:
                context.chat_data['structure_id'] = brief.structure_id
            if is_story(context.chat_data.get("format")) and brief.story_intent != 'auto':
                context.chat_data["angle"] = 'story_' + brief.story_intent
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


async def cmd_diagnose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    parts = update.message.text.split()
    if len(parts) != 2 or not re.fullmatch(r'[A-Za-z0-9-]{1,80}', parts[1]):
        await update.message.reply_text("الصيغة: /diagnose رقم_المراجعة")
        return
    try:
        result = diagnostic_report(parts[1], _chat_id(update))
    except ValueError:
        await update.message.reply_text("ما لكيت مراجعة متاحة لهذا الحساب بهالرقم.")
        return
    for part in _chunks(json.dumps(result, ensure_ascii=False, indent=2)):
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
                                         text, reason.strip(), _chat_id(update),
                                         story_intent=fields[2] if len(fields) > 2 else 'auto')
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
    info["bot_username"] = _bot_username(context)
    info["menu_stage"] = context.chat_data.get("menu_stage", "legacy_or_not_started")
    info["family"] = context.chat_data.get("family", "not_selected")
    info["story_mode"] = brief.story_mode
    info["story_intent"] = brief.story_intent
    info["structure_id"] = context.chat_data.get("structure_id", brief.structure_id)
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


def _bot_username(context) -> str:
    """Use the already initialized bot identity; never inspect the bot token."""
    try:
        return getattr(getattr(context, 'bot', None), 'username', None) or 'unknown'
    except RuntimeError:
        return 'unknown'


async def _show_platform(query, data: dict, family: str):
    _clear_selection(data)
    data.update(family=family, menu_stage='platform')
    prompt = "بوست لو مقال؟" if family == 'linkedin' else "لأي منصة تريد هذا المحتوى؟"
    await query.edit_message_text("الخطوة 2/5 — " + FAMILIES[family][0] + "\n" + prompt,
                                 reply_markup=_platform_keyboard(family))


async def on_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _allowed_chat(update):
        return
    data = context.chat_data
    previous = query.data.removeprefix('back:')
    if previous != data.get('menu_stage'):
        return
    family, fmt = data.get('family'), data.get('format')
    if family not in FAMILIES or fmt not in FAMILIES[family][1]:
        return
    if previous == 'angle':
        await _show_platform(query, data, family)
    elif previous == 'structure':
        for key in ('angle', 'structure_id', 'content_brief', 'pending_clarification'):
            data.pop(key, None)
        data['menu_stage'] = 'angle'
        await query.edit_message_text("الخطوة 3/5 — " + FORMATS[fmt][0] + "\nاختار الستايل / الزاوية:",
                                     reply_markup=_angle_keyboard(fmt, scoped=True))
    elif previous == 'topic':
        data.pop('structure_id', None)
        data.pop('pending_clarification', None)
        if 'content_brief' in data:
            data['content_brief'] = replace(data['content_brief'], structure_id='')
        data['menu_stage'] = 'structure'
        await query.edit_message_text("الخطوة 4/5 — " + FORMATS[fmt][0] + "\nاختار البنية:",
                                     reply_markup=_structure_keyboard(fmt))


async def on_family_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _allowed_chat(update):
        return
    family = query.data.removeprefix("fam:")
    if family != 'root' and family not in FAMILIES:
        return
    _clear_selection(context.chat_data)
    if family == 'root':
        await query.edit_message_text("الخطوة 1/5 — اختار نوع المحتوى:", reply_markup=_format_keyboard())
        return
    await _show_platform(query, context.chat_data, family)


async def on_structure_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _allowed_chat(update):
        return
    parts = query.data.split(':')
    if len(parts) != 3:
        return
    _, fmt, key = parts
    data = context.chat_data
    if data.get('menu_stage') != 'structure' or data.get('format') != fmt:
        return
    try:
        selected = get_structure(fmt, key)
    except ValueError:
        return
    data['structure_id'] = key
    data['content_brief'] = replace(data.get('content_brief', Brief()), structure_id=key)
    data.pop('pending_clarification', None)
    data['menu_stage'] = 'topic'
    intent = STORY_ANGLE_KEYS.get(data.get('angle'))
    prompt = STORY_STYLES[intent]['topic_prompt'] if intent else "هسه دزلي الموضوع كتابةً."
    await query.edit_message_text("الخطوة 5/5 — " + FORMATS[fmt][0] + "\nالبنية: " + selected.label + "\n" + prompt,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ غيّر البنية", callback_data="back:topic")]]))


async def on_format_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _allowed_chat(update):
        return
    key = query.data.removeprefix("fmt:")
    if key not in FORMATS:
        return
    family = context.chat_data.get('family')
    if not family:
        # An old inline format button must enter today's platform chooser.
        await _show_platform(query, context.chat_data, family_for_format(key))
        return
    if context.chat_data.get('menu_stage') != 'platform' or key not in FAMILIES[family][1]:
        return
    context.chat_data.pop("content_brief", None)
    context.chat_data.pop("structure_id", None)
    context.chat_data["format"] = key
    context.chat_data['menu_stage'] = 'angle'
    context.chat_data.pop("angle", None)
    context.chat_data.pop("pending_clarification", None)
    await query.edit_message_text(
        "الخطوة 3/5 — " + FORMATS[key][0] + "\n" +
        ("ستوري قصيرة، تقريباً ٣٠ ثانية: شنو الستايل اللي تريده؟"
         if is_story(key) else "هسة اختار الزاوية:"),
        reply_markup=_angle_keyboard(key, scoped=True),
    )


async def on_angle_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _allowed_chat(update):
        return
    fmt = context.chat_data.get("format")
    if query.data.startswith('pick:'):
        parts = query.data.split(':')
        if (len(parts) != 3 or parts[1] != fmt
                or context.chat_data.get('menu_stage') != 'angle'):
            return
        key = parts[2]
    else:
        if context.chat_data.get('menu_stage'):
            return  # Saved legacy callbacks cannot skip the current menu flow.
        key = query.data.removeprefix("ang:")
    if fmt not in FORMATS:
        if query.data.startswith('ang:') and key in {*ANGLES, *STORY_ANGLE_KEYS}:
            _clear_selection(context.chat_data)
            await query.edit_message_text("الخطوة 1/5 — حدّثنا الاختيارات، اختار نوع المحتوى:",
                                         reply_markup=_format_keyboard())
        return
    if key not in ANGLES and not (is_story(fmt) and key in STORY_ANGLE_KEYS):
        return
    if not context.chat_data.get('family'):
        await _show_platform(query, context.chat_data, family_for_format(fmt))
        return
    context.chat_data.pop("pending_clarification", None)
    context.chat_data["angle"] = key
    if is_story(fmt) and key in STORY_ANGLE_KEYS:
        intent = STORY_ANGLE_KEYS[key]
        style = STORY_STYLES[intent]
        current = context.chat_data.get("content_brief", Brief())
        context.chat_data["content_brief"] = replace(current, story_mode="moment", story_intent=intent,
            purpose=style['purpose'], duration_seconds=30, production=False)
    else:
        if is_story(fmt) and 'content_brief' in context.chat_data:
            context.chat_data['content_brief'] = replace(context.chat_data['content_brief'], story_intent='auto')
    context.chat_data['menu_stage'] = 'structure'
    await query.edit_message_text("الخطوة 4/5 — " + FORMATS[fmt][0] + "\nاختار بنية تناسب الفكرة:",
                                 reply_markup=_structure_keyboard(fmt))


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed_chat(update):
        return
    fmt = context.chat_data.get("format")
    angle = context.chat_data.get("angle")
    if not fmt:
        family = context.chat_data.get('family')
        await update.message.reply_text("اختار المنصة 👇" if family else "گبل شي اختار نوع المحتوى 👇",
            reply_markup=_platform_keyboard(family) if family else _format_keyboard())
        return
    if not angle:
        await update.message.reply_text("شنو الستايل اللي تريده؟" if is_story(fmt) else "اختار الزاوية 👇",
                                        reply_markup=_angle_keyboard(fmt, scoped=bool(context.chat_data.get("family"))))
        return

    if context.chat_data.get('family') and not context.chat_data.get('structure_id'):
        await update.message.reply_text("اختار البنية قبل الموضوع 👇", reply_markup=_structure_keyboard(fmt))
        return

    try:
        selected_angle = angle_description(fmt, angle)
    except KeyError:
        context.chat_data.pop("angle", None)
        await update.message.reply_text("اختار الستايل من جديد.", reply_markup=_angle_keyboard(fmt, scoped=bool(context.chat_data.get("family"))))
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
    if context.chat_data.get('structure_id'):
        brief = replace(brief, structure_id=context.chat_data['structure_id'])
    if is_story(fmt) and angle in STORY_ANGLE_KEYS and brief.story_mode == 'moment':
        intent = STORY_ANGLE_KEYS[angle]
        brief = replace(brief, story_intent=intent, duration_seconds=30)
        if 'content_brief' not in context.chat_data:
            brief = replace(brief, purpose=STORY_STYLES[intent]['purpose'])
    try:
        brief.validate_format(fmt)
    except ValueError:
        await update.message.reply_text("إعدادات البريف ما تناسب الفورمات. عدل /brief أو استخدم /brief reset.")
        return
    system = build_system_prompt(fmt, brief=brief) if "content_brief" in context.chat_data or brief.story_intent != "auto" or brief.structure_id else SYSTEM_PROMPTS[fmt]
    status = await update.message.reply_text("أراجع طلبك وأحدد إذا يحتاج بحث أو كتابة مباشرة… ⏳")
    try:
        run = await run_pipeline(fmt, system, topic, selected_angle,
                                 clarification_allowed=not resuming, brief=brief, research=True)
    except Exception:
        log.error("pipeline failed (%s)", type(sys.exc_info()[1]).__name__)
        await status.edit_text("صار خطأ بالاتصال بالموديل. جرب مرة ثانية بعد شوية.")
        return

    checked = run.checked
    # Enforce structure at the final delivery boundary, independently of pipeline status.
    # This guards against a future regression returning a wrongly accepted legacy layout.
    manual_draft = checked.manual_review_ready and manual_review_eligible(checked)
    if checked.status == "accepted" or manual_draft:
        delivery_failures = check(fmt, checked.text, story_mode=brief.story_mode, story_intent=brief.story_intent)
        if checked.story_mode != brief.story_mode or checked.story_intent != brief.story_intent:
            delivery_failures.append("Story mode mismatch")
        if brief.production:
            try:
                validate_plan(checked.production_plan, checked.text, brief.duration_seconds)
            except (ValueError, TypeError):
                delivery_failures.append("invalid production plan")
        if delivery_failures or checked.refused:
            checked.failures = delivery_failures or ["writer refused"]
            checked.status = "blocked"
            checked.manual_review_ready = manual_draft = False
            checked.failure_stage, checked.failure_code = "delivery", "invalid_structure"
    runtime = build_info(system)
    log.info("generation build=%s source=%s prompt=%s quality=%s",
             runtime["commit"], runtime["source"], runtime["prompt"], checked.status)
    log.info("fmt=%s angle=%s provider=%s attempts=%s calls=%d cost=$%.5f",
             fmt, angle, checked.provider, checked.attempts, len(run.calls), run.cost_usd)

    usage_known = (all(c.usage_known for c in run.calls)
                   and all(t["status"] == "ok" for t in run.timings))
    record = {
        "chat_id": cid, "format": fmt, "angle": angle, "topic": topic, "provider": checked.provider,
        "attempts": checked.attempts, "failures": checked.failures,
        "quality_status": checked.status, "review_history": checked.review_history,
        "transport_normalized": checked.transport_normalized,
        "structure_details": checked.structure_details,
        "failure_stage": checked.failure_stage, "failure_code": checked.failure_code,
        "manual_review_ready": manual_draft,
        "delivery_status": ("approved" if checked.status == "accepted" else
                            "manual_review" if manual_draft else "withheld"),
        "build": runtime, "planning": checked.planning, "research": checked.research,
        "routing": checked.routing,
        "objective": brief.purpose, "story_mode": brief.story_mode, "story_intent": brief.story_intent,
        "structure_id": brief.structure_id,
        "journey_stage": brief.journey_stage, "distribution": brief.distribution,
        "production_mode": brief.production,
        "elapsed_ms": run.elapsed_ms, "stage_timings": run.timings,
        "usage_known": usage_known,
        "quota_cost_usd": round(run.cost_usd if usage_known else max(run.cost_usd, 0.25), 6),
        "calls": len(run.calls), "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens, "cost_usd": round(run.cost_usd, 6),
    }
    try:
        pid = log_post(record, event="clarification" if checked.clarification else "generated")
    except OSError:
        log.error("generation_withheld: persistent record could not be saved")
        await status.edit_text("تعذّر حفظ سجل المحاولة، لذلك ما عرضنا المحتوى. كلم صاحب البوت حتى يراجع التخزين.")
        return

    if any(timing.get('fallback_reason') == 'provider_credit_exhausted' for timing in run.timings):
        await update.message.reply_text(
            '⚠️ رصيد Anthropic غير كافي أو حد الصرف مستنفد. انتقلت المحاولة إلى Nous البديل؛ '
            'بعدها نطبق نفس فحوصات الجودة قبل عرض المحتوى.')

    if checked.clarification:
        context.chat_data["pending_clarification"] = {
            "topic": topic, "format": fmt, "angle": angle, "question": checked.clarification}
        await status.edit_text(checked.clarification)
        return

    if checked.status != "accepted" and not manual_draft:
        log.warning("generation_not_delivered review=%s stage=%s code=%s", pid,
                    checked.failure_stage or 'unknown', checked.failure_code or 'unknown')
        await status.edit_text(failure_message({
            'failure_code': checked.failure_code, 'failures': checked.failures,
            'structure_details': checked.structure_details,
            'review_history': checked.review_history, 'stage_timings': run.timings}, pid))
        return

    await status.delete()
    delivered = render_story_copy(checked.text) if is_story(fmt) and brief.story_mode == "moment" else checked.text
    warning = manual_review_warning(checked) + "\n\n" if manual_draft else ""
    chunk_size = TELEGRAM_LIMIT - len(warning.encode('utf-16-le')) // 2
    for part in _chunks(delivered, size=chunk_size):
        await update.message.reply_text(warning + part)
    if checked.failures and not manual_draft:
        await update.message.reply_text("⚠️ تحقق يدوي قبل النشر:\n- " + "\n- ".join(checked.failures))
    if checked.production_plan:
        for part in _chunks(render_plan(checked.production_plan), size=chunk_size):
            await update.message.reply_text(warning + part)
    if checked.owner_note:
        await update.message.reply_text("📝 ملاحظة لك (لا تنشرها):\n" + checked.owner_note)
    if checked.research.get('sources'):
        sources = '📚 مصادر البحث (راجع تاريخ القرار ونطاق تطبيقه):\n' + '\n'.join(
            source['url'] for source in checked.research['sources'])
        for part in _chunks(sources):
            await update.message.reply_text(part, disable_web_page_preview=True)
    if manual_draft:
        await update.message.reply_text(
            f"رقم المسودة: {pid}\nهاي مسودة غير معتمدة وتحتاج مراجعتك وتعديلك. "
            "لنسخة جديدة دز الموضوع ويا ملاحظاتك، أو /format حتى تغيّر الاختيارات.")
        return
    await update.message.reply_text(
        f"رقم المنشور: {pid}\nبعد ما تنشره اكتب: /published {pid}\n"
        "تريد نعيده بشكل ثاني؟ دزلي ملاحظتك، أو /format حتى تغير النوع."
    )


async def log_runtime_identity(application):
    runtime = build_info()
    log.info("bot started workflow=%s format_contract=%s commit=%s branch=%s source=%s bot=@%s",
             runtime['workflow'], runtime['format_contract'], runtime['commit'], runtime['branch'],
             runtime['source'], application.bot.username)


async def on_handler_error(update, context):
    """Give storage failures an operational message without logging private payloads."""
    log.error('bot_handler_failed type=%s', type(context.error).__name__)
    if isinstance(context.error, OSError):
        message = getattr(update, 'effective_message', None) or getattr(update, 'message', None)
        if message is not None:
            await message.reply_text('تعذّر قراءة أو حفظ البيانات. كلم صاحب البوت حتى يراجع التخزين.')


def create_application(token: str, *, request=None):
    """Construct production handlers without starting a polling consumer."""
    builder = Application.builder().token(token).post_init(log_runtime_identity)
    if request is not None:
        builder = builder.request(request).get_updates_request(request)
    app = builder.build()
    app.add_error_handler(on_handler_error)
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
    app.add_handler(CommandHandler("diagnose", cmd_diagnose))
    app.add_handler(CommandHandler("experiment", cmd_experiment))
    app.add_handler(CommandHandler("example", cmd_example))
    app.add_handler(CommandHandler("pilot", cmd_pilot))
    app.add_handler(CallbackQueryHandler(on_back, pattern=r"^back:"))
    app.add_handler(CallbackQueryHandler(on_family_chosen, pattern=r"^fam:"))
    app.add_handler(CallbackQueryHandler(on_structure_chosen, pattern=r"^str:"))
    app.add_handler(CallbackQueryHandler(on_angle_chosen, pattern=r"^pick:"))
    app.add_handler(CallbackQueryHandler(on_format_chosen, pattern=r"^fmt:"))
    app.add_handler(CallbackQueryHandler(on_angle_chosen, pattern=r"^ang:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app


def main():
    app = create_application(os.environ["TELEGRAM_BOT_TOKEN"])
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
