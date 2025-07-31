from telegram import Update, InputFile, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
import db
import os
from utils import is_admin, IMAGES_DIR, logger

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    registered = db.register_user(user.id, user.username, user.full_name)
    msg_id = f"Ваш Telegram ID: {user.id}\n"
    if is_admin(user.id):
        keyboard = [["/tour", "/hc"], ["/send_tour_image", "/addhc", "/send_results", "/add_player", "/list_players"]]
        msg = (
            f'Привет, {user.full_name}! Ты зарегистрирован как администратор Fantasy KHL.\n\n'
            'Доступные команды:\n/tour — показать состав на тур\n/hc — баланс HC\n/send_tour_image — загрузить и разослать изображение тура\n/addhc — начислить HC пользователю\n/send_results — разослать результаты тура\n/add_player — добавить игрока\n/list_players — список игроков'
        )
    else:
        keyboard = [["/tour", "/hc"]]
        msg = (
            f'Привет, {user.full_name}! Ты зарегистрирован в Fantasy KHL.\n\n'
            'Доступные команды:\n/tour — показать состав на тур\n/hc — баланс HC'
        )
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    if registered:
        await message.reply_text(msg_id + msg, reply_markup=markup)
    else:
        await message.reply_text(msg_id + 'Ты уже зарегистрирован!', reply_markup=markup)

# --- TOUR ConversationHandler states ---
TOUR_START, TOUR_FORWARD_1, TOUR_FORWARD_2, TOUR_FORWARD_3, TOUR_DEFENDER_1, TOUR_DEFENDER_2, TOUR_GOALIE, TOUR_CAPTAIN = range(8)

async def tour_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем объект сообщения для ответа (универсально для Update и CallbackQuery)
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message
    # 1. Отправить картинку тура и вводный текст с бюджетом
    budget = db.get_budget() or 0
    roster = db.get_tour_roster_with_player_info()
    forwards = [p for p in roster if p[3].lower() == 'нападающий']
    defenders = [p for p in roster if p[3].lower() == 'защитник']
    goalies = [p for p in roster if p[3].lower() == 'вратарь']
    context.user_data['tour_budget'] = budget
    context.user_data['tour_roster'] = roster
    context.user_data['tour_selected'] = {
        'forwards': [],
        'defenders': [],
        'goalie': None,
        'captain': None,
        'spent': 0
    }
    context.user_data['tour_selected'] = {'forwards': [], 'defenders': [], 'goalie': None, 'captain': None, 'spent': 0}
    # Отправить картинку (если есть)
    try:
        tour_img_path = None
        tour_img_txt = os.path.join(os.getcwd(), 'latest_tour.txt')
        if os.path.exists(tour_img_txt):
            with open(tour_img_txt, 'r') as f:
                fname = f.read().strip()
                if fname:
                    fpath = os.path.join(IMAGES_DIR, fname)
                    if os.path.exists(fpath):
                        tour_img_path = fpath
        if not tour_img_path:
            # fallback: last by name
            files = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
            if files:
                tour_img_path = os.path.join(IMAGES_DIR, sorted(files)[-1])
        if tour_img_path:
            with open(tour_img_path, 'rb') as img:
                await update.message.reply_photo(photo=InputFile(img))
    except Exception as e:
        logger.error(f'Ошибка при отправке изображения тура: {e}')
    # Вводный текст
    intro = (
        "Вот список игроков на тур. Выберите состав:\n"
        "3 нападающих\n2 защитников\n1 вратаря\n\n1 капитан (из выбранных)\n\n"
        f"💰 Ваш бюджет: {budget} HC"
    )
    await message.reply_text(intro)
    # Сразу показываем выбор первого нападающего!
    return await tour_forward_1(update, context)

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

async def send_player_choice(update, context, position, exclude_ids, next_state, budget):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    # Универсально получаем message для reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message
    # Получаем актуальный ростер
    roster = context.user_data['tour_roster']
    # Фильтруем по позиции и исключениям
    players = [p for p in roster if p[3].lower() == position and p[1] not in exclude_ids and p[7] <= budget]
    if not players:
        # Проверка: если не хватает HC для обязательного выбора
        text = (
            '🚨 Вы привысили потолок зарплат. Пересоберите состав, чтобы вписаться в лимит.'
        )
        keyboard = [
            [InlineKeyboardButton('Пересобрать состав', callback_data='restart_tour')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(text, reply_markup=reply_markup)
        return ConversationHandler.END
    keyboard = []
    for p in players:
        btn_text = f"{p[2]} — {p[7]} HC"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pick_{p[1]}_{position}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Выберите {position} (осталось HC: {budget})"
    await message.reply_text(text, reply_markup=reply_markup)
    return next_state
    keyboard = []
    for p in players:
        btn_text = f"{p[2]} — {p[7]} HC"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pick_{p[1]}_{position}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Выберите {position} (осталось HC: {budget})"
    await message.reply_text(text, reply_markup=reply_markup)
    return next_state

async def tour_forward_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    picked = context.user_data['tour_selected']['forwards']
    return await send_player_choice(update, context, 'нападающий', picked, TOUR_FORWARD_2, budget)


async def tour_forward_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data
        print(f"Callback data: {data}", flush=True)
        # Ожидается формат pick_<player_id>_нападающий
        if not data.startswith('pick_') or '_нападающий' not in data:
            await query.edit_message_text('Некорректный выбор.')
            return TOUR_FORWARD_1
        pid = int(data.split('_')[1])
        # Получаем игрока по id
        roster = context.user_data['tour_roster']
        player = next((p for p in roster if p[1] == pid), None)
        if not player:
            await query.edit_message_text('Игрок не найден.')
            return TOUR_FORWARD_1
        # Проверяем бюджет
        budget = context.user_data['tour_budget']
        spent = context.user_data['tour_selected']['spent']
        if spent + player[7] > budget:
            await query.edit_message_text(f'Недостаточно HC для выбора {player[1]}!')
            return TOUR_FORWARD_1
        # Сохраняем выбор
        context.user_data['tour_selected']['forwards'].append(pid)
        context.user_data['tour_selected']['spent'] += player[7]
        left = budget - context.user_data['tour_selected']['spent']
        await query.edit_message_text(f'Вы выбрали: {player[2]} ({player[7]} HC)\nОсталось HC: {left}')
        # Переход ко второму или третьему нападающему
        if len(context.user_data['tour_selected']['forwards']) == 1:
            print("tour_forward_callback SUCCESS: переход к tour_forward_2", flush=True)
            return await tour_forward_2(update, context)
        elif len(context.user_data['tour_selected']['forwards']) == 2:
            print("tour_forward_callback SUCCESS: переход к tour_forward_3", flush=True)
            return await tour_forward_3(update, context)
        elif len(context.user_data['tour_selected']['forwards']) == 3:
            print("tour_forward_callback SUCCESS: переход к tour_defender_1", flush=True)
            await tour_defender_1(update, context)
            return TOUR_DEFENDER_1
    except Exception as e:
        print(f"tour_forward_callback ERROR: {e}", flush=True)
        logger.exception("Exception in tour_forward_callback")
        await query.edit_message_text(f"Ошибка: {e}")
        return TOUR_FORWARD_1
    finally:
        print("tour_forward_callback FINISHED", flush=True)


async def tour_forward_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = context.user_data['tour_selected']['forwards']
    return await send_player_choice(update, context, 'нападающий', picked, TOUR_FORWARD_3, left)


async def tour_forward_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = context.user_data['tour_selected']['forwards']
    # Показываем клавиатуру для третьего нападающего, next_state — TOUR_FORWARD_3
    return await send_player_choice(update, context, 'нападающий', picked, TOUR_FORWARD_3, left)

async def tour_defender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data
        print(f"Callback data: {data}", flush=True)
        # Ожидается формат pick_<player_id>_защитник
        if not data.startswith('pick_') or '_защитник' not in data:
            await query.edit_message_text('Некорректный выбор.')
            return TOUR_DEFENDER_1
        pid = int(data.split('_')[1])
        roster = context.user_data['tour_roster']
        player = next((p for p in roster if p[1] == pid), None)
        if not player:
            await query.edit_message_text('Игрок не найден.')
            return TOUR_DEFENDER_1
        budget = context.user_data['tour_budget']
        spent = context.user_data['tour_selected']['spent']
        if spent + player[7] > budget:
            await query.edit_message_text(f'Недостаточно HC для выбора {player[1]}!')
            return TOUR_DEFENDER_1
        context.user_data['tour_selected']['defenders'].append(pid)
        context.user_data['tour_selected']['spent'] += player[7]
        left = budget - context.user_data['tour_selected']['spent']
        await query.edit_message_text(f'Вы выбрали: {player[2]} ({player[7]} HC)\nОсталось HC: {left}')
        if len(context.user_data['tour_selected']['defenders']) == 1:
            print("tour_defender_callback SUCCESS: переход к tour_defender_2", flush=True)
            return await tour_defender_2(update, context)
        elif len(context.user_data['tour_selected']['defenders']) == 2:
            print("tour_defender_callback SUCCESS: переход к tour_goalie", flush=True)
            await tour_goalie(update, context)
            return TOUR_GOALIE
    except Exception as e:
        print(f"tour_defender_callback ERROR: {e}", flush=True)
        logger.exception("Exception in tour_defender_callback")
        await query.edit_message_text(f"Ошибка: {e}")
        return TOUR_DEFENDER_1
    finally:
        print("tour_defender_callback FINISHED", flush=True)


async def tour_defender_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = context.user_data['tour_selected']['defenders']
    return await send_player_choice(update, context, 'защитник', picked, TOUR_DEFENDER_2, left)

async def tour_defender_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = context.user_data['tour_selected']['defenders']
    # Показываем клавиатуру для второго защитника, next_state — TOUR_DEFENDER_2
    return await send_player_choice(update, context, 'защитник', picked, TOUR_DEFENDER_2, left)

async def tour_goalie_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data
        print(f"Callback data: {data}", flush=True)
        # Ожидается формат pick_<player_id>_вратарь
        if not data.startswith('pick_') or '_вратарь' not in data:
            await query.edit_message_text('Некорректный выбор.')
            return TOUR_GOALIE
        pid = int(data.split('_')[1])
        roster = context.user_data['tour_roster']
        player = next((p for p in roster if p[1] == pid), None)
        if not player:
            await query.edit_message_text('Игрок не найден.')
            return TOUR_GOALIE
        budget = context.user_data['tour_budget']
        spent = context.user_data['tour_selected']['spent']
        if spent + player[7] > budget:
            await query.edit_message_text(f'Недостаточно HC для выбора {player[1]}!')
            return TOUR_GOALIE
        context.user_data['tour_selected']['goalie'] = pid
        context.user_data['tour_selected']['spent'] += player[7]
        left = budget - context.user_data['tour_selected']['spent']
        await query.edit_message_text(f'Вы выбрали: {player[2]} ({player[7]} HC)\nОсталось HC: {left}')
        # Дальше — выбор капитана
        return TOUR_CAPTAIN
    except Exception as e:
        print(f"tour_goalie_callback ERROR: {e}", flush=True)
        logger.exception("Exception in tour_goalie_callback")
        await query.edit_message_text(f"Ошибка: {e}")
        return TOUR_GOALIE
    finally:
        print("tour_goalie_callback FINISHED", flush=True)


async def tour_goalie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = []
    # Вратарь только один, не нужен exclude кроме уже выбранного
    if context.user_data['tour_selected']['goalie']:
        picked = [context.user_data['tour_selected']['goalie']]
    return await send_player_choice(update, context, 'вратарь', picked, TOUR_CAPTAIN, left)


async def tour_captain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    # Универсально получаем message для reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message

    selected = context.user_data['tour_selected']
    roster = context.user_data['tour_roster']
    # Собираем id полевых игроков
    field_ids = selected['forwards'] + selected['defenders']
    # Получаем инфу по игрокам
    candidates = [p for p in roster if p[1] in field_ids]
    keyboard = [
        [InlineKeyboardButton(f"{p[2]} ({p[3]})", callback_data=f"pick_captain_{p[1]}")]
        for p in candidates
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "Назначь одного полевого игрока из состава капитаном. Его итоговые очки умножим на 1.5"
    await message.reply_text(text, reply_markup=reply_markup)
    return TOUR_CAPTAIN

# --- Обработчик выбора капитана ---
async def tour_captain_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith('pick_captain_'):
        await query.edit_message_text('Некорректный выбор капитана.')
        return TOUR_CAPTAIN
    captain_id = int(data.replace('pick_captain_', ''))
    context.user_data['tour_selected']['captain'] = captain_id
    # Получаем финальный состав
    selected = context.user_data['tour_selected']
    roster = context.user_data['tour_roster']
    def get_name(pid):
        p = next((x for x in roster if x[1]==pid), None)
        return f"{p[2]} ({p[3]})" if p else str(pid)
    text = "\n".join([
        "Ваш итоговый состав:",
        f"Нападающие: {', '.join(get_name(pid) for pid in selected['forwards'])}",
        f"Защитники: {', '.join(get_name(pid) for pid in selected['defenders'])}",
        f"Вратарь: {get_name(selected['goalie'])}",
        f"\nКапитан: {get_name(captain_id)} (очки x1.5)"
    ])
    await query.edit_message_text(text)
    return ConversationHandler.END


async def restart_tour_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Запускаем процесс выбора состава заново через /tour (ConversationHandler entry_point)
    await context.bot.send_message(chat_id=query.message.chat_id, text="/tour")
    return ConversationHandler.END

async def hc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    data = db.get_user_by_id(user.id)
    if data:
        await message.reply_text(f'💰 Твой баланс: {data[3]} HC')
    else:
        await message.reply_text('Ты не зарегистрирован!')
