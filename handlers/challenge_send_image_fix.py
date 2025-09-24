import os
import datetime
from typing import Optional
from telegram import Update, InputFile
from telegram.ext import ContextTypes, ConversationHandler

import db
from utils import IMAGES_DIR, CHALLENGE_IMAGE_PATH_FILE
from handlers.admin_handlers import (
    CHALLENGE_START, CHALLENGE_DEADLINE, CHALLENGE_END, CHALLENGE_WAIT_IMAGE,
)

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

_MSK_FALLBACK = datetime.timezone(datetime.timedelta(hours=3))

def _get_msk_timezone():
    if ZoneInfo is not None:
        try:
            return ZoneInfo('Europe/Moscow')
        except Exception:
            pass
    return _MSK_FALLBACK

_MSK_TZ = _get_msk_timezone()
_INPUT_EXAMPLE = '10.09.2025 12:00'


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
    text = (value or '').strip()
    if not text:
        return None
    formats = (
        '%d.%m.%Y %H:%M',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M',
        '%Y-%m-%dT%H:%M:%S',
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


async def send_challenge_image_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.admin_handlers import admin_only
    if not await admin_only(update, context):
        return ConversationHandler.END
    for key in ('challenge_start', 'challenge_deadline', 'challenge_end'):
        context.user_data.pop(key, None)
    await update.message.reply_text(
        f'Создание челленджа. Введите дату СТАРТА в формате {_INPUT_EXAMPLE} (МСК)'
    )
    return CHALLENGE_START


async def challenge_input_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dt = _parse_admin_datetime(update.message.text)
    if not dt:
        await update.message.reply_text(f'Неверная дата. Введите старт в формате {_INPUT_EXAMPLE} (МСК).')
        return CHALLENGE_START
    context.user_data['challenge_start'] = dt.isoformat()
    await update.message.reply_text(
        f'Введите дату ДЕДЛАЙНА (позже старта) в формате {_INPUT_EXAMPLE} (МСК).'
    )
    return CHALLENGE_DEADLINE


async def challenge_input_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dl = _parse_admin_datetime(update.message.text)
    if not dl:
        await update.message.reply_text(f'Неверная дата. Введите дедлайн в формате {_INPUT_EXAMPLE} (МСК).')
        return CHALLENGE_DEADLINE
    sd = _parse_admin_datetime(context.user_data.get('challenge_start', ''))
    if not sd or not (sd < dl):
        await update.message.reply_text('Дедлайн должен быть позже старта. Введите корректную дату.')
        return CHALLENGE_DEADLINE
    context.user_data['challenge_deadline'] = dl.isoformat()
    await update.message.reply_text(
        f'Введите дату ОКОНЧАНИЯ (после дедлайна) в формате {_INPUT_EXAMPLE} (МСК).'
    )
    return CHALLENGE_END


async def challenge_input_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ed = _parse_admin_datetime(update.message.text)
    if not ed:
        await update.message.reply_text(f'Неверная дата. Введите окончание в формате {_INPUT_EXAMPLE} (МСК).')
        return CHALLENGE_END
    sd = _parse_admin_datetime(context.user_data.get('challenge_start', ''))
    dl = _parse_admin_datetime(context.user_data.get('challenge_deadline', ''))
    if not sd or not dl or not (dl < ed):
        await update.message.reply_text('Окончание должно быть позже дедлайна. Введите корректную дату.')
        return CHALLENGE_END
    context.user_data['challenge_end'] = ed.isoformat()
    await update.message.reply_text('Отлично! Теперь отправьте изображение (постер) челленджа одним фото в ответ на это сообщение.')
    return CHALLENGE_WAIT_IMAGE


async def send_challenge_image_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        await update.message.reply_text('Пожалуйста, отправьте фото.')
        return CHALLENGE_WAIT_IMAGE
    try:
        photo = update.message.photo[-1]
        tg_file = await photo.get_file()
        os.makedirs(IMAGES_DIR, exist_ok=True)
        filename = f"challenge_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        try:
            await tg_file.download_to_drive(path)
        except Exception:
            await tg_file.download(custom_path=path)
        try:
            with open(CHALLENGE_IMAGE_PATH_FILE, 'w', encoding='utf-8') as handle:
                handle.write(filename)
        except Exception:
            pass

        start_date = context.user_data.get('challenge_start')
        deadline = context.user_data.get('challenge_deadline')
        end_date = context.user_data.get('challenge_end')
        ch_id = db.create_challenge(start_date, deadline, end_date, filename, getattr(photo, 'file_id', '') or '')

        await update.message.reply_text(
            f'Готово: челлендж создан (id={ch_id}). Изображение сохранено как `{filename}`.'
        )
    except Exception as exc:
        await update.message.reply_text(f'Не удалось обработать изображение: {exc}')
    finally:
        for key in ('challenge_start', 'challenge_deadline', 'challenge_end'):
            context.user_data.pop(key, None)
    return ConversationHandler.END


async def send_challenge_image_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Создание челленджа отменено.')
    for key in ('challenge_start', 'challenge_deadline', 'challenge_end'):
        context.user_data.pop(key, None)
    return ConversationHandler.END
