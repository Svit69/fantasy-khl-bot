"""YooKassa integration removed; using Telegram Stars."""
# Backward-compat shim to avoid NameError in legacy debug print below
class Configuration:
    account_id = None
    secret_key = None
print("[DEBUG] Ключи установлены через Configuration.configure:", Configuration.account_id, Configuration.secret_key)
import os
import logging
import logging.handlers
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
    restart_tour_callback, tour_captain_callback, rules, referral, subscribe, \
    premium_add_pool_callback, premium_team_input, premium_position_selected, \
    challenge_command, challenge_level_callback, \
    challenge_open_callback, challenge_info_callback, challenge_build_callback, \
    challenge_pick_pos_callback, challenge_team_input, challenge_pick_player_callback, \
    challenge_cancel_callback, challenge_reshuffle_callback, \
    tours, tour_open_callback, tour_build_callback
from handlers.user_handlers import shop, shop_item_callback
from handlers.user_handlers import subscribe_stars, precheckout_callback, successful_payment_handler
from handlers.admin_handlers import addhc2 as addhc, send_results, show_users, list_active_subscribers
from handlers.admin_handlers import ChangePlayerPriceCommand, CheckChannelCommand
from handlers.admin_handlers import list_challenges, delete_challenge_cmd
from handlers.admin_handlers import challenge_rosters_cmd
from handlers.show_hc_users import show_hc_users
# Override with UTF‑8 safe output
from handlers.challenge_rosters_fix import challenge_rosters_cmd as _challenge_rosters_cmd_fixed
challenge_rosters_cmd = _challenge_rosters_cmd_fixed
from handlers.admin_handlers import (
    send_challenge_image_start,
    challenge_input_start_date,
    challenge_input_deadline,
    challenge_input_end_date,
    send_challenge_image_photo,
    send_challenge_image_cancel,
    CHALLENGE_MODE,
    CHALLENGE_START,
    CHALLENGE_DEADLINE,
    CHALLENGE_END,
    CHALLENGE_WAIT_IMAGE,
)
from handlers.admin_handlers import (
    ADD_NAME, ADD_POSITION, ADD_CLUB, ADD_NATION, ADD_AGE, ADD_PRICE,
    add_player_start, add_player_name, add_player_position, add_player_club,
    add_player_nation, add_player_age, add_player_price, add_player_cancel, list_players, find_player,
    remove_player, edit_player_start, edit_player_name, edit_player_position, edit_player_club,
    edit_player_nation, edit_player_age, edit_player_price, edit_player_cancel,
    set_tour_roster_start, set_tour_roster_process, get_tour_roster,
    set_budget_start, set_budget_process,
    create_tour_conv, list_tours, activate_tour
)
from handlers.create_tour_full_fix import (
    start as ctff_start,
    name as ctff_name,
    start_date as ctff_start_date,
    deadline as ctff_deadline,
    end_date as ctff_end_date,
    photo as ctff_photo,
    roster as ctff_roster,
    cancel as ctff_cancel,
    FCT_NAME, FCT_START, FCT_DEADLINE, FCT_END, FCT_IMAGE, FCT_ROSTER,
)
from handlers.admin_handlers import (
    add_image_shop_start, add_image_shop_text, add_image_shop_photo, add_image_shop_cancel,
    SHOP_TEXT_WAIT, SHOP_IMAGE_WAIT
)
from handlers.admin_handlers import (
    purge_tours_start, purge_tours_password, purge_tours_cancel, PURGE_WAIT_PASSWORD
)

# broadcast to subscribers
from handlers.admin_handlers import (
    broadcast_subscribers_start, broadcast_subscribers_text, broadcast_subscribers_datetime, broadcast_subscribers_cancel,
    BROADCAST_SUBS_WAIT_TEXT, BROADCAST_SUBS_WAIT_DATETIME, BROADCAST_SUBS_CONFIRM,
)
# Override confirm handler to support Russian inputs and avoid mojibake
try:
    from handlers.broadcast_fix import broadcast_subscribers_confirm as _broadcast_subscribers_confirm
except Exception:
    try:
        from handlers.admin_handlers import broadcast_subscribers_confirm as _broadcast_subscribers_confirm
    except Exception:
        _broadcast_subscribers_confirm = None
broadcast_subscribers_confirm = _broadcast_subscribers_confirm
from handlers.addhc_fix import addhc2 as _addhc2_fixed
addhc = _addhc2_fixed
from handlers.list_tours_fix import list_tours as _list_tours_fixed
list_tours = _list_tours_fixed
from handlers.challenge_send_image_fix import (
    send_challenge_image_start as _scimg_start,
    challenge_mode_select as _scimg_mode_select,
    challenge_input_start_date as _scimg_start_date,
    challenge_input_deadline as _scimg_deadline,
    challenge_input_end_date as _scimg_end_date,
    send_challenge_image_photo as _scimg_photo,
    send_challenge_image_cancel as _scimg_cancel,
)
send_challenge_image_start = _scimg_start
challenge_mode_select = _scimg_mode_select
challenge_input_start_date = _scimg_start_date
challenge_input_deadline = _scimg_deadline
challenge_input_end_date = _scimg_end_date
send_challenge_image_photo = _scimg_photo
send_challenge_image_cancel = _scimg_cancel

# Send message to a single user (admin)
from handlers.admin_handlers import (
    message_user_start, message_user_target, message_user_text,
    message_user_datetime, message_user_photo_decision, message_user_photo, message_user_confirm,
    message_users_bulk_start, message_users_bulk_recipients, message_users_bulk_text,
    message_users_bulk_schedule, message_users_bulk_photo_decision, message_users_bulk_photo, message_users_bulk_cancel,
    MSG_USER_WAIT_TARGET, MSG_USER_WAIT_TEXT, MSG_USER_WAIT_DATETIME, MSG_USER_WAIT_PHOTO_DECISION, MSG_USER_WAIT_PHOTO, MSG_USER_CONFIRM,
    BULK_MSG_WAIT_RECIPIENTS, BULK_MSG_WAIT_TEXT, BULK_MSG_WAIT_SCHEDULE, BULK_MSG_WAIT_PHOTO_DECISION, BULK_MSG_WAIT_PHOTO,
    referral_limit_decision_callback,
    block_user_start, block_user_target, block_user_username, block_user_password, block_user_confirm, block_user_cancel,
    BLOCK_USER_WAIT_TARGET, BLOCK_USER_WAIT_USERNAME, BLOCK_USER_WAIT_PASSWORD, BLOCK_USER_WAIT_CONFIRM,
)

from handlers.admin_handlers import (
    ADD_NAME, ADD_POSITION, ADD_CLUB, ADD_NATION, ADD_AGE, ADD_PRICE,
    EDIT_NAME, EDIT_POSITION, EDIT_CLUB, EDIT_NATION, EDIT_AGE, EDIT_PRICE
)

# Настройка логирования: в файл и в консоль
import sys
os.makedirs('logs', exist_ok=True)
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler('logs/bot.log', encoding='utf-8')
file_handler.setFormatter(log_formatter)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)

# Настройка корневого логгера
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Логгер для этого модуля
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Логгер для telegram
logging.getLogger('telegram').setLevel(logging.INFO)
logging.getLogger('httpx').setLevel(logging.WARNING)

logger.info("=== Bot starting with enhanced logging ===")

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
        BotCommand("challenge", "Челлендж против редакции"),
        BotCommand("shop", "Магазин призов"),
    ]
    # Для меню админа показываем только одну команду справки
    # Ensure referral command is present in the menu
    user_commands.insert(3, BotCommand("referral", "получить реферальную ссылку"))
    # Temporary alias while users migrate from the misspelled command
    user_commands.insert(4, BotCommand("refferal", "получить реферальную ссылку (алиас)"))
    admin_commands = user_commands + [
        BotCommand("admin_help", "Справка по админ-командам"),
    ]
    admin_commands.append(BotCommand("message_users", "рассылка по списку пользователей"))
    admin_commands.append(BotCommand("list_active_subscribers", "показать активных подписчиков"))
    admin_commands.append(BotCommand("change_player_price", "изменить стоимость игроков"))
    admin_commands.append(BotCommand("check_channel", "проверить подписку на t.me/goalevaya"))
    admin_commands.append(BotCommand("refresh_commands", "обновить меню команд"))
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
    from db import init_referrals_table
    init_referrals_table()
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
        # YooKassa polling removed (replaced by Telegram Stars)
        # Запускаем напоминания о подписке (каждый час)
        asyncio.create_task(utils.poll_subscription_reminders(app.bot, 3600))

    # Создаем приложение с persistence для сохранения состояний
    persistence = PicklePersistence(
        filepath='bot_persistence.pickle',
        update_interval=5,
        single_file=True
    )
    
    # Настройка логгирования
    log_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Консольный вывод
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_formatter)
    
    # Файловый вывод с ротацией
    os.makedirs('logs', exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        'logs/bot.log',
        maxBytes=5*1024*1024,  # 5 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_formatter)
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Установка уровня логирования для библиотек
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.INFO)
    
    logger = logging.getLogger(__name__)
    logger.info("Логгирование инициализировано")
    logger = logging.getLogger(__name__)
    
    app = (Application.builder()
        .token(TELEGRAM_TOKEN)
        .persistence(persistence)
        .post_init(on_startup)
        .post_init(post_init_poll_payments)
        .build())

    # ЯВНЫЙ запуск poll_yookassa_payments для отладки
    import asyncio
    import utils

    # Wrap handlers with detailed logging
    async def log_add_player_start(update, context):
        logger.info(f"[add_player_start] User {update.effective_user.id} started /add_player")
        logger.info(f"[DEBUG] User data before start: {context.user_data}")
        try:
            result = await add_player_start(update, context)
            logger.info(f"[DEBUG] add_player_start returned: {result}")
            return result
        except Exception as e:
            logger.error(f"[ERROR] in add_player_start: {e}", exc_info=True)
            raise

    async def log_add_player_name(update, context):
        logger.info(f"[log_add_player_name] Starting with message: {update.message.text}")
        logger.info(f"[log_add_player_name] Current user_data: {context.user_data}")
        logger.info(f"[log_add_player_name] Chat ID: {update.effective_chat.id}, User ID: {update.effective_user.id}")
        
        try:
            # Safely get conversation state
            current_state = None
            try:
                conversations = await context.application.persistence.get_conversations('add_player')
                if conversations:
                    current_state = conversations.get((update.effective_chat.id, update.effective_user.id))
                logger.info(f"[log_add_player_name] Current conversation state: {current_state}")
            except Exception as conv_error:
                logger.warning(f"[log_add_player_name] Could not get conversation state: {conv_error}")
            
            # Call the actual handler
            logger.info("[log_add_player_name] Calling add_player_name...")
            try:
                result = await add_player_name(update, context)
                logger.info(f"[log_add_player_name] add_player_name returned: {result}")
                return result
            except Exception as handler_error:
                logger.error(f"[log_add_player_name] Error in add_player_name: {handler_error}", exc_info=True)
                await update.message.reply_text(
                    "Произошла ошибка при обработке имени игрока. "
                    "Пожалуйста, попробуйте еще раз или начните заново командой /add_player."
                )
                return ADD_NAME  # Return to name input state
            
            # Verify the next state is valid
            if result not in [ADD_POSITION, ConversationHandler.END]:
                logger.error(f"[log_add_player_name] Invalid state returned: {result}")
                
            return result
            
        except Exception as e:
            logger.error(f"[ERROR] in log_add_player_name: {str(e)}", exc_info=True)
            await update.message.reply_text("Произошла ошибка при обработке имени игрока. Пожалуйста, попробуйте снова.")
            return ConversationHandler.END

    async def log_add_player_position(update, context):
        logger.info(f"[log_add_player_position] Received position: {update.message.text}")
        logger.info(f"[log_add_player_position] Current user_data: {context.user_data}")
        logger.info(f"[log_add_player_position] Chat ID: {update.effective_chat.id}, User ID: {update.effective_user.id}")
        
        try:
            # Safely get conversation state
            current_state = None
            try:
                conversations = await context.application.persistence.get_conversations('add_player')
                if conversations:
                    current_state = conversations.get((update.effective_chat.id, update.effective_user.id))
                logger.info(f"[log_add_player_position] Current conversation state: {current_state}")
            except Exception as conv_error:
                logger.warning(f"[log_add_player_position] Could not get conversation state: {conv_error}")
            
            # Call the actual handler
            logger.info("[log_add_player_position] Calling add_player_position...")
            try:
                result = await add_player_position(update, context)
                logger.info(f"[log_add_player_position] add_player_position returned: {result}")
                return result
            except Exception as handler_error:
                logger.error(f"[log_add_player_position] Error in add_player_position: {handler_error}", exc_info=True)
                await update.message.reply_text(
                    "Произошла ошибка при обработке позиции игрока. "
                    "Пожалуйста, попробуйте еще раз или начните заново командой /add_player."
                )
                return ADD_POSITION  # Return to position input state
            
        except Exception as e:
            logger.error(f"[ERROR] in log_add_player_position: {str(e)}", exc_info=True)
            await update.message.reply_text("Произошла ошибка при обработке позиции игрока. Пожалуйста, попробуйте снова.")
            return ADD_POSITION
            
    async def log_add_player_club(update, context):
        logger.info(f"[log_add_player_club] Received club: {update.message.text}")
        logger.info(f"[log_add_player_club] Current user_data: {context.user_data}")
        logger.info(f"[log_add_player_club] Chat ID: {update.effective_chat.id}, User ID: {update.effective_user.id}")
        
        try:
            # Safely get conversation state
            current_state = None
            try:
                conversations = await context.application.persistence.get_conversations('add_player')
                if conversations:
                    current_state = conversations.get((update.effective_chat.id, update.effective_user.id))
                logger.info(f"[log_add_player_club] Current conversation state: {current_state}")
            except Exception as conv_error:
                logger.warning(f"[log_add_player_club] Could not get conversation state: {conv_error}")
            
            # Call the actual handler
            logger.info("[log_add_player_club] Calling add_player_club...")
            try:
                result = await add_player_club(update, context)
                logger.info(f"[log_add_player_club] add_player_club returned: {result}")
                return result
            except Exception as handler_error:
                logger.error(f"[log_add_player_club] Error in add_player_club: {handler_error}", exc_info=True)
                await update.message.reply_text(
                    "Произошла ошибка при обработке клуба игрока. "
                    "Пожалуйста, попробуйте еще раз или начните заново командой /add_player."
                )
                return ADD_CLUB  # Return to club input state
            
        except Exception as e:
            logger.error(f"[ERROR] in log_add_player_club: {str(e)}", exc_info=True)
            await update.message.reply_text("Произошла ошибка при обработке клуба игрока. Пожалуйста, попробуйте снова.")
            return ADD_CLUB
            
    async def log_add_player_nation(update, context):
        logger.info(f"[log_add_player_nation] Received nation: {update.message.text}")
        logger.info(f"[log_add_player_nation] Current user_data: {context.user_data}")
        logger.info(f"[log_add_player_nation] Chat ID: {update.effective_chat.id}, User ID: {update.effective_user.id}")
        
        try:
            # Safely get conversation state
            current_state = None
            try:
                conversations = await context.application.persistence.get_conversations('add_player')
                if conversations:
                    current_state = conversations.get((update.effective_chat.id, update.effective_user.id))
                logger.info(f"[log_add_player_nation] Current conversation state: {current_state}")
            except Exception as conv_error:
                logger.warning(f"[log_add_player_nation] Could not get conversation state: {conv_error}")
            
            # Call the actual handler
            logger.info("[log_add_player_nation] Calling add_player_nation...")
            try:
                result = await add_player_nation(update, context)
                logger.info(f"[log_add_player_nation] add_player_nation returned: {result}")
                return result
            except Exception as handler_error:
                logger.error(f"[log_add_player_nation] Error in add_player_nation: {handler_error}", exc_info=True)
                await update.message.reply_text(
                    "Произошла ошибка при обработке национальности игрока. "
                    "Пожалуйста, попробуйте еще раз или начните заново командой /add_player."
                )
                return ADD_NATION  # Return to nation input state
            
        except Exception as e:
            logger.error(f"[ERROR] in log_add_player_nation: {str(e)}", exc_info=True)
            await update.message.reply_text("Произошла ошибка при обработке национальности игрока. Пожалуйста, попробуйте снова.")
            return ADD_NATION
            
    async def log_add_player_age(update, context):
        logger.info(f"[log_add_player_age] Received age: {update.message.text}")
        logger.info(f"[log_add_player_age] Current user_data: {context.user_data}")
        logger.info(f"[log_add_player_age] Chat ID: {update.effective_chat.id}, User ID: {update.effective_user.id}")
        
        try:
            # Safely get conversation state
            current_state = None
            try:
                conversations = await context.application.persistence.get_conversations('add_player')
                if conversations:
                    current_state = conversations.get((update.effective_chat.id, update.effective_user.id))
                logger.info(f"[log_add_player_age] Current conversation state: {current_state}")
            except Exception as conv_error:
                logger.warning(f"[log_add_player_age] Could not get conversation state: {conv_error}")
            
            # Call the actual handler
            logger.info("[log_add_player_age] Calling add_player_age...")
            try:
                result = await add_player_age(update, context)
                logger.info(f"[log_add_player_age] add_player_age returned: {result}")
                return result
            except Exception as handler_error:
                logger.error(f"[log_add_player_age] Error in add_player_age: {handler_error}", exc_info=True)
                await update.message.reply_text(
                    "Произошла ошибка при обработке возраста игрока. "
                    "Пожалуйста, попробуйте еще раз или начните заново командой /add_player."
                )
                return ADD_AGE  # Return to age input state
            
        except Exception as e:
            logger.error(f"[ERROR] in log_add_player_age: {str(e)}", exc_info=True)
            await update.message.reply_text("Произошла ошибка при обработке возраста игрока. Пожалуйста, попробуйте снова.")
            return ADD_AGE
            
    async def log_add_player_price(update, context):
        logger.info(f"[log_add_player_price] Received price: {update.message.text}")
        logger.info(f"[log_add_player_price] Current user_data: {context.user_data}")
        logger.info(f"[log_add_player_price] Chat ID: {update.effective_chat.id}, User ID: {update.effective_user.id}")
        
        try:
            # Safely get conversation state
            current_state = None
            try:
                conversations = await context.application.persistence.get_conversations('add_player')
                if conversations:
                    current_state = conversations.get((update.effective_chat.id, update.effective_user.id))
                logger.info(f"[log_add_player_price] Current conversation state: {current_state}")
            except Exception as conv_error:
                logger.warning(f"[log_add_player_price] Could not get conversation state: {conv_error}")
            
            # Call the actual handler
            logger.info("[log_add_player_price] Calling add_player_price...")
            try:
                result = await add_player_price(update, context)
                logger.info(f"[log_add_player_price] add_player_price returned: {result}")
                return result
            except Exception as handler_error:
                logger.error(f"[log_add_player_price] Error in add_player_price: {handler_error}", exc_info=True)
                await update.message.reply_text(
                    "Произошла ошибка при обработке цены игрока. "
                    "Пожалуйста, попробуйте еще раз или начните заново командой /add_player."
                )
                return ADD_PRICE  # Return to price input state
            
        except Exception as e:
            logger.error(f"[ERROR] in log_add_player_price: {str(e)}", exc_info=True)
            await update.message.reply_text("Произошла ошибка при обработке цены игрока. Пожалуйста, попробуйте снова.")
            return ADD_PRICE

    # Определение ConversationHandler для добавления игрока
    add_player_conv = ConversationHandler(
        entry_points=[
            CommandHandler('add_player', log_add_player_start),
            CommandHandler('addplayer', log_add_player_start),  # Альтернативная команда
        ],
        states={
            ADD_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, log_add_player_name),
                CommandHandler('cancel', add_player_cancel)
            ],
            ADD_POSITION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, log_add_player_position),
                CommandHandler('cancel', add_player_cancel)
            ],
            ADD_CLUB: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, log_add_player_club),
                CommandHandler('cancel', add_player_cancel)
            ],
            ADD_NATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, log_add_player_nation),
                CommandHandler('cancel', add_player_cancel)
            ],
            ADD_AGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, log_add_player_age),
                CommandHandler('cancel', add_player_cancel)
            ],
            ADD_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, log_add_player_price),
                CommandHandler('cancel', add_player_cancel)
            ],
        },
        fallbacks=[
            CommandHandler('cancel', add_player_cancel),
            MessageHandler(filters.ALL, lambda update, context: logger.warning(f"Unexpected message in conversation: {update.message.text}"))
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=True,
        name="add_player_conversation"
    )

    # Регистрация обработчиков
    app.add_handler(CommandHandler('start', start))
    
    # Регистрация ConversationHandler для добавления игрока
    app.add_handler(add_player_conv)

    app.add_handler(CommandHandler('hc', hc))
    # Add both the correct command and a temporary alias
    app.add_handler(CommandHandler('referral', referral))
    app.add_handler(CommandHandler('refferal', referral))
    app.add_handler(CommandHandler('show_users', show_users))  # Только для админа
    app.add_handler(CommandHandler('list_active_subscribers', list_active_subscribers))  # Только для админа
    app.add_handler(CommandHandler('show_hc_users', show_hc_users))  # Только для админа
    app.add_handler(CommandHandler('subscribe', subscribe_stars))
    # Telegram Stars payments handlers
    from telegram.ext import PreCheckoutQueryHandler as _PreCheckoutQueryHandler  # local import to avoid top-level churn
    app.add_handler(_PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    app.add_handler(CommandHandler('shop', shop))
    app.add_handler(CallbackQueryHandler(shop_item_callback, pattern=r"^shop_item_\d+$"))
    app.add_handler(CommandHandler('challenge', challenge_command))
    
    async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            uid = update.effective_user.id if update.effective_user else None
        except Exception:
            uid = None
        if uid != ADMIN_ID:
            return
        text = (
            "<b>Админские команды</b>\n\n"
            "<b>Управление пользователями:</b>\n"
            "• /show_users — список пользователей и подписок\n"
            "• /show_hc_users — пользователи с балансом HC > 0\n"
            "• /list_active_subscribers — активные подписчики и окончание подписки\n"
            "• /addhc — начислить HC пользователю\n"
            "• /broadcast_subscribers — рассылка всем активным подписчикам к указанным дате и времени (админ)\n\n"
            "• /message_user — отправить сообщение одному пользователю по @username или ID (с подтверждением и временем МСК)\n"
            "• /message_users — рассылка по списку пользователей (текст, расписание и картинка)\n"
            "• /block_user — заблокировать пользователя (ID + @username + пароль + подтверждение)\n"
            "• /check_channel — проверить подписку пользователей на канал t.me/goalevaya\n\n"
            "<b>Управление турами:</b>\n"
            "• /send_results — разослать результаты тура\n"
            "• /set_budget — установить бюджет тура\n"
            "• /create_tour_full — создать тур (пакетный диалог: название, даты, картинка, ростер)\n"
            "• /list_tours\n"
            "• /activate_tour\n"
            "• /purge_tours — удалить все туры (по паролю)\n"
            "• /delete_tour — удалить один тур по id (по паролю)\n"
            "• /delete_sub_by_username — удалить подписку у пользователя (по паролю)\n"
            "• /purge_subscriptions — удалить все подписки (по паролю)\n"
            "• /tour_managers [tour_id] — список менеджеров с зарегистрированными составами на тур\n\n"
            "<b>Управление хоккеистами:</b>\n"
            "• /list_players — список игроков\n"
            "• /find_player — поиск игрока\n"
            "• /add_player — добавить игрока\n"
            "• /edit_player — отредактировать игрока\n"
            "• /change_player_price — изменить стоимость игроков списком\n"
            "• /remove_player — удалить игрока\n\n"
            "<b>Управление челленджами:</b>\n"
            "• /list_challenges — список челленджей\n"
            "• /delete_challenge &lt;id&gt; — удалить челлендж по id\n"
            "• /challenge_rosters &lt;id&gt; — составы участников челленджа по id\n"
            "• /send_challenge_image — зарегистрировать челлендж (даты + картинка)\n\n"
            "<b>Магазин:</b>\n"
            "• /add_image_shop — задать текст и изображение магазина (диалог)\n"
        )
        text += "\n• /refresh_commands — обновить меню команд"
        try:
            await update.message.reply_text(text, parse_mode='HTML')
        except Exception:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode='HTML')

    app.add_handler(CommandHandler('admin_help', admin_help))

    async def refresh_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            uid = update.effective_user.id if update.effective_user else None
        except Exception:
            uid = None
        if uid != ADMIN_ID:
            return
        try:
            await on_startup(context.application)
            try:
                await update.message.reply_text('Команды обновлены (default, ru, private, admin).')
            except Exception:
                await context.bot.send_message(chat_id=update.effective_chat.id, text='Команды обновлены (default, ru, private, admin).')
        except Exception as e:
            try:
                await update.message.reply_text(f'Ошибка при обновлении команд: {e}')
            except Exception:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f'Ошибка при обновлении команд: {e}')

    app.add_handler(CommandHandler('refresh_commands', refresh_commands))

    # --- ConversationHandlers: удаление подписок ---
    from handlers.admin_handlers import (
        delete_sub_by_username_start, delete_sub_by_username_password, delete_sub_by_username_username,
        delete_sub_by_username_cancel, DEL_SUB_WAIT_PASSWORD, DEL_SUB_WAIT_USERNAME,
        purge_subscriptions_start, purge_subscriptions_password, PURGE_SUBS_WAIT_PASSWORD,
        delete_tour_start, delete_tour_password, delete_tour_id, delete_tour_cancel,
        DEL_TOUR_WAIT_PASSWORD, DEL_TOUR_WAIT_ID,
    )

    del_sub_conv = ConversationHandler(
        entry_points=[CommandHandler('delete_sub_by_username', delete_sub_by_username_start)],
        states={
            DEL_SUB_WAIT_PASSWORD: [MessageHandler(filters.TEXT & (~filters.COMMAND), delete_sub_by_username_password)],
            DEL_SUB_WAIT_USERNAME: [MessageHandler(filters.TEXT & (~filters.COMMAND), delete_sub_by_username_username)],
        },
        fallbacks=[CommandHandler('cancel', delete_sub_by_username_cancel)],
        allow_reentry=True,
        name="delete_sub_by_username_conv",
        persistent=False,
    )
    app.add_handler(del_sub_conv)

    purge_subs_conv = ConversationHandler(
        entry_points=[CommandHandler('purge_subscriptions', purge_subscriptions_start)],
        states={
            PURGE_SUBS_WAIT_PASSWORD: [MessageHandler(filters.TEXT & (~filters.COMMAND), purge_subscriptions_password)],
        },
        fallbacks=[CommandHandler('cancel', purge_tours_cancel)],
        allow_reentry=True,
        name="purge_subscriptions_conv",
        persistent=False,
    )
    app.add_handler(purge_subs_conv)

    # --- ConversationHandler: /delete_tour ---
    delete_tour_conv = ConversationHandler(
        entry_points=[CommandHandler('delete_tour', delete_tour_start)],
        states={
            DEL_TOUR_WAIT_PASSWORD: [MessageHandler(filters.TEXT & (~filters.COMMAND), delete_tour_password)],
            DEL_TOUR_WAIT_ID: [MessageHandler(filters.TEXT & (~filters.COMMAND), delete_tour_id)],
        },
        fallbacks=[CommandHandler('cancel', delete_tour_cancel)],
        allow_reentry=True,
        name="delete_tour_conv",
        persistent=False,
    )
    app.add_handler(delete_tour_conv)

    # --- /tour_managers [tour_id] ---
    async def tour_managers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id if update.effective_user else None
        if uid != ADMIN_ID:
            return
        # Определяем tour_id
        tour_id = None
        try:
            if context.args and len(context.args) >= 1:
                tour_id = int(context.args[0])
        except Exception:
            tour_id = None
        if not tour_id:
            try:
                from db import get_active_tour
                at = get_active_tour()
                tour_id = at['id'] if at else None
            except Exception:
                tour_id = None
        if not tour_id:
            await update.message.reply_text("Тур не найден. Укажи id: /tour_managers <id>")
            return
        # Забираем менеджеров
        try:
            from db import get_tour_managers
            rows = get_tour_managers(tour_id)
        except Exception as e:
            await update.message.reply_text(f"Ошибка БД: {e}")
            return
        if not rows:
            await update.message.reply_text(f"Для тура #{tour_id} составы не найдены.")
            return
        # Форматируем подробный вывод с полным составом каждого менеджера
        def name_club(pid):
            try:
                from db import get_player_by_id
                p = get_player_by_id(int(pid))
                if p:
                    return f"{p[1]} ({p[3]})"
            except Exception:
                pass
            return str(pid)

        chunks = []
        cur = [f"Менеджеры с составами для тура #{tour_id}:", ""]
        for r in rows:
            try:
                from db import get_user_tour_roster
                ut = get_user_tour_roster(r['user_id'], tour_id)
            except Exception:
                ut = None
            roster = ut.get('roster') if (ut and isinstance(ut, dict)) else None
            captain_id = ut.get('captain_id') if ut else None
            uname = ("@" + r['username']) if r.get('username') else "—"
            name = r.get('name') or "—"
            spent = r.get('spent')
            ts = r.get('timestamp')

            # Шапка для менеджера
            cur.append(f"• {uname} | {name}")
            # Состав
            if roster:
                try:
                    gid = roster.get('goalie')
                    goalie_line = name_club(gid) if gid else "—"
                except Exception:
                    goalie_line = "—"
                try:
                    dids = roster.get('defenders', []) or []
                    defenders_line = " - ".join([name_club(x) for x in dids if x])
                except Exception:
                    defenders_line = ""
                try:
                    fids = roster.get('forwards', []) or []
                    forwards_line = " - ".join([name_club(x) for x in fids if x])
                except Exception:
                    forwards_line = ""
                try:
                    captain_line = name_club(captain_id) if captain_id else "—"
                except Exception:
                    captain_line = "—"

                cur.append(goalie_line)
                cur.append(defenders_line)
                cur.append(forwards_line)
                cur.append(f"Капитан: {captain_line}")
            else:
                cur.append("(состав не найден)")

            cur.append(f"Потрачено: {spent} | Время: {ts}")
            cur.append("")

            # Разбиение по ограничению Telegram (примерно 4096 символов)
            joined = "\n".join(cur)
            if len(joined) > 3500:  # небольшой запас
                chunks.append(joined)
                cur = []
        if cur:
            chunks.append("\n".join(cur))

        # Отправляем по частям
        for part in chunks:
            try:
                await update.message.reply_text(part)
            except Exception:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=part)

    app.add_handler(CommandHandler('tour_managers', tour_managers_cmd))
    
    send_tour_image_conv = ConversationHandler(
        entry_points=[CommandHandler('send_tour_image', send_tour_image_start)],
        states={
            WAIT_IMAGE: [MessageHandler(filters.PHOTO, send_tour_image_photo)]
        },
        fallbacks=[CommandHandler('cancel', send_tour_image_cancel)],
        allow_reentry=True
    )
    app.add_handler(send_tour_image_conv)
    # --- ConversationHandler для send_challenge_image ---
    send_challenge_image_conv = ConversationHandler(
        entry_points=[CommandHandler('send_challenge_image', send_challenge_image_start)],
        states={
            CHALLENGE_MODE: [
                CallbackQueryHandler(challenge_mode_select, pattern=r"^challenge_mode_(?:default|under21)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, challenge_mode_select),
            ],
            CHALLENGE_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, challenge_input_start_date)],
            CHALLENGE_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, challenge_input_deadline)],
            CHALLENGE_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, challenge_input_end_date)],
            CHALLENGE_WAIT_IMAGE: [MessageHandler(filters.PHOTO, send_challenge_image_photo)],
        },
        fallbacks=[CommandHandler('cancel', send_challenge_image_cancel)],
        allow_reentry=True
    )
    app.add_handler(send_challenge_image_conv)
    # --- ConversationHandler для /add_image_shop (админ) ---
    add_image_shop_conv = ConversationHandler(
        entry_points=[CommandHandler('add_image_shop', add_image_shop_start)],
        states={
            SHOP_TEXT_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_image_shop_text)],
            SHOP_IMAGE_WAIT: [MessageHandler(filters.PHOTO, add_image_shop_photo)],
        },
        fallbacks=[CommandHandler('cancel', add_image_shop_cancel)],
        allow_reentry=True
    )
    app.add_handler(add_image_shop_conv)

    # --- ConversationHandler для /broadcast_subscribers (админ) ---
    broadcast_subscribers_conv = ConversationHandler(
        entry_points=[CommandHandler('broadcast_subscribers', broadcast_subscribers_start)],
        states={
            BROADCAST_SUBS_WAIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_subscribers_text)],
            BROADCAST_SUBS_WAIT_DATETIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_subscribers_datetime)],
            BROADCAST_SUBS_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_subscribers_confirm)],
        },
        fallbacks=[CommandHandler('cancel', broadcast_subscribers_cancel)],
        name="broadcast_subscribers_conv",
    )
    app.add_handler(broadcast_subscribers_conv)

    # --- ConversationHandler для /message_user (админ) ---
    message_user_conv = ConversationHandler(
        entry_points=[CommandHandler('message_user', message_user_start)],
        states={
            MSG_USER_WAIT_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, message_user_target)],
            MSG_USER_WAIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, message_user_text)],
            MSG_USER_WAIT_DATETIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, message_user_datetime)],
            MSG_USER_WAIT_PHOTO_DECISION: [MessageHandler(filters.TEXT & ~filters.COMMAND, message_user_photo_decision)],
            MSG_USER_WAIT_PHOTO: [
                MessageHandler(filters.PHOTO, message_user_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, message_user_photo),
            ],
            MSG_USER_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, message_user_confirm)],
        },
        fallbacks=[CommandHandler('cancel', broadcast_subscribers_cancel)],
        name="message_user_conv",
    )
    app.add_handler(message_user_conv)

    message_users_conv = ConversationHandler(
        entry_points=[CommandHandler('message_users', message_users_bulk_start)],
        states={
            BULK_MSG_WAIT_RECIPIENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, message_users_bulk_recipients)],
            BULK_MSG_WAIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, message_users_bulk_text)],
            BULK_MSG_WAIT_SCHEDULE: [MessageHandler(filters.TEXT & ~filters.COMMAND, message_users_bulk_schedule)],
            BULK_MSG_WAIT_PHOTO_DECISION: [MessageHandler(filters.TEXT & ~filters.COMMAND, message_users_bulk_photo_decision)],
            BULK_MSG_WAIT_PHOTO: [
                MessageHandler(filters.PHOTO, message_users_bulk_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, message_users_bulk_photo),
            ],
        },
        fallbacks=[CommandHandler('cancel', message_users_bulk_cancel)],
        name="message_users_bulk_conv",
    )
    app.add_handler(message_users_conv)

    block_user_conv = ConversationHandler(
        entry_points=[CommandHandler('block_user', block_user_start)],
        states={
            BLOCK_USER_WAIT_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, block_user_target)],
            BLOCK_USER_WAIT_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, block_user_username)],
            BLOCK_USER_WAIT_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, block_user_password)],
            BLOCK_USER_WAIT_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, block_user_confirm)],
        },
        fallbacks=[CommandHandler('cancel', block_user_cancel)],
        name="block_user_conv",
    )
    app.add_handler(block_user_conv)
    # Список туров и колбэки
    app.add_handler(CommandHandler('tours', tours))
    app.add_handler(CommandHandler('tour', tours))  # для совместимости и удобства
    app.add_handler(CallbackQueryHandler(tour_open_callback, pattern=r"^tour_open_\d+$"))
    app.add_handler(CommandHandler('addhc', addhc))
    app.add_handler(CommandHandler('send_results', send_results))
    app.add_handler(CommandHandler('list_challenges', list_challenges))
    app.add_handler(CommandHandler('delete_challenge', delete_challenge_cmd))
    app.add_handler(CommandHandler('challenge_rosters', challenge_rosters_cmd))
    app.add_handler(CommandHandler('get_tour_roster', get_tour_roster))

    # --- ConversationHandler: /purge_tours ---
    purge_tours_conv = ConversationHandler(
        entry_points=[CommandHandler('purge_tours', purge_tours_start)],
        states={
            PURGE_WAIT_PASSWORD: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), purge_tours_password)
            ]
        },
        fallbacks=[CommandHandler('cancel', purge_tours_cancel)],
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=False,
        name="purge_tours_conv",
        persistent=False,
    )
    app.add_handler(purge_tours_conv)

    # --- ConversationHandler для выбора состава (запускается из кнопки "Собрать состав") ---
    TOUR_START, TOUR_FORWARD_1, TOUR_FORWARD_2, TOUR_FORWARD_3, TOUR_DEFENDER_1, TOUR_DEFENDER_2, TOUR_GOALIE, TOUR_CAPTAIN, PREMIUM_TEAM, PREMIUM_POSITION = range(10)
    tour_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(tour_build_callback, pattern=r"^tour_build_\d+$")],
        states={
            TOUR_FORWARD_1: [
                CallbackQueryHandler(premium_add_pool_callback, pattern=r"^premium_add_pool$"),
                CallbackQueryHandler(tour_forward_callback, pattern=r"^pick_\d+_нападающий$"),
                CallbackQueryHandler(restart_tour_callback, pattern=r"^restart_tour$")
            ],
            PREMIUM_TEAM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, premium_team_input)
            ],
            PREMIUM_POSITION: [
                CallbackQueryHandler(premium_position_selected, pattern=r"^premium_pos_(нападающий|защитник|вратарь)$")
            ],
            TOUR_FORWARD_2: [
                CallbackQueryHandler(premium_add_pool_callback, pattern=r"^premium_add_pool$"),
                CallbackQueryHandler(tour_forward_callback, pattern=r"^pick_\d+_нападающий$"),
                CallbackQueryHandler(restart_tour_callback, pattern=r"^restart_tour$")
            ],
            TOUR_FORWARD_3: [
                CallbackQueryHandler(premium_add_pool_callback, pattern=r"^premium_add_pool$"),
                CallbackQueryHandler(tour_forward_callback, pattern=r"^pick_\d+_нападающий$"),
                CallbackQueryHandler(restart_tour_callback, pattern=r"^restart_tour$")
            ],
            TOUR_DEFENDER_1: [
                CallbackQueryHandler(premium_add_pool_callback, pattern=r"^premium_add_pool$"),
                CallbackQueryHandler(tour_defender_callback, pattern=r"^pick_\d+_защитник$"),
                CallbackQueryHandler(restart_tour_callback, pattern=r"^restart_tour$")
            ],
            TOUR_DEFENDER_2: [
                CallbackQueryHandler(premium_add_pool_callback, pattern=r"^premium_add_pool$"),
                CallbackQueryHandler(tour_defender_callback, pattern=r"^pick_\d+_защитник$"),
                CallbackQueryHandler(restart_tour_callback, pattern=r"^restart_tour$")
            ],
            TOUR_GOALIE: [
                CallbackQueryHandler(premium_add_pool_callback, pattern=r"^premium_add_pool$"),
                CallbackQueryHandler(tour_goalie_callback, pattern=r"^pick_\d+_вратарь$"),
                CallbackQueryHandler(restart_tour_callback, pattern=r"^restart_tour$")
            ],
            TOUR_CAPTAIN: [
                CallbackQueryHandler(premium_add_pool_callback, pattern=r"^premium_add_pool$"),
                CallbackQueryHandler(tour_captain_callback, pattern=r"^pick_captain_\d+$"),
                CallbackQueryHandler(restart_tour_callback, pattern=r"^restart_tour$"),
                MessageHandler(filters.ALL, tour_captain)
            ],
        },
        fallbacks=[],
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=True,
        name="tour_conv",
        persistent=False,
    )
    app.add_handler(tour_conv)
    # Глобальный обработчик для кнопки "Пересобрать состав"
    app.add_handler(CallbackQueryHandler(restart_tour_callback, pattern=r"^restart_tour$"))
    # Глобальные колбэки челленджа
    app.add_handler(CallbackQueryHandler(challenge_open_callback, pattern=r"^challenge_open_\d+$"))
    app.add_handler(CallbackQueryHandler(challenge_info_callback, pattern=r"^challenge_info_\d+$"))
    app.add_handler(CallbackQueryHandler(challenge_build_callback, pattern=r"^challenge_build_\d+$"))
    app.add_handler(CallbackQueryHandler(challenge_level_callback, pattern=r"^challenge_level_(50|100|500)$"))
    app.add_handler(CallbackQueryHandler(challenge_pick_pos_callback, pattern=r"^challenge_pick_pos_.*$"))
    app.add_handler(CallbackQueryHandler(challenge_pick_player_callback, pattern=r"^challenge_pick_player_\d+$"))
    app.add_handler(CallbackQueryHandler(challenge_cancel_callback, pattern=r"^challenge_cancel$"))
    app.add_handler(CallbackQueryHandler(challenge_reshuffle_callback, pattern=r"^challenge_reshuffle$"))
    app.add_handler(CallbackQueryHandler(referral_limit_decision_callback, pattern=r"^ref_limit:"))
    # Обработчик ввода названия команды для челленджа
    # Do not block other handlers (e.g., admin conversations) when catching free-text
    # for challenge team input. This prevents it from swallowing messages intended
    # for ConversationHandlers like /create_tour_full state machine.
    # Place in a later group so conversation handlers process text first
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, challenge_team_input, block=False), group=1)

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

    app.add_handler(CommandHandler('list_players', list_players))
    app.add_handler(CommandHandler('find_player', find_player))
    app.add_handler(CommandHandler('remove_player', remove_player))

    change_player_price_command = ChangePlayerPriceCommand()
    change_player_price_conv = change_player_price_command.build_handler()
    app.add_handler(change_player_price_conv)

    check_channel_command = CheckChannelCommand()
    check_channel_conv = check_channel_command.build_handler()
    app.add_handler(check_channel_conv)

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
    # app.add_handler(create_tour_full_conv)
    # Fixed /create_tour_full with UTF-8 prompts
    create_tour_full_conv_fixed = ConversationHandler(
        entry_points=[CommandHandler('create_tour_full', ctff_start)],
        states={
            FCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ctff_name)],
            FCT_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, ctff_start_date)],
            FCT_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ctff_deadline)],
            FCT_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, ctff_end_date)],
            FCT_IMAGE: [MessageHandler(filters.PHOTO, ctff_photo)],
            FCT_ROSTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ctff_roster)],
        },
        fallbacks=[CommandHandler('cancel', ctff_cancel)],
        name='create_tour_full_conv_fixed',
        allow_reentry=True,
    )
    app.add_handler(create_tour_full_conv_fixed)
    
    app.add_handler(CommandHandler('list_tours', list_tours))
    app.add_handler(CommandHandler('activate_tour', activate_tour))

    # Установка команд для пользователей и админа
    user_commands = [
        BotCommand("start", "Регистрация и приветствие"),
        BotCommand("tour", "Показать состав игроков на тур"),
        BotCommand("hc", "Показать баланс HC"),
        BotCommand("subscribe", "Оформить подписку"),
        BotCommand("rules", "Правила сборки составов"),
        BotCommand("shop", "Магазин призов"),
    ]
    # Ensure referral command is present in the menu
    user_commands.insert(3, BotCommand("referral", "получить реферальную ссылку"))
    admin_commands = user_commands + [
        BotCommand("show_users", "Список пользователей и подписок (админ)"),
        BotCommand("send_tour_image", "Разослать изображение тура (админ)"),
        BotCommand("addhc", "Начислить HC пользователю (админ)"),
        BotCommand("send_results", "Разослать результаты тура (админ)"),
        BotCommand("broadcast_subscribers", "Рассылка подписчикам (админ)"),
        BotCommand("message_user", "Сообщение пользователю (админ)"),
        BotCommand("change_player_price", "Изменить стоимость игроков (админ)"),
    ]

    # Установить команды для всех пользователей
    # await здесь нельзя, переносим в post_init

    # Запуск приложения
    app.add_handler(CommandHandler('start', start))
    # Убрано: отдельная регистрация /tour для сборки. Теперь /tour показывает список туров.
    app.add_handler(CommandHandler('hc', hc))
    app.add_handler(CommandHandler('rules', rules))
    app.add_handler(CommandHandler('shop', shop))
    app.run_polling()















