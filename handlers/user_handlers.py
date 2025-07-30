from telegram import Update, InputFile, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
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
        await update.message.reply_text(msg_id + msg, reply_markup=markup)
    else:
        await update.message.reply_text(msg_id + 'Ты уже зарегистрирован!', reply_markup=markup)

# --- TOUR ConversationHandler states ---
TOUR_START, TOUR_FORWARD_1, TOUR_FORWARD_2, TOUR_FORWARD_3, TOUR_DEFENDER_1, TOUR_DEFENDER_2, TOUR_GOALIE, TOUR_CAPTAIN = range(8)

async def tour_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Отправить картинку тура и вводный текст с бюджетом
    budget = db.get_budget() or 0
    roster = db.get_tour_roster_with_player_info()
    forwards = [p for p in roster if p[3].lower() == 'нападающий']
    defenders = [p for p in roster if p[3].lower() == 'защитник']
    goalies = [p for p in roster if p[3].lower() == 'вратарь']
    context.user_data['tour_budget'] = budget
    context.user_data['tour_roster'] = roster
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
    await update.message.reply_text(intro)
    # Переходим к выбору первого нападающего
    return TOUR_FORWARD_1

async def tour_forward_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # TODO: показать кнопки с нападающими, обработать выбор
    pass

async def tour_forward_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # TODO: показать кнопки с нападающими (без уже выбранных), обработать выбор
    pass

async def tour_forward_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # TODO: показать кнопки с нападающими (без уже выбранных), обработать выбор
    pass

async def tour_defender_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # TODO: показать кнопки с защитниками, обработать выбор
    pass

async def tour_defender_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # TODO: показать кнопки с защитниками (без уже выбранных), обработать выбор
    pass

async def tour_goalie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # TODO: показать кнопки с вратарями, обработать выбор
    pass

async def tour_captain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # TODO: показать кнопки с выбранными нападающими и защитниками, обработать выбор капитана
    pass


async def hc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    data = db.get_user_by_id(user.id)
    if data:
        await update.message.reply_text(f'💰 Твой баланс: {data[3]} HC')
    else:
        await update.message.reply_text('Ты не зарегистрирован!')
