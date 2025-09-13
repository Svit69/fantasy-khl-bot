import os
import datetime
from telegram import Update, InputFile
from telegram.ext import ContextTypes, ConversationHandler

import db
from utils import IMAGES_DIR, CHALLENGE_IMAGE_PATH_FILE
from handlers.admin_handlers import (
    CHALLENGE_START, CHALLENGE_DEADLINE, CHALLENGE_END, CHALLENGE_WAIT_IMAGE,
)


def _parse_iso(dt_str: str):
    try:
        return datetime.datetime.fromisoformat(str(dt_str))
    except Exception:
        return None


async def send_challenge_image_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # admin check from existing helper
    from handlers.admin_handlers import admin_only
    if not await admin_only(update, context):
        return ConversationHandler.END
    # reset temp
    for k in ('challenge_start', 'challenge_deadline', 'challenge_end'):
        context.user_data.pop(k, None)
    await update.message.reply_text(
        'Создание челленджа. Введите дату СТАРТА в формате ISO, например: 2025-08-08T12:00:00'
    )
    return CHALLENGE_START


async def challenge_input_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    if not _parse_iso(text):
        await update.message.reply_text('Неверная дата. Введите в формате ISO: 2025-08-08T12:00:00')
        return CHALLENGE_START
    context.user_data['challenge_start'] = text
    await update.message.reply_text('Введите дату ДЕДЛАЙНА (не раньше старта) в формате ISO: 2025-08-09T18:00:00')
    return CHALLENGE_DEADLINE


async def challenge_input_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    dl = _parse_iso(text)
    if not dl:
        await update.message.reply_text('Неверная дата. Введите дедлайн в формате ISO.')
        return CHALLENGE_DEADLINE
    sd = _parse_iso(context.user_data.get('challenge_start', ''))
    if not sd or not (sd < dl):
        await update.message.reply_text('Дедлайн должен быть позже старта. Введите корректную дату дедлайна.')
        return CHALLENGE_DEADLINE
    context.user_data['challenge_deadline'] = text
    await update.message.reply_text('Введите дату ОКОНЧАНИЯ (после дедлайна) в формате ISO: 2025-08-12T23:59:59')
    return CHALLENGE_END


async def challenge_input_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    ed = _parse_iso(text)
    if not ed:
        await update.message.reply_text('Неверная дата. Введите окончание в формате ISO.')
        return CHALLENGE_END
    sd = _parse_iso(context.user_data.get('challenge_start', ''))
    dl = _parse_iso(context.user_data.get('challenge_deadline', ''))
    if not sd or not dl or not (dl < ed):
        await update.message.reply_text('Окончание должно быть позже дедлайна. Введите корректную дату окончания.')
        return CHALLENGE_END
    context.user_data['challenge_end'] = text
    await update.message.reply_text('Отлично! Теперь отправьте изображение (постер) челленджа одним фото в ответ на это сообщение.')
    return CHALLENGE_WAIT_IMAGE


async def send_challenge_image_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Expect a photo; save it and create challenge
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
        # remember path for other features
        try:
            with open(CHALLENGE_IMAGE_PATH_FILE, 'w', encoding='utf-8') as f:
                f.write(filename)
        except Exception:
            pass

        start_date = context.user_data.get('challenge_start')
        deadline = context.user_data.get('challenge_deadline')
        end_date = context.user_data.get('challenge_end')
        ch_id = db.create_challenge(start_date, deadline, end_date, filename, getattr(photo, 'file_id', '') or '')

        await update.message.reply_text(
            f'Готово: челлендж создан (id={ch_id}). Изображение сохранено как `{filename}`.'
        )
    except Exception as e:
        await update.message.reply_text(f'Не удалось обработать изображение: {e}')
    finally:
        for k in ('challenge_start', 'challenge_deadline', 'challenge_end'):
            context.user_data.pop(k, None)
    return ConversationHandler.END


async def send_challenge_image_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Создание челленджа отменено.')
    for k in ('challenge_start', 'challenge_deadline', 'challenge_end'):
        context.user_data.pop(k, None)
    return ConversationHandler.END

