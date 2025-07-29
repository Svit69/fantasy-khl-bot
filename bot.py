import os
import logging
import asyncio

from telegram import Update, InputFile, BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
import httpx

from config import TELEGRAM_TOKEN, ADMIN_ID

import db
from handlers.handlers import start, tour, hc, addhc, send_results, IMAGES_DIR


# Настройка логирования: в файл и в консоль
import sys
os.makedirs('logs', exist_ok=True)
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler('logs/bot.log', encoding='utf-8')
file_handler.setFormatter(log_formatter)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.handlers = []  # Сбросить обработчики, если уже были
logger.addHandler(file_handler)
logger.addHandler(console_handler)


async def main():
    db.init_db()
    os.makedirs(IMAGES_DIR, exist_ok=True)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('tour', tour))
    app.add_handler(CommandHandler('hc', hc))

    # --- ConversationHandler для send_tour_image ---
    from telegram.ext import ConversationHandler, MessageHandler, filters
    WAIT_IMAGE = 1


    async def send_tour_image_start(update, context):
        logger.info(f"[send_tour_image_start] user_id={update.effective_user.id if update.effective_user else None}")
        try:
            await update.message.reply_text('Пожалуйста, прикрепите картинку следующим сообщением.')
        except Exception as e:
            logger.error(f"Ошибка при отправке приглашения на фото: {e}")
            await update.message.reply_text(f"Ошибка: {e}")
        return WAIT_IMAGE

    async def send_tour_image_photo(update, context):
        logger.info(f"[send_tour_image_photo] user_id={update.effective_user.id if update.effective_user else None}, has_photo={bool(update.message.photo)}")
        try:
            from handlers.admin_handlers import send_tour_image
            await send_tour_image(update, context)
            logger.info("[send_tour_image_photo] Фото успешно обработано и разослано.")
        except Exception as e:
            logger.error(f"Ошибка при обработке фото: {e}")
            await update.message.reply_text(f"Ошибка при обработке фото: {e}")
        return ConversationHandler.END

    async def send_tour_image_cancel(update, context):
        logger.info(f"[send_tour_image_cancel] user_id={update.effective_user.id if update.effective_user else None}")
        try:
            await update.message.reply_text('Отменено.')
        except Exception as e:
            logger.error(f"Ошибка при отмене: {e}")
            await update.message.reply_text(f"Ошибка: {e}")
        return ConversationHandler.END

    send_tour_image_conv = ConversationHandler(
        entry_points=[CommandHandler('send_tour_image', send_tour_image_start)],
        states={
            WAIT_IMAGE: [MessageHandler(filters.PHOTO, send_tour_image_photo)]
        },
        fallbacks=[CommandHandler('cancel', send_tour_image_cancel)],
        allow_reentry=True
    )
    app.add_handler(send_tour_image_conv)
    app.add_handler(CommandHandler('addhc', addhc))
    app.add_handler(CommandHandler('send_results', send_results))

    # Установка команд для пользователей и админа
    from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
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
    await app.run_polling()

if __name__ == '__main__':
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

