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
import db.db as db
from handlers.handlers import start, tour, hc, send_tour_image, addhc, send_results, IMAGES_DIR

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def main():
    db.init_db()
    os.makedirs(IMAGES_DIR, exist_ok=True)

    app = Application.builder().token(TELEGRAM_TOKEN).build()


    from handlers.handlers import start, tour, hc, send_tour_image, addhc, send_results
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('tour', tour))
    app.add_handler(CommandHandler('hc', hc))
    app.add_handler(CommandHandler('send_tour_image', send_tour_image))
    app.add_handler(CommandHandler('addhc', addhc))
    app.add_handler(CommandHandler('send_results', send_results))

    # Обработчик для фото-сообщений от админа (для сценария send_tour_image)
    from telegram.ext import MessageHandler, filters
    async def admin_photo_handler(update, context):
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id if update.effective_user else None
        debug_info = f"[DEBUG] chat_id: {chat_id}, user_id: {user_id}, chat_data: {context.chat_data}, user_data: {context.user_data}"
        await update.message.reply_text(debug_info)
        # Всегда проверяем флаг ожидания картинки
        if context.chat_data.get('awaiting_tour_image'):
            from handlers.admin_handlers import send_tour_image
            await send_tour_image(update, context)
            # Отклик уже отправляется внутри send_tour_image
            # Сброс флага происходит только после успешной обработки
        else:
            await update.message.reply_text('Сначала отправьте команду /send_tour_image, затем фото.')
    # Регистрируем обработчик фото для всех
    app.add_handler(MessageHandler(filters.PHOTO, admin_photo_handler))

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
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())

