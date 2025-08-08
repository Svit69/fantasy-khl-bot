from yookassa import Configuration
from utils import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY
Configuration.configure(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
print("[DEBUG] Ключи установлены через Configuration.configure:", Configuration.account_id, Configuration.secret_key)
import os
import logging
import asyncio

from telegram import Update, InputFile, BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from telegram.ext import PicklePersistence
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import httpx

from config import TELEGRAM_TOKEN, ADMIN_ID

import db
from handlers.user_handlers import start, hc, IMAGES_DIR, \
    tour_start, tour_forward_1, tour_forward_2, tour_forward_3, \
    tour_defender_1, tour_defender_2, tour_goalie, tour_captain, \
    tour_forward_callback, tour_defender_callback, tour_goalie_callback, \
    restart_tour_callback, tour_captain_callback, rules, referral, subscribe
from handlers.admin_handlers import addhc, send_results, show_users
from handlers.admin_handlers import (
    add_player_start, add_player_name, add_player_position, add_player_club,
    add_player_nation, add_player_age, add_player_price, add_player_cancel, list_players, find_player,
    remove_player, edit_player_start, edit_player_name, edit_player_position, edit_player_club,
    edit_player_nation, edit_player_age, edit_player_price, edit_player_cancel,
    set_tour_roster_start, set_tour_roster_process, get_tour_roster,
    set_budget_start, set_budget_process,
    create_tour_conv, list_tours, activate_tour
)

ADD_NAME, ADD_POSITION, ADD_CLUB, ADD_NATION, ADD_AGE, ADD_PRICE = range(6)
EDIT_NAME, EDIT_POSITION, EDIT_CLUB, EDIT_NATION, EDIT_AGE, EDIT_PRICE = range(6, 12)

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


# Инициализация базы данных и создание директорий
db.init_db()
os.makedirs(IMAGES_DIR, exist_ok=True)

# --- ConversationHandler для send_tour_image ---
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
        from handlers.admin_handlers import process_tour_image_photo, create_tour_conv, list_tours, activate_tour
        await process_tour_image_photo(update, context)
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

import utils

async def on_startup(app):
    from telegram import BotCommand, BotCommandScopeChat, BotCommandScopeAllPrivateChats
    from config import ADMIN_ID
    print("[DEBUG] on_startup called: setting bot commands")
    user_commands = [
        BotCommand("start", "Регистрация и приветствие"),
        BotCommand("tour", "Показать состав игроков на тур"),
        BotCommand("hc", "Показать баланс HC"),
        BotCommand("subscribe", "Оформить подписку"),
        BotCommand("rules", "Правила сборки составов"),
    ]
    admin_commands = user_commands + [
        BotCommand("show_users", "Список пользователей и подписок (админ)"),
        BotCommand("send_tour_image", "Разослать изображение тура (админ)"),
        BotCommand("addhc", "Начислить HC пользователю (админ)"),
        BotCommand("send_results", "Разослать результаты тура (админ)"),
    ]
    try:
        # Очистим команды на всякий случай (default и ru)
        await app.bot.delete_my_commands()
        await app.bot.delete_my_commands(language_code='ru')
        print("[DEBUG] Existing commands cleared (default + ru)")
    except Exception as e:
        print(f"[WARN] delete_my_commands failed: {e}")

    # Установим команды по умолчанию и для RU
    await app.bot.set_my_commands(user_commands)
    await app.bot.set_my_commands(user_commands, language_code='ru')
    print("[DEBUG] Default commands set (default + ru)")

    # Установим команды для всех приватных чатов (дублирование для надёжности)
    try:
        await app.bot.set_my_commands(user_commands, scope=BotCommandScopeAllPrivateChats())
        await app.bot.set_my_commands(user_commands, scope=BotCommandScopeAllPrivateChats(), language_code='ru')
        print("[DEBUG] Commands set for all private chats (default + ru)")
    except Exception as e:
        print(f"[WARN] Failed to set commands for AllPrivateChats: {e}")

    # Для админа в личке (его чат)
    await app.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
    try:
        await app.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_ID), language_code='ru')
        print("[DEBUG] Admin chat commands set (default + ru)")
    except Exception:
        # Не все клиенты поддерживают язык для chat scope — игнорируем
        print("[WARN] Admin chat commands ru-language not supported; skipped")
    print("[DEBUG] Bot commands set complete")
    
    # Принудительное обновление кеша команд в Telegram
    try:
        await app.bot.delete_my_commands()
        await app.bot.set_my_commands(user_commands)
        await app.bot.delete_my_commands(language_code='ru')
        await app.bot.set_my_commands(user_commands, language_code='ru')
        print("[DEBUG] Bot commands cache updated (default and ru)")
        print("[DEBUG] Команды успешно обновлены через Bot API")
    except Exception as e:
        print(f"[ERROR] Ошибка обновления команд: {e}")



if __name__ == '__main__':
    from db import init_payments_table
    init_payments_table()
    import platform
    import sys
    import asyncio
    
    if sys.version_info >= (3, 12) and platform.system() == 'Linux':
        # Специальный патч для Python 3.12+ на Linux
        import asyncio.events
        asyncio.events._get_event_loop = asyncio.get_event_loop

    # Создание и настройка приложения    
    async def post_init_poll_payments(app):
        print("[DEBUG] post_init_poll_payments called")
        import utils
        import asyncio
        asyncio.create_task(utils.poll_yookassa_payments(app.bot, 60))

    # Создаем приложение с persistence для сохранения состояний
    persistence = PicklePersistence(filepath='bot_persistence.pickle')
    app = Application.builder()\
        .token(TELEGRAM_TOKEN)\
        .persistence(persistence)\
        .post_init(on_startup)\
        .post_init(post_init_poll_payments)\
        .build()

    # ЯВНЫЙ запуск poll_yookassa_payments для отладки
    import asyncio
    import utils

    
    # Регистрация обработчиков
    app.add_handler(CommandHandler('start', start))


    app.add_handler(CommandHandler('hc', hc))
    app.add_handler(CommandHandler('referral', referral))
    app.add_handler(CommandHandler('show_users', show_users))  # Только для админа
    app.add_handler(CommandHandler('subscribe', subscribe))
    
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
    app.add_handler(CommandHandler('get_tour_roster', get_tour_roster))

    # --- ConversationHandler для /tour ---
    TOUR_START, TOUR_FORWARD_1, TOUR_FORWARD_2, TOUR_FORWARD_3, TOUR_DEFENDER_1, TOUR_DEFENDER_2, TOUR_GOALIE, TOUR_CAPTAIN = range(8)
    tour_conv = ConversationHandler(
        entry_points=[CommandHandler('tour', tour_start)],
        states={
            TOUR_FORWARD_1: [
                CallbackQueryHandler(tour_forward_callback, pattern=r"^pick_\d+_нападающий$"),
                CallbackQueryHandler(restart_tour_callback, pattern=r"^restart_tour$")
            ],
            TOUR_FORWARD_2: [
                CallbackQueryHandler(tour_forward_callback, pattern=r"^pick_\d+_нападающий$"),
                CallbackQueryHandler(restart_tour_callback, pattern=r"^restart_tour$")
            ],
            TOUR_FORWARD_3: [
                CallbackQueryHandler(tour_forward_callback, pattern=r"^pick_\d+_нападающий$"),
                CallbackQueryHandler(restart_tour_callback, pattern=r"^restart_tour$")
            ],
            TOUR_DEFENDER_1: [
                CallbackQueryHandler(tour_defender_callback, pattern=r"^pick_\d+_защитник$"),
                CallbackQueryHandler(restart_tour_callback, pattern=r"^restart_tour$")
            ],
            TOUR_DEFENDER_2: [
                CallbackQueryHandler(tour_defender_callback, pattern=r"^pick_\d+_защитник$"),
                CallbackQueryHandler(restart_tour_callback, pattern=r"^restart_tour$")
            ],
            TOUR_GOALIE: [
                CallbackQueryHandler(tour_goalie_callback, pattern=r"^pick_\d+_вратарь$"),
                CallbackQueryHandler(restart_tour_callback, pattern=r"^restart_tour$")
            ],
            TOUR_CAPTAIN: [
                CallbackQueryHandler(tour_captain_callback, pattern=r"^pick_captain_\d+$"),
                CallbackQueryHandler(restart_tour_callback, pattern=r"^restart_tour$"),
                MessageHandler(filters.ALL, tour_captain)
            ],
        },
        fallbacks=[],
    )
    app.add_handler(tour_conv)
    # Глобальный обработчик для кнопки "Пересобрать состав"
    app.add_handler(CallbackQueryHandler(restart_tour_callback, pattern=r"^restart_tour$"))

    # ConversationHandler для установки бюджета
    set_budget_conv = ConversationHandler(
        entry_points=[CommandHandler('set_budget', set_budget_start)],
        states={
            21: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_budget_process)],
        },
        fallbacks=[],
    )
    app.add_handler(set_budget_conv)

    set_tour_roster_conv = ConversationHandler(
        entry_points=[CommandHandler('set_tour_roster', set_tour_roster_start)],
        states={
            20: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_tour_roster_process)],
        },
        fallbacks=[],
    )
    app.add_handler(set_tour_roster_conv)

    add_player_conv = ConversationHandler(
        entry_points=[CommandHandler('add_player', add_player_start)],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_player_name)],
            ADD_POSITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_player_position)],
            ADD_CLUB: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_player_club)],
            ADD_NATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_player_nation)],
            ADD_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_player_age)],
            ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_player_price)],
        },
        fallbacks=[CommandHandler('cancel', add_player_cancel)],
    )
    app.add_handler(add_player_conv)
    app.add_handler(CommandHandler('list_players', list_players))
    app.add_handler(CommandHandler('find_player', find_player))
    app.add_handler(CommandHandler('remove_player', remove_player))

    edit_player_conv = ConversationHandler(
        entry_points=[CommandHandler('edit_player', edit_player_start)],
        states={
            EDIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_player_name)],
            EDIT_POSITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_player_position)],
            EDIT_CLUB: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_player_club)],
            EDIT_NATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_player_nation)],
            EDIT_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_player_age)],
            EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_player_price)],
        },
        fallbacks=[CommandHandler('cancel', edit_player_cancel)],
    )
    app.add_handler(edit_player_conv)

    # --- Турнирные туры ---
    app.add_handler(create_tour_conv)
    app.add_handler(CommandHandler('list_tours', list_tours))
    app.add_handler(CommandHandler('activate_tour', activate_tour))

    # Установка команд для пользователей и админа
    user_commands = [
        BotCommand("start", "Регистрация и приветствие"),
        BotCommand("tour", "Показать состав игроков на тур"),
        BotCommand("hc", "Показать баланс HC"),
        BotCommand("subscribe", "Оформить подписку"),
        BotCommand("rules", "Правила сборки составов"),
    ]
    admin_commands = user_commands + [
        BotCommand("show_users", "Список пользователей и подписок (админ)"),
        BotCommand("send_tour_image", "Разослать изображение тура (админ)"),
        BotCommand("addhc", "Начислить HC пользователю (админ)"),
        BotCommand("send_results", "Разослать результаты тура (админ)"),
    ]

    # Установить команды для всех пользователей
    # await здесь нельзя, переносим в post_init

    # Запуск приложения
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('tour', tour_start))
    app.add_handler(CommandHandler('hc', hc))
    app.add_handler(CommandHandler('rules', rules))
    app.run_polling()



