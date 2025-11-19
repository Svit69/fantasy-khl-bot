import os
import datetime
from typing import Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import ContextTypes, ConversationHandler

import db
from utils import IMAGES_DIR, CHALLENGE_IMAGE_PATH_FILE
from utils.challenge_modes import (
    find_mode_by_text,
    get_challenge_mode,
    iter_challenge_modes,
)
from handlers.admin_handlers import (
    CHALLENGE_MODE,
    CHALLENGE_START,
    CHALLENGE_DEADLINE,
    CHALLENGE_END,
    CHALLENGE_WAIT_IMAGE,
)

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


_MSK_FALLBACK = datetime.timezone(datetime.timedelta(hours=3))


def _get_msk_timezone():
    if ZoneInfo is not None:
        try:
            return ZoneInfo("Europe/Moscow")
        except Exception:
            pass
    return _MSK_FALLBACK


_MSK_TZ = _get_msk_timezone()
_INPUT_EXAMPLE = "10.09.2025 12:00"
_CANCEL_KEYBOARD = ReplyKeyboardMarkup([["/cancel"]], resize_keyboard=True)
_CANCEL_REMOVE = ReplyKeyboardRemove()
_AVAILABLE_MODES = list(iter_challenge_modes())
_MODE_BUTTONS = [
    InlineKeyboardButton(
        f"{idx}) {mode.button_title}",
        callback_data=f"challenge_mode_{mode.code}",
    )
    for idx, mode in enumerate(_AVAILABLE_MODES, start=1)
]
_MODE_KEYBOARD_ROWS = [
    _MODE_BUTTONS[i : i + 2] for i in range(0, len(_MODE_BUTTONS), 2)
]
_MODE_KEYBOARD = InlineKeyboardMarkup(_MODE_KEYBOARD_ROWS)
_MODE_PROMPT = "Выберите режим челленджа:\n" + "\n".join(
    f"{idx} — {mode.prompt_line}"
    for idx, mode in enumerate(_AVAILABLE_MODES, start=1)
)


def _ensure_msk(dt: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_MSK_TZ)
    try:
        return dt.astimezone(_MSK_TZ)
    except Exception:
        return dt


def _parse_admin_datetime(value: str) -> Optional[datetime.datetime]:
    text = (value or "").strip()
    if not text:
        return None
    formats = (
        "%d.%m.%Y %H:%M",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
    )
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(text, fmt)
            return _ensure_msk(dt)
        except Exception:
            continue
    try:
        dt = datetime.datetime.fromisoformat(text)
    except Exception:
        return None
    return _ensure_msk(dt)


def _reset_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in ("challenge_mode", "challenge_start", "challenge_deadline", "challenge_end"):
        context.user_data.pop(key, None)


async def send_challenge_image_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.admin_handlers import admin_only

    if not await admin_only(update, context):
        return ConversationHandler.END
    _reset_state(context)
    if update.message:
        await update.message.reply_text(_MODE_PROMPT, reply_markup=_MODE_KEYBOARD)
    return CHALLENGE_MODE


async def challenge_mode_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = getattr(update, "callback_query", None)
    mode_obj = None
    if query is not None:
        data = (query.data or "").strip()
        if data == "challenge_mode_default":
            mode_obj = get_challenge_mode("default")
        elif data == "challenge_mode_under23":
            mode_obj = get_challenge_mode("under23")
        elif data.startswith("challenge_mode_"):
            code = data.replace("challenge_mode_", "", 1)
            mode_obj = get_challenge_mode(code)
        await query.answer()
    else:
        text_value = (update.message.text or "").strip()
        if text_value.isdigit():
            idx = int(text_value) - 1
            if 0 <= idx < len(_AVAILABLE_MODES):
                mode_obj = _AVAILABLE_MODES[idx]
        if mode_obj is None:
            mode_obj = find_mode_by_text(text_value)
    if mode_obj is None:
        prompt = "Пожалуйста, выберите режим с помощью кнопок или отправьте номер варианта."
        if query is not None:
            await query.answer(prompt, show_alert=True)
        elif update.message:
            await update.message.reply_text(prompt, reply_markup=_MODE_KEYBOARD)
        return CHALLENGE_MODE

    context.user_data["challenge_mode"] = mode_obj.code
    summary = mode_obj.summary_label
    next_prompt = f"Укажите дату и время старта в формате {_INPUT_EXAMPLE} (МСК)."

    if query is not None:
        try:
            await query.edit_message_text(summary)
        except Exception:
            await query.message.reply_text(summary)
        await query.message.reply_text(next_prompt, reply_markup=_CANCEL_KEYBOARD)
    else:
        await update.message.reply_text(f"{summary}\n{next_prompt}", reply_markup=_CANCEL_KEYBOARD)
    return CHALLENGE_START


async def challenge_input_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dt = _parse_admin_datetime(update.message.text)
    if not dt:
        await update.message.reply_text(
            f"Не удалось распознать дату. Введите значение в формате {_INPUT_EXAMPLE} (МСК).",
            reply_markup=_CANCEL_KEYBOARD,
        )
        return CHALLENGE_START

    context.user_data["challenge_start"] = dt.isoformat()
    await update.message.reply_text(
        f"Старт сохранён. Теперь отправьте дедлайн в формате {_INPUT_EXAMPLE} (МСК).",
        reply_markup=_CANCEL_KEYBOARD,
    )
    return CHALLENGE_DEADLINE


async def challenge_input_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dl = _parse_admin_datetime(update.message.text)
    if not dl:
        await update.message.reply_text(
            f"Не удалось распознать дедлайн. Введите значение в формате {_INPUT_EXAMPLE} (МСК).",
            reply_markup=_CANCEL_KEYBOARD,
        )
        return CHALLENGE_DEADLINE

    sd = _parse_admin_datetime(context.user_data.get("challenge_start", ""))
    if not sd or not (sd < dl):
        await update.message.reply_text(
            "Дедлайн должен быть позже старта. Повторите ввод.",
            reply_markup=_CANCEL_KEYBOARD,
        )
        return CHALLENGE_DEADLINE

    context.user_data["challenge_deadline"] = dl.isoformat()
    await update.message.reply_text(
        f"Дедлайн сохранён. Теперь укажите дату завершения в формате {_INPUT_EXAMPLE} (МСК).",
        reply_markup=_CANCEL_KEYBOARD,
    )
    return CHALLENGE_END


async def challenge_input_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ed = _parse_admin_datetime(update.message.text)
    if not ed:
        await update.message.reply_text(
            f"Не удалось распознать дату завершения. Введите значение в формате {_INPUT_EXAMPLE} (МСК).",
            reply_markup=_CANCEL_KEYBOARD,
        )
        return CHALLENGE_END

    sd = _parse_admin_datetime(context.user_data.get("challenge_start", ""))
    dl = _parse_admin_datetime(context.user_data.get("challenge_deadline", ""))
    if not sd or not dl or not (dl < ed):
        await update.message.reply_text(
            "Завершение должно быть позже дедлайна. Повторите ввод.",
            reply_markup=_CANCEL_KEYBOARD,
        )
        return CHALLENGE_END

    context.user_data["challenge_end"] = ed.isoformat()
    await update.message.reply_text(
        "Отлично! Теперь отправьте изображение челленджа (как фото).",
        reply_markup=_CANCEL_KEYBOARD,
    )
    return CHALLENGE_WAIT_IMAGE


async def send_challenge_image_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.photo:
        if message:
            await message.reply_text("Пожалуйста, отправьте изображение челленджа.", reply_markup=_CANCEL_KEYBOARD)
        return CHALLENGE_WAIT_IMAGE

    try:
        photo = message.photo[-1]
        tg_file = await photo.get_file()
        os.makedirs(IMAGES_DIR, exist_ok=True)
        filename = f"challenge_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        try:
            await tg_file.download_to_drive(path)
        except Exception:
            await tg_file.download(custom_path=path)
        try:
            with open(CHALLENGE_IMAGE_PATH_FILE, "w", encoding="utf-8") as handle:
                handle.write(filename)
        except Exception:
            pass

        start_date = context.user_data.get("challenge_start")
        deadline = context.user_data.get("challenge_deadline")
        end_date = context.user_data.get("challenge_end")
        age_mode = context.user_data.get("challenge_mode", "default")
        ch_id = db.create_challenge(
            start_date,
            deadline,
            end_date,
            filename,
            getattr(photo, "file_id", "") or "",
            age_mode,
        )

        await message.reply_text(
            f"Готово: челлендж зарегистрирован (id={ch_id}). Файл изображения: `{filename}`.",
            parse_mode="Markdown",
            reply_markup=_CANCEL_REMOVE,
        )
    except Exception as exc:
        await message.reply_text(
            f"Не удалось сохранить челлендж: {exc}",
            reply_markup=_CANCEL_KEYBOARD,
        )
    finally:
        _reset_state(context)
    return ConversationHandler.END


async def send_challenge_image_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if message:
        await message.reply_text("Создание челленджа отменено.", reply_markup=_CANCEL_REMOVE)
    _reset_state(context)
    return ConversationHandler.END
