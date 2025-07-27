from telegram import Update, InputFile
from telegram.ext import ContextTypes
from config import ADMIN_ID
import db
import os

IMAGES_DIR = 'images'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    registered = db.register_user(user.id, user.username, user.full_name)
    if registered:
        await update.message.reply_text(f'Привет, {user.full_name}! Ты зарегистрирован в Fantasy KHL.')
    else:
        await update.message.reply_text('Ты уже зарегистрирован!')

async def tour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        files = os.listdir(IMAGES_DIR)
        if not files:
            await update.message.reply_text('Изображение тура пока не загружено.')
            return
        latest = sorted(files)[-1]
        with open(os.path.join(IMAGES_DIR, latest), 'rb') as img:
            await update.message.reply_photo(photo=InputFile(img), caption='Состав игроков на тур:')
    except Exception as e:
        await update.message.reply_text('Ошибка при отправке изображения.')

async def hc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = db.get_user_by_id(user.id)
    if data:
        await update.message.reply_text(f'💰 Твой баланс: {data[3]} HC')
    else:
        await update.message.reply_text('Ты не зарегистрирован!')

# Админские команды будут реализованы в bot.py для проверки прав 