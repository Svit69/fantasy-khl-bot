from telegram import Update, InputFile
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
import db
import os
from utils import is_admin, send_message_to_users, IMAGES_DIR, TOUR_IMAGE_PATH_FILE, logger

# --- Добавление игрока ---
ADD_NAME, ADD_POSITION, ADD_CLUB, ADD_NATION, ADD_AGE, ADD_PRICE = range(6)

# --- Редактирование игрока ---
EDIT_NAME, EDIT_POSITION, EDIT_CLUB, EDIT_NATION, EDIT_AGE, EDIT_PRICE = range(6, 12)

async def add_player_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text("Введите имя и фамилию игрока:")
    return ADD_NAME

async def add_player_name(update, context):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Введите позицию (нападающий/защитник/вратарь):")
    return ADD_POSITION

async def add_player_position(update, context):
    context.user_data['position'] = update.message.text
    await update.message.reply_text("Введите клуб:")
    return ADD_CLUB

async def add_player_club(update, context):
    context.user_data['club'] = update.message.text
    await update.message.reply_text("Введите нацию:")
    return ADD_NATION

async def add_player_nation(update, context):
    context.user_data['nation'] = update.message.text
    await update.message.reply_text("Введите возраст:")
    return ADD_AGE

async def add_player_age(update, context):
    context.user_data['age'] = update.message.text
    await update.message.reply_text("Введите стоимость:")
    return ADD_PRICE

async def add_player_price(update, context):
    context.user_data['price'] = update.message.text
    db.add_player(
        context.user_data['name'],
        context.user_data['position'],
        context.user_data['club'],
        context.user_data['nation'],
        int(context.user_data['age']),
        int(context.user_data['price'])
    )
    await update.message.reply_text("Игрок добавлен!")
    return ConversationHandler.END

async def add_player_cancel(update, context):
    await update.message.reply_text("Добавление отменено.")
    return ConversationHandler.END

# --- Список игроков ---
async def list_players(update, context):
    if not await admin_only(update, context):
        return
    players = db.get_all_players()
    if not players:
        await update.message.reply_text("Список игроков пуст.")
        return
    msg = "\n".join([f"{p[0]}. {p[1]} | {p[2]} | {p[3]} | {p[4]} | {p[5]} лет | {p[6]} HC" for p in players])
    await update.message.reply_text(msg)

async def find_player(update, context):
    if not await admin_only(update, context):
        return
    if not context.args or not context.args[0].isdigit():
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
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Использование: /remove_player <id>")
        return
    player_id = int(context.args[0])
    player = db.get_player_by_id(player_id)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    
    if db.remove_player(player_id):
        await update.message.reply_text(f"Игрок {player[1]} (ID: {player_id}) удален.")
    else:
        await update.message.reply_text("Ошибка при удалении игрока.")

# --- Редактирование игрока ---
async def edit_player_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Использование: /edit_player <id>")
        return ConversationHandler.END
    
    player_id = int(context.args[0])
    player = db.get_player_by_id(player_id)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return ConversationHandler.END
    
    context.user_data['edit_player_id'] = player_id
    context.user_data['current_player'] = player
    
    msg = f"Редактирование игрока:\n{player[0]}. {player[1]} | {player[2]} | {player[3]} | {player[4]} | {player[5]} лет | {player[6]} HC\n\nВведите новое имя и фамилию игрока:"
    await update.message.reply_text(msg)
    return EDIT_NAME

async def edit_player_name(update, context):
    context.user_data['edit_name'] = update.message.text
    await update.message.reply_text("Введите новую позицию (нападающий/защитник/вратарь):")
    return EDIT_POSITION

async def edit_player_position(update, context):
    context.user_data['edit_position'] = update.message.text
    await update.message.reply_text("Введите новый клуб:")
    return EDIT_CLUB

async def edit_player_club(update, context):
    context.user_data['edit_club'] = update.message.text
    await update.message.reply_text("Введите новую нацию:")
    return EDIT_NATION

async def edit_player_nation(update, context):
    context.user_data['edit_nation'] = update.message.text
    await update.message.reply_text("Введите новый возраст:")
    return EDIT_AGE

async def edit_player_age(update, context):
    context.user_data['edit_age'] = update.message.text
    await update.message.reply_text("Введите новую стоимость:")
    return EDIT_PRICE

async def edit_player_price(update, context):
    context.user_data['edit_price'] = update.message.text
    
    player_id = context.user_data['edit_player_id']
    if db.update_player(
        player_id,
        context.user_data['edit_name'],
        context.user_data['edit_position'],
        context.user_data['edit_club'],
        context.user_data['edit_nation'],
        int(context.user_data['edit_age']),
        int(context.user_data['edit_price'])
    ):
        await update.message.reply_text("Игрок успешно обновлен!")
    else:
        await update.message.reply_text("Ошибка при обновлении игрока.")
    
    return ConversationHandler.END

async def edit_player_cancel(update, context):
    await update.message.reply_text("Редактирование отменено.")
    return ConversationHandler.END

# --- Тур: добавить и вывести состав ---
SET_BUDGET_WAIT = 21

async def установить_бюджет_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text("Пожалуйста, отправьте число — новый бюджет (например, 180):")
    return SET_BUDGET_WAIT

async def установить_бюджет_process(update, context):
    text = update.message.text.strip()
    try:
        value = int(text)
        if value <= 0:
            await update.message.reply_text("Бюджет должен быть положительным числом!")
            return ConversationHandler.END
        db.set_budget(value)
        await update.message.reply_text(f"Бюджет успешно установлен: {value}")
    except Exception:
        await update.message.reply_text("Ошибка! Введите целое положительное число.")
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
