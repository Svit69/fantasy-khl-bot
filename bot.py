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
    restart_tour_callback, tour_captain_callback, rules, referral, subscribe, \
    premium_add_pool_callback, premium_team_input, premium_position_selected, \
    challenge_command, challenge_level_callback, \
    challenge_open_callback, challenge_info_callback, challenge_build_callback, \
    challenge_pick_pos_callback, challenge_team_input, challenge_pick_player_callback, \
    challenge_cancel_callback, challenge_reshuffle_callback, \
    tours, tour_open_callback, tour_build_callback
from handlers.user_handlers import shop, shop_item_callback
from handlers.admin_handlers import addhc, send_results, show_users
from handlers.admin_handlers import list_challenges, delete_challenge_cmd
from handlers.admin_handlers import (
    send_challenge_image_start,
    challenge_input_start_date,
    challenge_input_deadline,
    challenge_input_end_date,
    send_challenge_image_photo,
    send_challenge_image_cancel,
    CHALLENGE_START,
    CHALLENGE_DEADLINE,
    CHALLENGE_END,
    CHALLENGE_WAIT_IMAGE,
)
from handlers.admin_handlers import (
    add_player_start, add_player_name, add_player_position, add_player_club,
    add_player_nation, add_player_age, add_player_price, add_player_cancel, list_players, find_player,
    remove_player, edit_player_start, edit_player_name, edit_player_position, edit_player_club,
    edit_player_nation, edit_player_age, edit_player_price, edit_player_cancel,
    set_tour_roster_start, set_tour_roster_process, get_tour_roster,
    set_budget_start, set_budget_process,
    create_tour_conv, create_tour_full_conv, list_tours, activate_tour
)
from handlers.admin_handlers import (
    add_image_shop_start, add_image_shop_text, add_image_shop_photo, add_image_shop_cancel,
    SHOP_TEXT_WAIT, SHOP_IMAGE_WAIT
)
from handlers.admin_handlers import (
    purge_tours_start, purge_tours_password, purge_tours_cancel, PURGE_WAIT_PASSWORD
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
        BotCommand("challenge", "Челлендж против редакции"),
        BotCommand("shop", "Магазин призов"),
    ]
    # Для меню админа показываем только одну команду справки
    admin_commands = user_commands + [
        BotCommand("admin_help", "Справка по админ-командам"),
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
    from db import init_payments_table, init_referrals_table
    init_payments_table()
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
        asyncio.create_task(utils.poll_yookassa_payments(app.bot, 60))
        # Запускаем напоминания о подписке (каждый час)
        asyncio.create_task(utils.poll_subscription_reminders(app.bot, 3600))

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
            "• /addhc — начислить HC пользователю \n\n"
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
            "• /remove_player — удалить игрока\n\n"
            "<b>Управление челленджами:</b>\n"
            "• /list_challenges — список челленджей\n"
            "• /delete_challenge &lt;id&gt; — удалить челлендж по id\n"
            "• /send_challenge_image — зарегистрировать челлендж (даты + картинка)\n\n"
            "<b>Магазин:</b>\n"
            "• /add_image_shop — задать текст и изображение магазина (диалог)\n"
        )
        try:
            await update.message.reply_text(text, parse_mode='HTML')
        except Exception:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode='HTML')

    app.add_handler(CommandHandler('admin_help', admin_help))

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
    # Список туров и колбэки
    app.add_handler(CommandHandler('tours', tours))
    app.add_handler(CommandHandler('tour', tours))  # для совместимости и удобства
    app.add_handler(CallbackQueryHandler(tour_open_callback, pattern=r"^tour_open_\d+$"))
    app.add_handler(CommandHandler('addhc', addhc))
    app.add_handler(CommandHandler('send_results', send_results))
    app.add_handler(CommandHandler('list_challenges', list_challenges))
    app.add_handler(CommandHandler('delete_challenge', delete_challenge_cmd))
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
    # Обработчик ввода названия команды для челленджа
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, challenge_team_input))

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
    app.add_handler(create_tour_full_conv)
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
    # Убрано: отдельная регистрация /tour для сборки. Теперь /tour показывает список туров.
    app.add_handler(CommandHandler('hc', hc))
    app.add_handler(CommandHandler('rules', rules))
    app.add_handler(CommandHandler('shop', shop))
    app.run_polling()



