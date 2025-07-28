
from telegram import Update, InputFile, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_ID
import db
import os
from utils import is_admin, send_message_to_users, IMAGES_DIR, TOUR_IMAGE_PATH_FILE, logger

# --- Пользовательские обработчики ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Регистрация пользователя и приветствие."""
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
    """Показать последнее изображение тура."""
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
    """Показать баланс HC пользователя."""
    user = update.effective_user
    data = db.get_user_by_id(user.id)
    if data:
        await update.message.reply_text(f'💰 Твой баланс: {data[3]} HC')
    else:
        await update.message.reply_text('Ты не зарегистрирован!')

# --- Админские обработчики ---

async def admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверка прав администратора."""
    user_id = update.effective_user.id if update.effective_user else None
    if not is_admin(user_id):
        await update.message.reply_text('Нет доступа')
        return False
    return True

async def send_tour_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Загрузка и рассылка изображения тура всем пользователям."""
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
        with open(TOUR_IMAGE_PATH_FILE, 'w') as f:
            f.write(filename)
        users = db.get_all_users()
        success, failed = await send_message_to_users(context.bot, users, photo_path=path, caption='🏒 Новый тур! Состав игроков на сегодня:')
        msg = f'✅ Изображение сохранено как `{filename}`.\n📤 Успешно отправлено {success} пользователям.'
        if failed:
            msg += f'\n⚠️ Ошибки у {failed} пользователей.'
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f'Ошибка в send_tour_image: {e}')
        await update.message.reply_text(f'Ошибка: {e}')

async def addhc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начислить HC пользователю."""
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

async def send_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Разослать результаты тура всем пользователям (фото или текст)."""
    if not await admin_only(update, context):
        return
    users = db.get_all_users()
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        filename = f"results_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        await file.download_to_drive(path)
        success, failed = await send_message_to_users(context.bot, users, photo_path=path, caption='📊 Результаты тура:')
        await update.message.reply_text(f'Результаты (фото) разосланы. Успешно: {success}, ошибки: {failed}')
    elif context.args:
        text = ' '.join(context.args)
        success, failed = await send_message_to_users(context.bot, users, text=f'📊 Результаты тура:\n{text}')
        await update.message.reply_text(f'Результаты (текст) разосланы. Успешно: {success}, ошибки: {failed}')
    else:
        await update.message.reply_text('Пришлите изображение или текст после команды.')

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