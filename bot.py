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

