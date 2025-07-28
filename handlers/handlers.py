

from telegram import Update, InputFile
from telegram.ext import ContextTypes
import os
import db
from config import ADMIN_ID
from utils.utils import IMAGES_DIR
from .user_handlers import start, tour, hc
from .admin_handlers import send_tour_image, addhc, send_results, admin_only

async def admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    if user_id != ADMIN_ID:
        await update.message.reply_text('Нет доступа')
        return False
    return True

async def send_tour_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return
    if not update.message.photo:
        await update.message.reply_text('Пожалуйста, прикрепите фото вместе с командой.')
        return
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        filename = f"tour_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        await file.download_to_drive(path)
        with open('latest_tour.txt', 'w') as f:
            f.write(filename)
        users = db.get_all_users()
        success = 0
        failed = 0
        for user in users:
            try:
                await context.bot.send_photo(chat_id=user[0], photo=InputFile(path), caption='🏒 Новый тур! Состав игроков на сегодня:')
                success += 1
            except Exception:
                failed += 1
        msg = f'✅ Изображение сохранено как `{filename}`.\n📤 Успешно отправлено {success} пользователям.'
        if failed:
            msg += f'\n⚠️ Ошибки у {failed} пользователей.'
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f'Ошибка: {e}')

async def addhc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return
    if len(context.args) != 2 or not context.args[1].isdigit():
        await update.message.reply_text('Использование: /addhc @username 100')
        return
    username = context.args[0].lstrip('@')
    amount = int(context.args[1])
    user = db.get_user_by_username(username)
    if not user:
        await update.message.reply_text('Пользователь не найден.')
        return
    db.update_hc_balance(user[0], amount)
    new_balance = db.get_user_by_id(user[0])[3]
    await context.bot.send_message(chat_id=user[0], text=f'🎉 Тебе начислено {amount} HC!\n💰 Новый баланс: {new_balance} HC')
    await update.message.reply_text(f'Пользователю @{username} начислено {amount} HC.')

async def send_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return
    users = db.get_all_users()
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        filename = f"results_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        await file.download_to_drive(path)
        for user in users:
            try:
                await context.bot.send_photo(chat_id=user[0], photo=InputFile(path), caption='📊 Результаты тура:')
            except Exception:
                pass
        await update.message.reply_text('Результаты (фото) разосланы.')
    elif context.args:
        text = ' '.join(context.args)
        for user in users:
            try:
                await context.bot.send_message(chat_id=user[0], text=f'📊 Результаты тура:\n{text}')
            except Exception:
                pass
        await update.message.reply_text('Результаты (текст) разосланы.')
    else:
        await update.message.reply_text('Пришлите изображение или текст после команды.')