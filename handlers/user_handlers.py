from telegram import Update, InputFile, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_ID
import db
import os
from utils.utils import is_admin, IMAGES_DIR, logger

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    registered = db.register_user(user.id, user.username, user.full_name)
    if is_admin(user.id):
        keyboard = [["/tour", "/hc"], ["/send_tour_image", "/addhc", "/send_results"]]
        msg = (
            f'Привет, {user.full_name}! Ты зарегистрирован как администратор Fantasy KHL.\n\n'
            'Доступные команды:\n/tour — показать состав на тур\n/hc — баланс HC\n/send_tour_image — загрузить и разослать изображение тура\n/addhc — начислить HC пользователю\n/send_results — разослать результаты тура'
        )
    else:
        keyboard = [["/tour", "/hc"]]
        msg = (
            f'Привет, {user.full_name}! Ты зарегистрирован в Fantasy KHL.\n\n'
            'Доступные команды:\n/tour — показать состав на тур\n/hc — баланс HC'
        )
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    if registered:
        await update.message.reply_text(msg, reply_markup=markup)
    else:
        await update.message.reply_text('Ты уже зарегистрирован!', reply_markup=markup)

async def tour(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        files = os.listdir(IMAGES_DIR)
        if not files:
            await update.message.reply_text('Изображение тура пока не загружено.')
            return
        latest = sorted(files)[-1]
        with open(os.path.join(IMAGES_DIR, latest), 'rb') as img:
            await update.message.reply_photo(photo=InputFile(img), caption='Состав игроков на тур:')
    except Exception as e:
        logger.error(f'Ошибка при отправке изображения тура: {e}')
        await update.message.reply_text('Ошибка при отправке изображения.')

async def hc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    data = db.get_user_by_id(user.id)
    if data:
        await update.message.reply_text(f'💰 Твой баланс: {data[3]} HC')
    else:
        await update.message.reply_text('Ты не зарегистрирован!')
