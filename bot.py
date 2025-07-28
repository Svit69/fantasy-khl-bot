import os
import logging
import asyncio

from telegram import (
    Update, InputFile, BotCommand,
    BotCommandScopeDefault, BotCommandScopeChat
)
from telegram.ext import (
    Application, CommandHandler, ContextTypes
)
import httpx

from config import TELEGRAM_TOKEN, ADMIN_ID
import db
from handlers import start, tour, hc  # если есть

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

IMAGES_DIR = 'images'
TOUR_IMAGE_PATH_FILE = 'latest_tour.txt'

async def admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    logger.info(f'Проверка прав пользователя {user_id}')
    if user_id != ADMIN_ID:
        await update.message.reply_text('Нет доступа')
        return False
    return True

async def tour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(TOUR_IMAGE_PATH_FILE):
        await update.message.reply_text("Изображение тура пока не загружено.")
        return

    with open(TOUR_IMAGE_PATH_FILE, 'r') as f:
        filename = f.read().strip()

    path = os.path.join(IMAGES_DIR, filename)

    if not os.path.exists(path):
        await update.message.reply_text("Изображение тура пока не загружено.")
        return

    await update.message.reply_photo(photo=InputFile(path), caption='🏒 Состав игроков на сегодня:')

async def send_tour_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info('Вызов команды /send_tour_image')

    if not await admin_only(update, context):
        return

    if not update.message.photo:
        await update.message.reply_text('Пожалуйста, прикрепите фото вместе с командой.')
        logger.info('Фото не прикреплено к сообщению')
        return

    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        filename = f"tour_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        await file.download_to_drive(path)
        logger.info(f"Фото тура сохранено: {path}")

        with open(TOUR_IMAGE_PATH_FILE, 'w') as f:
            f.write(filename)

        users = db.get_all_users()
        success = 0
        failed = 0

        for user in users:
            try:
                await context.bot.send_photo(
                    chat_id=user[0],
                    photo=InputFile(path),
                    caption='🏒 Новый тур! Состав игроков на сегодня:'
                )
                success += 1
            except Exception as e:
                logger.warning(f"Ошибка при отправке фото пользователю {user[0]}: {e}")
                failed += 1

        msg = (
            f'✅ Изображение успешно получено и сохранено как `{filename}`.\n'
            f'📤 Успешно отправлено {success} пользователям.'
        )
        if failed:
            msg += f'\n⚠️ Ошибки у {failed} пользователей.'
        await update.message.reply_text(msg)

    except Exception as e:
        logger.error(f'Ошибка в send_tour_image: {e}', exc_info=True)
        await update.message.reply_text(f'Произошла ошибка при обработке фото: {e}')

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

    await context.bot.send_message(
        chat_id=user[0],
        text=f'🎉 Тебе начислено {amount} HC!\n💰 Новый баланс: {new_balance} HC'
    )
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
            except Exception as e:
                logger.warning(f"Ошибка при отправке результата пользователю {user[0]}: {e}")

        await update.message.reply_text('Результаты (фото) разосланы.')

    elif context.args:
        text = ' '.join(context.args)

        for user in users:
            try:
                await context.bot.send_message(chat_id=user[0], text=f'📊 Результаты тура:\n{text}')
            except Exception as e:
                logger.warning(f"Ошибка при отправке текста результата {user[0]}: {e}")

        await update.message.reply_text('Результаты (текст) разосланы.')
    else:
        await update.message.reply_text('Пришлите изображение или текст после команды.')

async def set_commands(app: Application):
    user_commands = [
        BotCommand("start", "Регистрация и приветствие"),
        BotCommand("tour", "Показать состав игроков на тур"),
        BotCommand("hc", "Показать баланс HC"),
    ]
    await app.bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())

    admin_commands = user_commands + [
        BotCommand("send_tour_image", "Разослать изображение тура (админ)"),
        BotCommand("addhc", "Начислить HC пользователю (админ)"),
        BotCommand("send_results", "Разослать результаты тура (админ)"),
    ]
    await app.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_ID))

async def main():
    db.init_db()
    os.makedirs(IMAGES_DIR, exist_ok=True)

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('tour', tour))
    app.add_handler(CommandHandler('hc', hc))
    app.add_handler(CommandHandler('send_tour_image', send_tour_image))
    app.add_handler(CommandHandler('addhc', addhc))
    app.add_handler(CommandHandler('send_results', send_results))

    await set_commands(app)
    await app.run_polling()

if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())

