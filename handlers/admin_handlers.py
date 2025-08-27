from telegram import Update, InputFile
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from config import ADMIN_ID
import db
import os
import json
import logging
from utils import is_admin, send_message_to_users, IMAGES_DIR, TOUR_IMAGE_PATH_FILE, CHALLENGE_IMAGE_PATH_FILE, logger
from telegram import Update, Bot
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler
import asyncio

# --- Добавление игрока ---
ADD_NAME, ADD_POSITION, ADD_CLUB, ADD_NATION, ADD_AGE, ADD_PRICE = range(6)

# --- Редактирование игрока ---
EDIT_NAME, EDIT_POSITION, EDIT_CLUB, EDIT_NATION, EDIT_AGE, EDIT_PRICE = range(6, 12)

# (зарезервировано для будущих констант состояний 12-13)

# --- Магазин: состояния диалога ---
SHOP_TEXT_WAIT = 30
SHOP_IMAGE_WAIT = 31

async def add_image_shop_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text("Отправьте текст описания магазина:")
    return SHOP_TEXT_WAIT

async def add_image_shop_text(update, context):
    text = (update.message.text or '').strip()
    try:
        db.update_shop_text(text)
        context.user_data['shop_text'] = text
    except Exception as e:
        await update.message.reply_text(f"Ошибка сохранения текста: {e}")
        return ConversationHandler.END
    await update.message.reply_text("Теперь отправьте одно фото магазина в следующем сообщении.")
    return SHOP_IMAGE_WAIT

async def add_image_shop_photo(update, context):
    if not update.message or not update.message.photo:
        await update.message.reply_text("Пожалуйста, отправьте именно фото.")
        return SHOP_IMAGE_WAIT
    try:
        photo = update.message.photo[-1]
        file_id = photo.file_id
        tg_file = await photo.get_file()
        os.makedirs(IMAGES_DIR, exist_ok=True)
        filename = 'shop.jpg'
        file_path = os.path.join(IMAGES_DIR, filename)
        # попытка универсальной загрузки для PTB v20
        try:
            await tg_file.download_to_drive(file_path)
        except Exception:
            await tg_file.download(custom_path=file_path)
        db.update_shop_image(filename, file_id)
        await update.message.reply_text("Готово. Магазин обновлён.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка сохранения фото: {e}")
    return ConversationHandler.END

async def add_image_shop_cancel(update, context):
    await update.message.reply_text("Обновление магазина отменено.")
    return ConversationHandler.END

# --- Удаление подписок (запароленные команды) ---
DEL_SUB_WAIT_PASSWORD = 10010
DEL_SUB_WAIT_USERNAME = 10011

async def delete_sub_by_username_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Команда доступна только администратору.")
        return ConversationHandler.END
    await update.message.reply_text("Введите пароль для удаления подписки пользователя:")
    return DEL_SUB_WAIT_PASSWORD

async def delete_sub_by_username_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pw = (update.message.text or '').strip()
    checker = _get_purge_password_checker()
    if not checker(pw):
        await update.message.reply_text("Неверный пароль. Отмена.")
        return ConversationHandler.END
    await update.message.reply_text("Введите @username пользователя (без пробелов):")
    return DEL_SUB_WAIT_USERNAME

async def delete_sub_by_username_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = (update.message.text or '').strip()
    if username.startswith('@'):
        username = username[1:]
    try:
        row = db.get_user_by_username(username)
        if not row:
            await update.message.reply_text("Пользователь не найден.")
            return ConversationHandler.END
        user_id = row[0] if isinstance(row, tuple) else row['telegram_id'] if isinstance(row, dict) else row[0]
        deleted = db.delete_subscription_by_user_id(user_id)
        await update.message.reply_text(f"Удалено подписок: {deleted} у пользователя @{username}.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
    return ConversationHandler.END

async def delete_sub_by_username_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END

PURGE_SUBS_WAIT_PASSWORD = 10020

async def purge_subscriptions_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Команда доступна только администратору.")
        return ConversationHandler.END
    await update.message.reply_text("Введите пароль для подтверждения удаления ВСЕХ подписок:")
    return PURGE_SUBS_WAIT_PASSWORD

async def purge_subscriptions_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pw = (update.message.text or '').strip()
    checker = _get_purge_password_checker()
    if not checker(pw):
        await update.message.reply_text("Неверный пароль. Отмена.")
        return ConversationHandler.END
    try:
        deleted = db.purge_all_subscriptions()
        await update.message.reply_text(f"Удалено подписок: {deleted}.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка удаления: {e}")
    return ConversationHandler.END

# --- Удаление ОДНОГО тура по id (запароленная команда) ---
DEL_TOUR_WAIT_PASSWORD = 10030
DEL_TOUR_WAIT_ID = 10031

async def delete_tour_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Команда доступна только администратору.")
        return ConversationHandler.END
    await update.message.reply_text("Введите пароль для удаления ТУРА по id:")
    return DEL_TOUR_WAIT_PASSWORD

async def delete_tour_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pw = (update.message.text or '').strip()
    checker = _get_purge_password_checker()
    if not checker(pw):
        await update.message.reply_text("Неверный пароль. Отмена.")
        return ConversationHandler.END
    await update.message.reply_text("Введите id тура (целое число):")
    return DEL_TOUR_WAIT_ID

async def delete_tour_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (update.message.text or '').strip()
    if not txt.isdigit():
        await update.message.reply_text("Нужно число. Отменено.")
        return ConversationHandler.END
    tour_id = int(txt)
    try:
        deleted = db.delete_tour_by_id(tour_id)
        if deleted:
            await update.message.reply_text(f"Тур #{tour_id} удалён. Связанные данные очищены.")
        else:
            await update.message.reply_text(f"Тур #{tour_id} не найден.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка удаления: {e}")
    return ConversationHandler.END

async def delete_tour_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END
# --- PURGE TOURS (запароленная команда) ---
PURGE_WAIT_PASSWORD = 9991

def _get_purge_password_checker():
    """Возвращает функцию checker(pw:str)->bool, не раскрывая пароль в коде.
    Проверяется сначала переменная окружения PURGE_TOURS_PASSWORD_HASH (sha256),
    иначе PURGE_TOURS_PASSWORD (plain)."""
    import hashlib
    env_hash = os.getenv('PURGE_TOURS_PASSWORD_HASH', '').strip()
    env_plain = os.getenv('PURGE_TOURS_PASSWORD', '').strip()
    if env_hash:
        def check(pw: str) -> bool:
            try:
                return hashlib.sha256((pw or '').encode('utf-8')).hexdigest() == env_hash
            except Exception:
                return False
        return check
    else:
        secret = env_plain
        def check(pw: str) -> bool:
            return (pw or '') == secret and secret != ''
        return check

async def purge_tours_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from utils import is_admin
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Команда доступна только администратору.")
        return ConversationHandler.END
    await update.message.reply_text("Введите пароль для подтверждения удаления ВСЕХ туров:")
    return PURGE_WAIT_PASSWORD

async def purge_tours_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pw = (update.message.text or '').strip()
    checker = _get_purge_password_checker()
    if not checker(pw):
        await update.message.reply_text("Неверный пароль. Отмена.")
        return ConversationHandler.END
    try:
        deleted = db.purge_all_tours()
        await update.message.reply_text(f"Удалено туров: {deleted}. Составы и связанные данные также очищены.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка удаления: {e}")
    return ConversationHandler.END

async def purge_tours_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END

async def add_image_shop_cancel(update, context):
    await update.message.reply_text("Обновление магазина отменено.")
    return ConversationHandler.END

# --- Добавление игрока ---
async def add_player_start(update, context):
    logger.info("add_player_start called")
    if not await admin_only(update, context):
        logger.warning("Admin check failed in add_player_start")
        return ConversationHandler.END
    logger.info("Sending name prompt")
    await update.message.reply_text("Введите имя и фамилию игрока:")
    logger.info(f"Returning ADD_NAME state: {ADD_NAME}")
    return ADD_NAME

async def add_player_name(update, context):
    try:
        logger.info(f"add_player_name called with text: {update.message.text}")
        if not update.message or not update.message.text or not update.message.text.strip():
            await update.message.reply_text("Пожалуйста, введите корректное имя игрока.")
            return ADD_NAME
            
        context.user_data['name'] = update.message.text.strip()
        logger.info(f"Set name to: {context.user_data['name']}")
        logger.info(f"Sending position prompt, will return ADD_POSITION: {ADD_POSITION}")
        
        await update.message.reply_text("Введите позицию (нападающий/защитник/вратарь):")
        return ADD_POSITION
        
    except Exception as e:
        logger.error(f"Error in add_player_name: {str(e)}", exc_info=True)
        if update and update.message:
            await update.message.reply_text("Произошла ошибка при обработке имени игрока. Пожалуйста, попробуйте еще раз.")
        return ADD_NAME  # Возвращаемся к вводу имени

async def add_player_position(update, context):
    context.user_data['position'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите клуб:")
    return ADD_CLUB

async def add_player_club(update, context):
    context.user_data['club'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите нацию:")
    return ADD_NATION

async def add_player_nation(update, context):
    context.user_data['nation'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите возраст (число):")
    return ADD_AGE

async def add_player_age(update, context):
    context.user_data['age'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите стоимость (HC, число):")
    return ADD_PRICE

async def add_player_price(update, context):
    try:
        name = context.user_data.get('name', '')
        position = context.user_data.get('position', '')
        club = context.user_data.get('club', '')
        nation = context.user_data.get('nation', '')
        age = int(context.user_data.get('age', '0'))
        price = int((update.message.text or '0').strip())
        db.add_player(name, position, club, nation, age, price)
        await update.message.reply_text("Игрок добавлен!")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при добавлении: {e}")
    return ConversationHandler.END

async def add_player_cancel(update, context):
    await update.message.reply_text("Добавление отменено.")
    return ConversationHandler.END

# --- Список / поиск / удаление игроков ---
async def list_players(update, context):
    if not await admin_only(update, context):
        return
    try:
        players = db.get_all_players()
    except Exception as e:
        await update.message.reply_text(f"Ошибка получения списка игроков: {e}")
        return
    if not players:
        await update.message.reply_text("Список игроков пуст.")
        return
    msg = "\n".join([
        f"{p[0]}. {p[1]} | {p[2]} | {p[3]} | {p[4]} | {p[5]} лет | {p[6]} HC" for p in players
    ])
    for i in range(0, len(msg), 3500):
        await update.message.reply_text(msg[i:i+3500])

async def find_player(update, context):
    if not await admin_only(update, context):
        return
    if not context.args or not str(context.args[0]).isdigit():
        await update.message.reply_text("Использование: /find_player <id>")
        return
    player_id = int(context.args[0])
    player = db.get_player_by_id(player_id)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    msg = f"{player[0]}. {player[1]} | {player[2]} | {player[3]} | {player[4]} | {player[5]} лет | {player[6]} HC"
    await update.message.reply_text(msg)

async def remove_player(update, context):
    if not await admin_only(update, context):
        return
    if not context.args or not str(context.args[0]).isdigit():
        await update.message.reply_text("Использование: /remove_player <id>")
        return
    player_id = int(context.args[0])
    player = db.get_player_by_id(player_id)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    try:
        if db.remove_player(player_id):
            await update.message.reply_text(f"Игрок {player[1]} (ID: {player_id}) удален.")
        else:
            await update.message.reply_text("Ошибка при удалении игрока.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при удалении игрока: {e}")

# --- Редактирование игрока ---
async def edit_player_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    if not context.args or not str(context.args[0]).isdigit():
        await update.message.reply_text("Использование: /edit_player <id>")
        return ConversationHandler.END
    player_id = int(context.args[0])
    player = db.get_player_by_id(player_id)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return ConversationHandler.END
    context.user_data['edit_player_id'] = player_id
    await update.message.reply_text("Введите новое имя и фамилию игрока:")
    return EDIT_NAME

async def edit_player_name(update, context):
    context.user_data['edit_name'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите новую позицию (нападающий/защитник/вратарь):")
    return EDIT_POSITION

async def edit_player_position(update, context):
    context.user_data['edit_position'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите новый клуб:")
    return EDIT_CLUB

async def edit_player_club(update, context):
    context.user_data['edit_club'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите новую нацию:")
    return EDIT_NATION

async def edit_player_nation(update, context):
    context.user_data['edit_nation'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите новый возраст (число):")
    return EDIT_AGE

async def edit_player_age(update, context):
    context.user_data['edit_age'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите новую стоимость (HC, число):")
    return EDIT_PRICE

async def edit_player_price(update, context):
    try:
        player_id = int(context.user_data.get('edit_player_id'))
        name = context.user_data.get('edit_name', '')
        position = context.user_data.get('edit_position', '')
        club = context.user_data.get('edit_club', '')
        nation = context.user_data.get('edit_nation', '')
        age = int(context.user_data.get('edit_age', '0'))
        price = int((update.message.text or '0').strip())
        ok = db.update_player(player_id, name, position, club, nation, age, price)
        if ok:
            await update.message.reply_text("Игрок успешно обновлён!")
        else:
            await update.message.reply_text("Не удалось обновить игрока.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при обновлении: {e}")
    finally:
        for k in ('edit_player_id','edit_name','edit_position','edit_club','edit_nation','edit_age'):
            context.user_data.pop(k, None)
    return ConversationHandler.END

async def edit_player_cancel(update, context):
    await update.message.reply_text("Редактирование отменено.")
    return ConversationHandler.END

# --- Тур: добавить и вывести состав ---
SET_BUDGET_WAIT = 21

async def set_budget_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text("Please send the new budget as a positive integer (e.g., 180):")
    return SET_BUDGET_WAIT

async def set_budget_process(update, context):
    text = update.message.text.strip()
    try:
        value = int(text)
        if value <= 0:
            await update.message.reply_text("Budget must be a positive integer!")
            return ConversationHandler.END
        db.set_budget(value)
        await update.message.reply_text(f"Budget set successfully: {value}")
    except Exception:
        await update.message.reply_text("Error! Please send a positive integer.")
    return ConversationHandler.END

SET_TOUR_ROSTER_WAIT = 20

async def set_tour_roster_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text(
        "Пожалуйста, отправьте список игроков на тур в формате:\n50: 28, 1, ...\n40: ... и т.д. (ровно 20 игроков)"
    )
    return SET_TOUR_ROSTER_WAIT

async def set_tour_roster_process(update, context):
    text = update.message.text
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    ids = []
    try:
        for line in lines:
            if ':' not in line:
                await update.message.reply_text(f"Неверный формат строки: {line}")
                return ConversationHandler.END
            cost_str, ids_str = line.split(':', 1)
            cost = int(cost_str.strip())
            id_list = [int(x.strip()) for x in ids_str.split(',') if x.strip()]
            for player_id in id_list:
                ids.append((cost, player_id))
    except Exception as e:
        await update.message.reply_text(f"Ошибка разбора: {e}")
        return ConversationHandler.END
    if len(ids) != 20:
        await update.message.reply_text(f"Ошибка: должно быть ровно 20 игроков, а не {len(ids)}")
        return ConversationHandler.END
    # Проверка, что все игроки существуют
    for cost, player_id in ids:
        player = db.get_player_by_id(player_id)
        if not player:
            await update.message.reply_text(f"Игрок с id {player_id} не найден!")
            return ConversationHandler.END
    db.clear_tour_roster()
    for cost, player_id in ids:
        db.add_tour_roster_entry(player_id, cost)
    await update.message.reply_text("Состав на тур успешно сохранён!")
    return ConversationHandler.END

async def get_tour_roster(update, context):
    if not await admin_only(update, context):
        return
    roster = db.get_tour_roster_with_player_info()
    if not roster:
        await update.message.reply_text("Состав на тур не задан.")
        return
    msg = "Состав на тур:\n"
    for cost, pid, name, pos, club, nation, age, price in roster:
        msg += f"{cost}: {pid}. {name} | {pos} | {club} | {nation} | {age} лет | {price} HC\n"
    await update.message.reply_text(msg)

# --- Список пользователей и подписок ---
async def show_users(update, context):
    if not await admin_only(update, context):
        return
    import datetime
    # Получаем всех пользователей и их подписки
    with db.closing(db.sqlite3.connect(db.DB_NAME)) as conn:
        users = conn.execute('SELECT telegram_id, username, name FROM users').fetchall()
        subs = {row[0]: row[1] for row in conn.execute('SELECT user_id, paid_until FROM subscriptions').fetchall()}
    now = datetime.datetime.utcnow()
    lines = []
    for user_id, username, name in users:
        paid_until = subs.get(user_id)
        active = False
        if paid_until:
            try:
                dt = datetime.datetime.fromisoformat(str(paid_until))
                active = dt > now
            except Exception:
                active = False
        status = '✅ подписка активна' if active else '❌ нет подписки'
        lines.append(f"{user_id} | {username or '-'} | {name or '-'} | {status}")
    if not lines:
        await update.message.reply_text("Нет пользователей.")
    else:
        msg = 'Пользователи и подписки:\n\n' + '\n'.join(lines)
        for i in range(0, len(msg), 4000):
            await update.message.reply_text(msg[i:i+4000])

# --- Челлендж: вывод составов по id ---
async def challenge_rosters_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ-команда: /challenge_rosters <challenge_id>
    Показывает список пользователей, их статус заявки, ставку и выбранных игроков (нападающий/защитник/вратарь).
    """
    if not await admin_only(update, context):
        return
    # Разбор аргумента
    challenge_id = None
    try:
        if context.args and len(context.args) >= 1:
            challenge_id = int(context.args[0])
    except Exception:
        challenge_id = None
    if not challenge_id:
        await update.message.reply_text("Использование: /challenge_rosters <challenge_id>")
        return

    # Получаем записи заявок с юзерами
    try:
        with db.closing(db.sqlite3.connect(db.DB_NAME)) as conn:
            conn.row_factory = db.sqlite3.Row
            rows = conn.execute(
                '''
                SELECT ce.user_id,
                       u.username,
                       u.name,
                       ce.stake,
                       ce.forward_id,
                       ce.defender_id,
                       ce.goalie_id,
                       ce.status,
                       ce.created_at
                FROM challenge_entries AS ce
                LEFT JOIN users AS u ON u.telegram_id = ce.user_id
                WHERE ce.challenge_id = ?
                ORDER BY ce.created_at DESC
                ''', (challenge_id,)
            ).fetchall()
    except Exception as e:
        await update.message.reply_text(f"Ошибка БД: {e}")
        return

    if not rows:
        await update.message.reply_text(f"Для челленджа #{challenge_id} заявки не найдены.")
        return

    def name_club(pid):
        if not pid:
            return "—"
        try:
            p = db.get_player_by_id(int(pid))
            if p:
                return f"{p[1]} ({p[3]})"
        except Exception:
            pass
        return str(pid)

    # Формируем сообщение с разбиением на части
    parts = []
    cur_lines = [f"Составы участников челленджа #{challenge_id}:", ""]
    for r in rows:
        uname = ("@" + (r["username"] or "").strip()) if r["username"] else "—"
        name = r["name"] or "—"
        status = (r["status"] or "").lower()
        stake = r["stake"] or 0
        fwd = name_club(r["forward_id"]) if r["forward_id"] else "—"
        dfd = name_club(r["defender_id"]) if r["defender_id"] else "—"
        gk = name_club(r["goalie_id"]) if r["goalie_id"] else "—"

        # Статус значком
        status_icon = {
            'in_progress': '🟡 in_progress',
            'completed': '🟢 completed',
            'canceled': '⚪ canceled',
            'refunded': '⚪ refunded',
        }.get(status, status or '—')

        cur_lines.append(f"• {uname} | {name} | {status_icon} | Ставка: {stake} HC")
        cur_lines.append(f"Нападающий: {fwd}")
        cur_lines.append(f"Защитник: {dfd}")
        cur_lines.append(f"Вратарь: {gk}")
        cur_lines.append("")

        joined = "\n".join(cur_lines)
        if len(joined) > 3500:  # запас до лимита Telegram в 4096
            parts.append(joined)
            cur_lines = []
    if cur_lines:
        parts.append("\n".join(cur_lines))

    for part in parts:
        try:
            await update.message.reply_text(part)
        except Exception:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=part)

async def admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id if update.effective_user else None
    if not is_admin(user_id):
        await update.message.reply_text('Нет доступа')
        return False
    return True

async def send_tour_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Сценарий:
    1. Админ отправляет /send_tour_image — бот просит прикрепить картинку.
    2. Админ отправляет фото — бот сохраняет, сообщает об успехе.
    """
    if not await admin_only(update, context):
        logger.info(f"Пользователь {update.effective_user.id} не админ, доступ запрещён.")
        return

    # Если команда вызвана без фото, запрашиваем фото


    if not update.message.photo:
        context.user_data['awaiting_tour_image'] = True
        chat_id = update.effective_chat.id
        debug_info = f"[DEBUG] /send_tour_image chat_id: {chat_id}, user_data: {context.user_data}"
        await update.message.reply_text('Пожалуйста, прикрепите картинку следующим сообщением.')
        await update.message.reply_text(debug_info)
        logger.info(f"[DEBUG] Ожидание картинки от админа {update.effective_user.id}, user_data: {context.user_data}")
        return

    # Если фото пришло после запроса


    if context.user_data.get('awaiting_tour_image'):
        logger.info(f"[DEBUG] Получено фото, user_data: {context.user_data}")
        try:
            photo = update.message.photo[-1]
            file = await photo.get_file()
            filename = f"tour_{photo.file_unique_id}.jpg"
            path = os.path.join(IMAGES_DIR, filename)
            await file.download_to_drive(path)
            with open(TOUR_IMAGE_PATH_FILE, 'w') as f:
                f.write(filename)
            context.user_data['awaiting_tour_image'] = False
            await update.message.reply_text(f'✅ Картинка принята и сохранена как `{filename}`. Она будет разослана пользователям при команде /tour.')
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f'[DEBUG] Фото обработано, сохранено как {filename}')
            logger.info(f"Картинка тура сохранена: {path} (от {update.effective_user.id})")
        except Exception as e:
            logger.error(f'Ошибка при сохранении картинки тура: {e}')
            await update.message.reply_text(f'Ошибка при сохранении картинки: {e}')
        return

    # Если фото пришло без запроса
    await update.message.reply_text('Сначала отправьте команду /send_tour_image, затем фото.')
    logger.info(f"Фото получено без запроса от {update.effective_user.id}")

async def process_tour_image_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        filename = f"tour_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        await file.download_to_drive(path)
        with open(TOUR_IMAGE_PATH_FILE, 'w') as f:
            f.write(filename)
        await update.message.reply_text(f'✅ Картинка принята и сохранена как `{filename}`. Она будет разослана пользователям при команде /tour.')
        logger.info(f"Картинка тура сохранена: {path} (от {update.effective_user.id})")
    except Exception as e:
        logger.error(f'Ошибка при сохранении картинки тура: {e}')
        await update.message.reply_text(f'Ошибка при сохранении картинки: {e}')

async def addhc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

# --- Регистрация челленджа (+ загрузка картинки) ---
CHALLENGE_START = 31
CHALLENGE_DEADLINE = 32
CHALLENGE_END = 33
CHALLENGE_WAIT_IMAGE = 34

def _parse_iso(dt_str: str):
    import datetime
    try:
        return datetime.datetime.fromisoformat(dt_str)
    except Exception:
        return None

async def send_challenge_image_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return ConversationHandler.END
    context.user_data.pop('challenge_start', None)
    context.user_data.pop('challenge_deadline', None)
    context.user_data.pop('challenge_end', None)
    await update.message.reply_text(
        'Создание челленджа. Введите дату СТАРТА в формате ISO, например: 2025-08-08T12:00:00'
    )
    return CHALLENGE_START

async def challenge_input_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    dt = _parse_iso(text)
    if not dt:
        await update.message.reply_text('Некорректная дата. Повторите в формате ISO: 2025-08-08T12:00:00')
        return CHALLENGE_START
    context.user_data['challenge_start'] = text
    await update.message.reply_text('Введите ДЕДЛАЙН (крайний срок выбора состава) в формате ISO: 2025-08-09T18:00:00')
    return CHALLENGE_DEADLINE

async def challenge_input_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    dt = _parse_iso(text)
    if not dt:
        await update.message.reply_text('Некорректная дата. Повторите дедлайн в формате ISO.')
        return CHALLENGE_DEADLINE
    # Проверим порядок
    sd = _parse_iso(context.user_data.get('challenge_start', ''))
    if not sd or not (sd < dt):
        await update.message.reply_text('Дедлайн должен быть ПОСЛЕ даты старта. Повторите ввод дедлайна.')
        return CHALLENGE_DEADLINE
    context.user_data['challenge_deadline'] = text
    await update.message.reply_text('Введите ДАТУ ОКОНЧАНИЯ игры в формате ISO: 2025-08-12T23:59:59')
    return CHALLENGE_END

async def challenge_input_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    dt = _parse_iso(text)
    if not dt:
        await update.message.reply_text('Некорректная дата. Повторите дату окончания в формате ISO.')
        return CHALLENGE_END
    sd = _parse_iso(context.user_data.get('challenge_start', ''))
    dl = _parse_iso(context.user_data.get('challenge_deadline', ''))
    if not sd or not dl or not (dl < dt):
        await update.message.reply_text('Дата окончания должна быть ПОСЛЕ дедлайна. Повторите дату окончания.')
        return CHALLENGE_END
    context.user_data['challenge_end'] = text
    await update.message.reply_text('Теперь пришлите КАРТИНКУ челленджа сообщением в чат.')
    return CHALLENGE_WAIT_IMAGE

async def send_challenge_image_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Сохраняем фото
        photo = update.message.photo[-1]
        file = await photo.get_file()
        filename = f"challenge_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        await file.download_to_drive(path)
        with open(CHALLENGE_IMAGE_PATH_FILE, 'w') as f:
            f.write(filename)

        # Регистрируем челлендж в БД
        start_date = context.user_data.get('challenge_start')
        deadline = context.user_data.get('challenge_deadline')
        end_date = context.user_data.get('challenge_end')
        image_file_id = getattr(photo, 'file_id', '') or ''
        ch_id = db.create_challenge(start_date, deadline, end_date, filename, image_file_id)

        await update.message.reply_text(
            f'✅ Челлендж зарегистрирован (id={ch_id}). Картинка сохранена как `{filename}`.'
        )
        logger.info(f"Челлендж {ch_id} создан: {start_date} / {deadline} / {end_date}, image={path}")
    except Exception as e:
        logger.error(f'Ошибка при регистрации челленджа: {e}')
        await update.message.reply_text(f'Ошибка при регистрации челленджа: {e}')
    finally:
        # Очистим временные данные
        for k in ('challenge_start','challenge_deadline','challenge_end'):
            context.user_data.pop(k, None)
    return ConversationHandler.END

# --- Магазин: описание + картинка ---
SHOP_TEXT_WAIT = 41
SHOP_IMAGE_WAIT = 42

async def add_image_shop_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text(
        "Напишите текст описания магазина. Можете оформить аккуратно (обычный текст)."
    )
    return SHOP_TEXT_WAIT

async def add_image_shop_text(update, context):
    text = (update.message.text or '').strip()
    try:
        db.update_shop_text(text)
    except Exception:
        pass
    await update.message.reply_text("Теперь отправьте картинку магазина одним фото сообщением.")
    return SHOP_IMAGE_WAIT

async def add_image_shop_photo(update, context):
    if not update.message.photo:
        await update.message.reply_text("Пожалуйста, отправьте одно фото.")
        return SHOP_IMAGE_WAIT
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        filename = f"shop_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        await file.download_to_drive(path)
        # Сохраним file_id для быстрого повторного отправления
        db.update_shop_image(filename, photo.file_id)
        await update.message.reply_text("Готово. Магазин обновлён.")
        logger.info(f"Магазин обновлён: text set, image {filename}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении картинки магазина: {e}")
        await update.message.reply_text(f"Ошибка при сохранении картинки: {e}")
    return ConversationHandler.END

async def send_challenge_image_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text('Отменено.')
    except Exception:
        pass
    for k in ('challenge_start','challenge_deadline','challenge_end'):
        context.user_data.pop(k, None)
    return ConversationHandler.END

async def send_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

# --- Управление челленджами (список/удаление) ---
async def list_challenges(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_only(update, context):
        return
    try:
        rows = db.get_all_challenges()
        if not rows:
            await update.message.reply_text('В базе нет челленджей.')
            return
        lines = []
        for r in rows:
            # ожидаемые поля: id, start_date, deadline, end_date, image_filename, status[, image_file_id]
            ch_id = r[0]
            start_date = r[1]
            deadline = r[2]
            end_date = r[3]
            image_filename = r[4] if len(r) > 4 else ''
            status = r[5] if len(r) > 5 else ''
            lines.append(
                f"id={ch_id} | {status}\nstart: {start_date}\ndeadline: {deadline}\nend: {end_date}\nimage: {image_filename}\n—"
            )
        msg = "\n".join(lines)
        # Telegram ограничение на длину сообщения ~4096
        for i in range(0, len(msg), 3500):
            await update.message.reply_text(msg[i:i+3500])
    except Exception as e:
        await update.message.reply_text(f"Ошибка получения списка челленджей: {e}")

async def delete_challenge_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_only(update, context):
        return
    args = getattr(context, 'args', []) or []
    if not args or not args[0].isdigit():
        await update.message.reply_text('Использование: /delete_challenge <id>')
        return
    ch_id = int(args[0])
    try:
        deleted = db.delete_challenge(ch_id)
        if deleted:
            await update.message.reply_text(f'Челлендж id={ch_id} удалён.')
        else:
            await update.message.reply_text(f'Челлендж id={ch_id} не найден.')
    except Exception as e:
        await update.message.reply_text(f'Ошибка удаления челленджа: {e}')

# --- Управление турами (admin) ---
from telegram.ext import CommandHandler, MessageHandler, filters, ConversationHandler
import json

TOUR_NAME, TOUR_START, TOUR_DEADLINE, TOUR_END, TOUR_CONFIRM = range(100, 105)

# --- ЕДИНЫЙ ПАКЕТНЫЙ ДИАЛОГ СОЗДАНИЯ ТУРА ---
# Этапы: имя -> дата старта -> дедлайн -> окончание -> фото -> ростер -> финал
CT_NAME, CT_START, CT_DEADLINE, CT_END, CT_IMAGE, CT_ROSTER = range(200, 206)

async def create_tour_full_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    # Очистим временные данные диалога
    for k in ['ct_name', 'ct_start', 'ct_deadline', 'ct_end', 'ct_image_filename', 'ct_tour_id']:
        context.user_data.pop(k, None)
    await update.message.reply_text("Введите название тура:")
    return CT_NAME

async def create_tour_full_name(update, context):
    context.user_data['ct_name'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите дату старта тура (дд.мм.гг):")
    return CT_START

async def create_tour_full_start_date(update, context):
    context.user_data['ct_start'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите дедлайн (дд.мм.гг чч:мм):")
    return CT_DEADLINE

async def create_tour_full_deadline(update, context):
    context.user_data['ct_deadline'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите дату окончания тура (дд.мм.гг):")
    return CT_END

async def create_tour_full_end_date(update, context):
    context.user_data['ct_end'] = (update.message.text or '').strip()
    # Создаём тур сразу, чтобы получить id (автоинкремент)
    try:
        tour_id = db.create_tour(
            context.user_data['ct_name'],
            context.user_data['ct_start'],
            context.user_data['ct_deadline'],
            context.user_data['ct_end']
        )
        context.user_data['ct_tour_id'] = tour_id
    except Exception as e:
        await update.message.reply_text(f"Ошибка создания тура: {e}")
        return ConversationHandler.END
    await update.message.reply_text("Теперь отправьте одно фото для тура сообщением с фотографией.")
    return CT_IMAGE

async def create_tour_full_photo(update, context):
    if not update.message or not update.message.photo:
        await update.message.reply_text("Пожалуйста, отправьте именно фото.")
        return CT_IMAGE
    try:
        photo = update.message.photo[-1]
        tg_file = await photo.get_file()
        os.makedirs(IMAGES_DIR, exist_ok=True)
        filename = f"tour_{photo.file_unique_id}.jpg"
        file_path = os.path.join(IMAGES_DIR, filename)
        try:
            await tg_file.download_to_drive(file_path)
        except Exception:
            await tg_file.download(custom_path=file_path)
        # Сохраним "последнюю" картинку для показа в /tour
        try:
            with open(TOUR_IMAGE_PATH_FILE, 'w') as f:
                f.write(filename)
        except Exception:
            logger.warning("Failed to write TOUR_IMAGE_PATH_FILE", exc_info=True)
        context.user_data['ct_image_filename'] = filename
        # Привяжем изображение к созданному туру
        try:
            tour_id = context.user_data.get('ct_tour_id')
            if tour_id:
                db.update_tour_image(tour_id, filename, photo.file_id)
        except Exception:
            logger.warning("Failed to update tour image in DB", exc_info=True)
        await update.message.reply_text(
            "Фото сохранено. Теперь отправьте ростер в формате:\n"
            "50: 28, 1, ...\n40: ... и т.д. (ровно 20 игроков)"
        )
        return CT_ROSTER
    except Exception as e:
        await update.message.reply_text(f"Ошибка сохранения фото: {e}")
        return ConversationHandler.END

async def create_tour_full_roster(update, context):
    text = (update.message.text or '').strip()
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    pairs = []
    try:
        for line in lines:
            if ':' not in line:
                await update.message.reply_text(f"Неверный формат строки: {line}")
                return CT_ROSTER
            cost_str, ids_str = line.split(':', 1)
            cost = int(cost_str.strip())
            id_list = [int(x.strip()) for x in ids_str.split(',') if x.strip()]
            for pid in id_list:
                pairs.append((cost, pid))
    except Exception as e:
        await update.message.reply_text(f"Ошибка разбора: {e}")
        return CT_ROSTER
    if len(pairs) != 20:
        await update.message.reply_text(f"Ошибка: должно быть ровно 20 игроков, а не {len(pairs)}. Повторите ввод.")
        return CT_ROSTER
    # Проверим, что игроки существуют
    for cost, pid in pairs:
        player = db.get_player_by_id(pid)
        if not player:
            await update.message.reply_text(f"Игрок с id {pid} не найден! Повторите ввод.")
            return CT_ROSTER
    # Сохраняем ростер на конкретный тур в таблицу tour_players
    try:
        tour_id = context.user_data.get('ct_tour_id')
        if tour_id:
            db.clear_tour_players(tour_id)
            for cost, pid in pairs:
                db.add_tour_player(tour_id, pid, cost)
            # Обратная совместимость: также заполним старую таблицу tour_roster,
            # т.к. текущая пользовательская логика читает её.
            try:
                db.clear_tour_roster()
                for cost, pid in pairs:
                    db.add_tour_roster_entry(pid, cost)
            except Exception:
                logger.warning("Failed to mirror roster into legacy tour_roster", exc_info=True)
        else:
            await update.message.reply_text("Внутренняя ошибка: tour_id отсутствует.")
            return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"Ошибка сохранения ростера: {e}")
        return ConversationHandler.END
    tour_id = context.user_data.get('ct_tour_id')
    name = context.user_data.get('ct_name')
    start = context.user_data.get('ct_start')
    deadline = context.user_data.get('ct_deadline')
    end = context.user_data.get('ct_end')
    await update.message.reply_text(
        "Тур создан успешно!\n"
        f"ID: {tour_id}\nНазвание: {name}\nСтарт: {start}\nДедлайн: {deadline}\nОкончание: {end}\n"
        f"Картинка: {context.user_data.get('ct_image_filename', '-')}. Ростер принят."
    )
    # Очистим временные данные
    for k in ['ct_name', 'ct_start', 'ct_deadline', 'ct_end', 'ct_image_filename', 'ct_tour_id']:
        context.user_data.pop(k, None)
    return ConversationHandler.END

async def create_tour_full_cancel(update, context):
    await update.message.reply_text("Создание тура отменено.")
    # Очистим временные данные
    for k in ['ct_name', 'ct_start', 'ct_deadline', 'ct_end', 'ct_image_filename', 'ct_tour_id']:
        context.user_data.pop(k, None)
    return ConversationHandler.END

create_tour_full_conv = ConversationHandler(
    entry_points=[CommandHandler("create_tour_full", create_tour_full_start)],
    states={
        CT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_full_name)],
        CT_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_full_start_date)],
        CT_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_full_deadline)],
        CT_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_full_end_date)],
        CT_IMAGE: [MessageHandler(filters.PHOTO, create_tour_full_photo)],
        CT_ROSTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_full_roster)],
    },
    fallbacks=[CommandHandler("cancel", create_tour_full_cancel)],
    per_chat=True, per_user=True, per_message=False, allow_reentry=True,
)

async def create_tour_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text("Введите название тура:")
    return TOUR_NAME

async def create_tour_name(update, context):
    context.user_data['tour_name'] = update.message.text.strip()
    await update.message.reply_text("Введите дату старта тура (дд.мм.гг):")
    return TOUR_START

async def create_tour_start_date(update, context):
    context.user_data['tour_start'] = update.message.text.strip()
    await update.message.reply_text("Введите дедлайн (дд.мм.гг чч:мм):")
    return TOUR_DEADLINE

async def create_tour_deadline(update, context):
    context.user_data['tour_deadline'] = update.message.text.strip()
    await update.message.reply_text("Введите дату окончания тура (дд.мм.гг):")
    return TOUR_END

async def create_tour_end_date(update, context):
    context.user_data['tour_end'] = update.message.text.strip()
    summary = (
        f"Название: {context.user_data['tour_name']}\n"
        f"Старт: {context.user_data['tour_start']}\n"
        f"Дедлайн: {context.user_data['tour_deadline']}\n"
        f"Окончание: {context.user_data['tour_end']}\n"
        "\nПодтвердить создание тура? (да/нет)"
    )
    await update.message.reply_text(summary)
    return TOUR_CONFIRM

async def create_tour_confirm(update, context):
    text = update.message.text.strip().lower()
    if text not in ("да", "нет"):
        await update.message.reply_text("Пожалуйста, напишите 'да' или 'нет'.")
        return TOUR_CONFIRM
    if text == "нет":
        await update.message.reply_text("Создание тура отменено.")
        return ConversationHandler.END
    db.create_tour(
        context.user_data['tour_name'],
        context.user_data['tour_start'],
        context.user_data['tour_deadline'],
        context.user_data['tour_end']
    )
    await update.message.reply_text("Тур успешно создан!")
    return ConversationHandler.END

async def create_tour_cancel(update, context):
    await update.message.reply_text("Создание тура отменено.")
    return ConversationHandler.END

create_tour_conv = ConversationHandler(
    entry_points=[CommandHandler("create_tour", create_tour_start)],
    states={
        TOUR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_name)],
        TOUR_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_start_date)],
        TOUR_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_deadline)],
        TOUR_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_end_date)],
        TOUR_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_confirm)],
    },
    fallbacks=[CommandHandler("cancel", create_tour_cancel)],
)

async def list_tours(update, context):
    if not await admin_only(update, context):
        return
    tours = db.get_all_tours()
    if not tours:
        await update.message.reply_text("Туров пока нет.")
        return
    msg = "Список туров:\n"
    for t in tours:
        winners = "-"
        try:
            winners_list = json.loads(t[6]) if t[6] else []
            if winners_list:
                winners = ", ".join(map(str, winners_list))
        except Exception:
            winners = t[6]
        msg += (
            f"\nID: {t[0]} | {t[1]}\n"
            f"Старт: {t[2]} | Дедлайн: {t[3]} | Окончание: {t[4]}\n"
            f"Статус: {t[5]} | Победители: {winners}\n"
        )
    await update.message.reply_text(msg)

# --- Push Notifications ---
SEND_PUSH = 100

async def send_push_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса отправки push-уведомления"""
    if not await admin_only(update, context):
        return ConversationHandler.END
        
    await update.message.reply_text(
        "✉️ Введите текст push-уведомления, которое будет отправлено всем пользователям бота:\n"
        "(Вы можете использовать HTML-разметку: <b>жирный</b>, <i>курсив</i>, <a href=\"URL\">ссылка</a>)\n\n"
        "Для отмены введите /cancel"
    )
    return SEND_PUSH

async def send_push_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка push-уведомления всем пользователям"""
    message_text = update.message.text
    users = db.get_all_users()
    
    if not users:
        await update.message.reply_text("❌ В базе данных нет пользователей.")
        return ConversationHandler.END
    
    sent_count = 0
    failed_count = 0
    
    progress_msg = await update.message.reply_text(f"🔄 Отправка уведомления {len(users)} пользователям...")
    
    for user in users:
        try:
            user_id = user[0] if isinstance(user, (tuple, list)) else user.get('telegram_id')
            if not user_id:
                continue
                
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            sent_count += 1
            
            # Не спамим слишком быстро, чтобы не получить ограничение от Telegram
            if sent_count % 20 == 0:
                await asyncio.sleep(1)
                await progress_msg.edit_text(f"🔄 Отправлено {sent_count} из {len(users)} уведомлений...")
                
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
            failed_count += 1
    
    await progress_msg.edit_text(
        f"✅ Рассылка завершена!\n"
        f"• Отправлено: {sent_count}\n"
        f"• Не удалось отправить: {failed_count}\n\n"
        f"Текст уведомления:\n{message_text}"
    )
    return ConversationHandler.END

async def send_push_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена отправки push-уведомления"""
    await update.message.reply_text("❌ Отправка уведомлений отменена.")
    return ConversationHandler.END

# Регистрация обработчика для команды /push
push_conv = ConversationHandler(
    entry_points=[CommandHandler("push", send_push_start)],
    states={
        SEND_PUSH: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, send_push_process),
            CommandHandler("cancel", send_push_cancel)
        ]
    },
    fallbacks=[CommandHandler("cancel", send_push_cancel)]
)

# --- Активация тура админом ---
async def activate_tour(update, context):
    if not await admin_only(update, context):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Использование: /activate_tour <id>")
        return
    tour_id = int(context.args[0])
    tours = db.get_all_tours()
    found = False
    for t in tours:
        if t[0] == tour_id:
            db.update_tour_status(tour_id, "активен")
            found = True
        elif t[5] == "активен":
            db.update_tour_status(t[0], "создан")
    if found:
        await update.message.reply_text(f"Тур {tour_id} активирован.")
    else:
        await update.message.reply_text(f"Тур с id {tour_id} не найден.")
