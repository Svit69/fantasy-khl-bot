from telegram import Update, InputFile, ReplyKeyboardMarkup, MessageEntity, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from telegram.error import BadRequest
from telegram.constants import MessageEntityType
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
import db
import os
from utils import is_admin, IMAGES_DIR, logger, CHALLENGE_IMAGE_PATH_FILE
import datetime

# --- Time guards: block actions after deadlines ---
def _tour_deadline_passed(context) -> bool:
    try:
        import db as _db
        tour_id = context.user_data.get('active_tour_id') or context.user_data.get('selected_tour_id')
        if not tour_id:
            return False
        row = _db.get_tour_by_id(tour_id)
        dl_str = row[3]
        # Parse deadline in MSK
        dl = datetime.datetime.strptime(str(dl_str), "%d.%m.%y %H:%M")
        try:
            from zoneinfo import ZoneInfo
            dl = dl.replace(tzinfo=ZoneInfo("Europe/Moscow"))
            now = datetime.datetime.now(ZoneInfo("Europe/Moscow"))
        except Exception:
            # Fallback: approximate by shifting UTC by +3
            now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
        return now >= dl
    except Exception:
        return False

def _challenge_deadline_passed(challenge_id: int) -> bool:
    """╨б╤З╨╕╤В╨░╨╡╨╝ ╨┤╨╡╨┤╨╗╨░╨╣╨╜ ╨┐╤А╨╛╤И╨╡╨┤╤И╨╕╨╝ ╨╜╨░ ╨╛╤Б╨╜╨╛╨▓╨╡ ╤Б╤В╨░╤В╤Г╤Б╨░ ╨╕╨╖ ╨С╨Ф.

    ╨Т╨╛╨╖╨▓╤А╨░╤Й╨░╨╡╤В True, ╨╡╤Б╨╗╨╕ ╤Б╤В╨░╤В╤Г╤Б '╨▓ ╨╕╨│╤А╨╡' ╨╕╨╗╨╕ '╨╖╨░╨▓╨╡╤А╤И╨╡╨╜' (╤В.╨╡. deadline ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗).
    ╨Ф╨╗╤П '╨░╨║╤В╨╕╨▓╨╡╨╜' ╨╕ '╨▓ ╨╛╨╢╨╕╨┤╨░╨╜╨╕╨╕' тАФ False.
    """
    try:
        import db as _db
        ch = _db.get_challenge_by_id(challenge_id)
        # ch: (id, start_date, deadline, end_date, image_filename, status, image_file_id)
        status = (ch[5] or '').lower()
        return status in ('╨▓ ╨╕╨│╤А╨╡', '╨╖╨░╨▓╨╡╤А╤И╨╡╨╜')
    except Exception:
        return False

def escape_md(text):
    # ╨Т╤Б╨╡ ╤Б╨┐╨╡╤Ж╤Б╨╕╨╝╨▓╨╛╨╗╤Л MarkdownV2
    for ch in r'\_*[]()~`>#+-=|{}.!':
        text = text.replace(ch, '\\' + ch)
    return text

async def send_player_selected_message(query, player, budget, context):
    left = budget - context.user_data['tour_selected']['spent']
    player_name = escape_md(str(player[2]))
    cost = escape_md(str(player[7]))
    left_str = escape_md(str(left))
    msg = f'╨Т╤Л ╨▓╤Л╨▒╤А╨░╨╗╨╕ {player_name} \\({cost}\\)\n\n*╨Ю╤Б╤В╨░╨▓╤И╨╕╨╣╤Б╤П ╨▒╤О╨┤╨╢╨╡╤В: {left_str}*'
    await query.edit_message_text(msg, parse_mode="MarkdownV2")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ╨г╨╜╨╕╨▓╨╡╤А╤Б╨░╨╗╤М╨╜╨╛ ╨┐╨╛╨╗╤Г╤З╨░╨╡╨╝ message ╨┤╨╗╤П reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message
    user = update.effective_user
    registered = db.register_user(user.id, user.username, user.full_name)

    # --- ╨а╨╡╤Д╨╡╤А╨░╨╗: ╨╡╤Б╨╗╨╕ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤М ╨┐╤А╨╕╤И╤С╨╗ ╨┐╨╛ ╤Б╤Б╤Л╨╗╨║╨╡ ref_<id>,
    # ╨╕ ╤Н╤В╨╛ ╨╡╨│╨╛ ╨Я╨Х╨а╨Т╨Р╨п ╤А╨╡╨│╨╕╤Б╤В╤А╨░╤Ж╨╕╤П (registered == True), ╨╜╨░╤З╨╕╤Б╨╗╤П╨╡╨╝ ╤А╨╡╤Д╨╡╤А╨╡╤А╤Г +50 HC
    try:
        if registered and getattr(context, 'args', None):
            arg0 = context.args[0] if len(context.args) > 0 else ''
            if isinstance(arg0, str) and arg0.startswith('ref_'):
                ref_str = arg0[4:]
                if ref_str.isdigit():
                    referrer_id = int(ref_str)
                    if referrer_id != user.id:
                        # ╨Т╤Б╤В╨░╨▓╨╕╨╝ ╨╖╨░╨┐╨╕╤Б╤М ╤А╨╡╤Д╨╡╤А╨░╨╗╨░, ╨╡╤Б╨╗╨╕ ╨┤╨╗╤П ╤Н╤В╨╛╨│╨╛ user_id ╨╡╤С ╨╡╤Й╤С ╨╜╨╡ ╨▒╤Л╨╗╨╛
                        if db.add_referral_if_new(user.id, referrer_id):
                            # ╨С╨╛╨╜╤Г╤Б ╨╖╨░╨▓╨╕╤Б╨╕╤В ╨╛╤В ╨░╨║╤В╨╕╨▓╨╜╨╛╤Б╤В╨╕ ╨┐╨╛╨┤╨┐╨╕╤Б╨║╨╕ ╤Г ╤А╨╡╤Д╨╡╤А╨╡╤А╨░
                            try:
                                from db import is_subscription_active
                                bonus = 100 if is_subscription_active(referrer_id) else 50
                            except Exception:
                                bonus = 50
                            db.update_hc_balance(referrer_id, bonus)
                            # ╨г╨▓╨╡╨┤╨╛╨╝╨╕╨╝ ╤А╨╡╤Д╨╡╤А╨╡╤А╨░ (╨╡╤Б╨╗╨╕ ╨╝╨╛╨╢╨╜╨╛)
                            try:
                                new_balance = db.get_user_by_id(referrer_id)
                                new_balance = new_balance[3] if new_balance else 'тАФ'
                                await context.bot.send_message(
                                    chat_id=referrer_id,
                                    text=f'ЁЯОЙ ╨Я╨╛ ╨▓╨░╤И╨╡╨╣ ╤А╨╡╤Д╨╡╤А╨░╨╗╤М╨╜╨╛╨╣ ╤Б╤Б╤Л╨╗╨║╨╡ ╨╖╨░╤А╨╡╨│╨╕╤Б╤В╤А╨╕╤А╨╛╨▓╨░╨╗╤Б╤П ╨╜╨╛╨▓╤Л╨╣ ╤Г╤З╨░╤Б╤В╨╜╨╕╨║!\n+{bonus} HC ╨╜╨░╤З╨╕╤Б╨╗╨╡╨╜╨╛. ╨в╨╡╨║╤Г╤Й╨╕╨╣ ╨▒╨░╨╗╨░╨╜╤Б: {new_balance} HC.'
                                )
                            except Exception:
                                pass
                            # ╨б╨╛╨╛╨▒╤Й╨╕╨╝ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤О, ╤З╤В╨╛ ╨╛╨╜ ╨┐╤А╨╕╤И╤С╨╗ ╨┐╨╛ ╤Б╤Б╤Л╨╗╨║╨╡
                            try:
                                await message.reply_text('╨Т╤Л ╨╖╨░╤А╨╡╨│╨╕╤Б╤В╤А╨╕╤А╨╛╨▓╨░╨╗╨╕╤Б╤М ╨┐╨╛ ╤А╨╡╤Д╨╡╤А╨░╨╗╤М╨╜╨╛╨╣ ╤Б╤Б╤Л╨╗╨║╨╡ тАФ ╨┤╨╛╨▒╤А╨╛ ╨┐╨╛╨╢╨░╨╗╨╛╨▓╨░╤В╤М!')
                            except Exception:
                                pass
    except Exception as e:
        # ╨Э╨╡ ╨┐╤А╨╡╤А╤Л╨▓╨░╨╡╨╝ ╤Б╤В╨░╤А╤В ╨┐╤А╨╕ ╨╛╤И╨╕╨▒╨║╨╡ ╤А╨╡╤Д╨╡╤А╨░╨╗╤М╨╜╨╛╨╣ ╨╛╨▒╤А╨░╨▒╨╛╤В╨║╨╕
        try:
            await message.reply_text(f"[WARN] ╨Ю╤И╨╕╨▒╨║╨░ ╨╛╨▒╤А╨░╨▒╨╛╤В╨║╨╕ ╤А╨╡╤Д╨╡╤А╨░╨╗╨░: {e}")
        except Exception:
            pass
    msg_id = f"╨Т╨░╤И Telegram ID: {user.id}\n"
    if is_admin(user.id):
        keyboard = [["/tour", "/hc"], ["/send_tour_image", "/addhc", "/send_results", "/add_player", "/list_players"]]
        msg = (
            f'╨Я╤А╨╕╨▓╨╡╤В, {user.full_name}! ╨в╤Л ╨╖╨░╤А╨╡╨│╨╕╤Б╤В╤А╨╕╤А╨╛╨▓╨░╨╜ ╨║╨░╨║ ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А Fantasy KHL.\n\n'
            '╨Ф╨╛╤Б╤В╤Г╨┐╨╜╤Л╨╡ ╨║╨╛╨╝╨░╨╜╨┤╤Л:\n/tour тАФ ╨┐╨╛╨║╨░╨╖╨░╤В╤М ╤Б╨╛╤Б╤В╨░╨▓ ╨╜╨░ ╤В╤Г╤А\n/hc тАФ ╨▒╨░╨╗╨░╨╜╤Б HC\n/send_tour_image тАФ ╨╖╨░╨│╤А╤Г╨╖╨╕╤В╤М ╨╕ ╤А╨░╨╖╨╛╤Б╨╗╨░╤В╤М ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╡ ╤В╤Г╤А╨░\n/addhc тАФ ╨╜╨░╤З╨╕╤Б╨╗╨╕╤В╤М HC ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤О\n/send_results тАФ ╤А╨░╨╖╨╛╤Б╨╗╨░╤В╤М ╤А╨╡╨╖╤Г╨╗╤М╤В╨░╤В ╤В╤Г╤А╨░\n/add_player тАФ ╨┤╨╛╨▒╨░╨▓╨╕╤В╤М ╨╕╨│╤А╨╛╨║╨░\n/list_players тАФ ╤Б╨┐╨╕╤Б╨╛╨║ ╨╕╨│╤А╨╛╨║╨╛╨▓'
        )
    else:
        keyboard = [["/tour", "/hc", "/rules", "/shop"]]
        msg = (
            f'╨Я╤А╨╕╨▓╨╡╤В, {user.full_name}! ╨Ф╨╛╨▒╤А╨╛ ╨┐╨╛╨╢╨░╨╗╨╛╨▓╨░╤В╤М ╨▓ ╨д╨╡╨╜╤В╨╡╨╖╨╕ ╨Ф╤А╨░╤Д╤В ╨Ъ╨е╨Ы\n\n'
            'ЁЯФ╕ ╨б╨╛╨▒╨╕╤А╨░╨╣ ╤Б╨▓╨╛╤О ╨║╨╛╨╝╨░╨╜╨┤╤Г ╨╜╨░ ╨║╨░╨╢╨┤╤Л╨╣ ╤В╤Г╤А\n'
            'ЁЯФ╕ ╨б╨╗╨╡╨┤╨╕ ╨╖╨░ ╤А╨╡╨╖╤Г╨╗╤М╤В╨░╤В╨░╨╝╨╕ ╤В╤Г╤А╨╛╨▓\n'
            'ЁЯФ╕ ╨Ч╨░╤А╨░╨▒╨░╤В╤Л╨▓╨░╨╣ ╨╕ ╨║╨╛╨┐╨╕ Hockey Coin (HC)\n'
            'ЁЯФ╕ ╨Ь╨╡╨╜╤П╨╣ Hockey Coin (HC) ╨╜╨░ ╨┐╤А╨╕╨╖╤Л\n\n'
            '╨Ф╨╛╤Б╤В╤Г╨┐╨╜╤Л╨╡ ╨║╨╛╨╝╨░╨╜╨┤╤Л:\n'
            '/tour тАФ ╤В╤Г╤А ╨╕ ╤Г╨┐╤А╨░╨▓╨╗╨╡╨╜╨╕╨╡ ╨║╨╛╨╝╨░╨╜╨┤╨╛╨╣\n'
            '/hc тАФ ╤В╨▓╨╛╨╣ ╨▒╨░╨╗╨░╨╜╤Б Hockey Coin\n'
            '/rules тАФ ╨┐╤А╨░╨▓╨╕╨╗╨░ ╤Б╨▒╨╛╤А╨║╨╕ ╤Б╨╛╤Б╤В╨░╨▓╨╛╨▓\n'
            '/shop тАФ ╨╝╨░╨│╨░╨╖╨╕╨╜ ╨┐╤А╨╕╨╖╨╛╨▓'
        )
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    if registered:
        await message.reply_text(msg_id + msg, reply_markup=markup)
    else:
        await message.reply_text(
            escape_md("тЪая╕П ╨в╤Л ╤Г╨╢╨╡ ╨▓ ╤Б╨┐╨╕╤Б╨║╨╡ ╨│╨╡╨╜╨╡╤А╨░╨╗╤М╨╜╤Л╤Е ╨╝╨╡╨╜╨╡╨┤╨╢╨╡╤А╨╛╨▓ ╨д╨╡╨╜╤В╨╡╨╖╨╕ ╨Ф╤А╨░╤Д╤В╨░ ╨Ъ╨е╨Ы.\n\n╨д╨╛╤А╨╝╨╕╤А╤Г╨╣ ╤Б╨╛╤Б╤В╨░╨▓ ╨╕ ╤Б╨╗╨╡╨┤╨╕ ╨╖╨░ ╤А╨╡╨╖╤Г╨╗╤М╤В╨░╤В╨░╨╝╨╕ ╤В╤Г╤А╨╛╨▓ - /tour"),
            reply_markup=markup,
            parse_mode="MarkdownV2"
        )

# --- TOUR ConversationHandler states ---

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    # ╨Ю╨┐╤А╨╡╨┤╨╡╨╗╨╕╨╝ ╤В╨╡╨║╤Г╤Й╨╕╨╣ ╨▒╨╛╨╜╤Г╤Б: 100 HC ╨┐╤А╨╕ ╨░╨║╤В╨╕╨▓╨╜╨╛╨╣ ╨┐╨╛╨┤╨┐╨╕╤Б╨║╨╡, ╨╕╨╜╨░╤З╨╡ 50 HC
    try:
        from db import is_subscription_active
        bonus = 100 if is_subscription_active(user.id) else 50
    except Exception:
        bonus = 50
    text = (
        f"ЁЯФЧ ╨Т╨░╤И╨░ ╤А╨╡╤Д╨╡╤А╨░╨╗╤М╨╜╨░╤П ╤Б╤Б╤Л╨╗╨║╨░:\n"
        f"{link}\n\n"
        f"╨Я╤А╨╕╨│╨╗╨░╤И╨░╨╣╤В╨╡ ╨┤╤А╤Г╨╖╨╡╨╣! ╨Ч╨░ ╨║╨░╨╢╨┤╨╛╨│╨╛ ╨╜╨╛╨▓╨╛╨│╨╛ ╤Г╤З╨░╤Б╤В╨╜╨╕╨║╨░ ╨▓╤Л ╨┐╨╛╨╗╤Г╤З╨╕╤В╨╡ +{bonus} HC ╨┐╨╛╤Б╨╗╨╡ ╨╡╨│╨╛ ╤А╨╡╨│╨╕╤Б╤В╤А╨░╤Ж╨╕╨╕."
    )
    keyboard = [[InlineKeyboardButton('╨б╨║╨╛╨┐╨╕╤А╨╛╨▓╨░╤В╤М ╤Б╤Б╤Л╨╗╨║╤Г', url=link)]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from utils import create_yookassa_payment
    user = update.effective_user
    payment_url, payment_id = create_yookassa_payment(user.id)
    # ╨б╨╛╤Е╤А╨░╨╜╤П╨╡╨╝ payment_id ╨▓ ╨С╨Ф (╨╝╨╛╨╢╨╜╨╛ ╨┤╨╛╨▒╨░╨▓╨╕╤В╤М ╤Д╤Г╨╜╨║╤Ж╨╕╤О)
    # db.save_payment_id(user.id, payment_id)
    # ╨Я╤А╨╛╨▓╨╡╤А╨╕╨╝ ╤Б╤В╨░╤В╤Г╤Б ╨┐╨╛╨┤╨┐╨╕╤Б╨║╨╕ ╨╕ ╨┤╨░╤В╤Г ╨╛╨║╨╛╨╜╤З╨░╨╜╨╕╤П
    end_line = ""
    try:
        from db import is_subscription_active, get_subscription
        import datetime
        if is_subscription_active(user.id):
            row = get_subscription(user.id)  # (user_id, paid_until, last_payment_id)
            pu = row[1] if row else None
            dt = None
            try:
                dt = datetime.datetime.fromisoformat(pu) if pu else None
            except Exception:
                dt = None
            if dt:
                # ╨Я╤А╨╡╨╛╨▒╤А╨░╨╖╤Г╨╡╨╝ ╨║ ╨╗╨╛╨║╨░╨╗╤М╨╜╨╛╨╝╤Г ╨▓╤А╨╡╨╝╨╡╨╜╨╕ ╨┤╨╗╤П ╤Г╨┤╨╛╨▒╤Б╤В╨▓╨░
                local_dt = dt.astimezone() if dt.tzinfo else dt
                end_line = f"\n<b>╨Я╨╛╨┤╨┐╨╕╤Б╨║╨░ ╨░╨║╤В╨╕╨▓╨╜╨░</b> ╨┤╨╛: <b>{local_dt.strftime('%d.%m.%Y %H:%M')}</b>"
    except Exception:
        pass

    benefits = (
        "\n\n<b>╨Я╤А╨╡╨╕╨╝╤Г╤Й╨╡╤Б╤В╨▓╨░ ╨┐╨╛╨┤╨┐╨╕╤Б╨║╨╕:</b>\n"
        "тАв ╨Ф╨╛╨┐╨╛╨╗╨╜╨╕╤В╨╡╨╗╤М╨╜╤Л╨╣ ╨╕╨│╤А╨╛╨║ ╨▓ ╨┐╤Г╨╗ ╨╜╨░ ╤В╤Г╤А\n"
        "тАв ╨Я╨╛╨▓╤Л╤И╨╡╨╜╨╜╤Л╨╡ ╤А╨╡╤Д╨╡╤А╨░╨╗╤М╨╜╤Л╨╡ ╨▒╨╛╨╜╤Г╤Б╤Л\n"
        "тАв ╨Я╤А╨╕╨╛╤А╨╕╤В╨╡╤В╨╜╨░╤П ╨┐╨╛╨┤╨┤╨╡╤А╨╢╨║╨░\n"
        "тАв ╨Э╨╛╨▓╤Л╨╡ ╤Д╨╕╤З╨╕ ╤А╨░╨╜╤М╤И╨╡ ╨▓╤Б╨╡╤Е"
    )

    text = (
        f"ЁЯТ│ <b>╨Я╨╛╨┤╨┐╨╕╤Б╨║╨░ ╨╜╨░ Fantasy KHL</b>\n\n"
        f"╨б╤В╨╛╨╕╨╝╨╛╤Б╤В╤М: <b>299 ╤А╤Г╨▒/╨╝╨╡╤Б╤П╤Ж</b>"
        f"{end_line}\n\n"
        f"╨Э╨░╨╢╨╝╨╕╤В╨╡ ╨║╨╜╨╛╨┐╨║╤Г ╨╜╨╕╨╢╨╡ ╨┤╨╗╤П ╨╛╨┐╨╗╨░╤В╤Л ╤З╨╡╤А╨╡╨╖ ╨оKassa. ╨Я╨╛╤Б╨╗╨╡ ╤Г╤Б╨┐╨╡╤И╨╜╨╛╨╣ ╨╛╨┐╨╗╨░╤В╤Л ╨┐╨╛╨┤╨┐╨╕╤Б╨║╨░ ╨░╨║╤В╨╕╨▓╨╕╤А╤Г╨╡╤В╤Б╤П ╨░╨▓╤В╨╛╨╝╨░╤В╨╕╤З╨╡╤Б╨║╨╕."
        f"{benefits}"
    )
    keyboard = [[InlineKeyboardButton('╨Ю╨┐╨╗╨░╤В╨╕╤В╤М 299тВ╜ ╤З╨╡╤А╨╡╨╖ ╨оKassa', url=payment_url)]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# --- Telegram Stars payments ---

async def subscribe_stars(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """╨Ю╤Д╨╛╤А╨╝╨╗╨╡╨╜╨╕╨╡ ╨┐╨╛╨┤╨┐╨╕╤Б╨║╨╕ ╤З╨╡╤А╨╡╨╖ Telegram Stars (invoice)."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    # ╨Ш╨╜╤Д╨╛╤А╨╝╨░╤Ж╨╕╤П ╨╛ ╤В╨╡╨║╤Г╤Й╨╡╨╣ ╨┐╨╛╨┤╨┐╨╕╤Б╨║╨╡, ╨╡╤Б╨╗╨╕ ╨░╨║╤В╨╕╨▓╨╜╨░
    end_line = ""
    try:
        from db import is_subscription_active, get_subscription
        import datetime
        if is_subscription_active(user.id):
            row = get_subscription(user.id)  # (user_id, paid_until, last_payment_id)
            pu = row[1] if row else None
            dt = None
            try:
                dt = datetime.datetime.fromisoformat(pu) if pu else None
            except Exception:
                dt = None
            if dt:
                local_dt = dt.astimezone() if dt.tzinfo else dt
                end_line = f"\n<b>╨в╨╡╨║╤Г╤Й╨░╤П ╨┐╨╛╨┤╨┐╨╕╤Б╨║╨░ ╨░╨║╤В╨╕╨▓╨╜╨░</b> ╨┤╨╛: <b>{local_dt.strftime('%d.%m.%Y %H:%M')}</b>"
    except Exception:
        pass

    # ╨д╨╛╤А╨╝╨╕╤А╤Г╨╡╨╝ invoice ╨┤╨╗╤П Telegram Stars
    from utils import SUBSCRIPTION_STARS
    title = "╨Я╨╛╨┤╨┐╨╕╤Б╨║╨░ Fantasy KHL тАФ 1 ╨╝╨╡╤Б╤П╤Ж"
    description = (
        "╨Ф╨╛╤Б╤В╤Г╨┐ ╨║ ╨┐╤А╨╡╨╝╨╕╤Г╨╝-╤Д╤Г╨╜╨║╤Ж╨╕╤П╨╝ ╨╕ ╨▒╨╛╨╜╤Г╤Б╨░╨╝ ╨▓ ╨▒╨╛╤В╨╡." + end_line
    )
    payload = f"sub_{user.id}"
    prices = [LabeledPrice(label="╨Я╨╛╨┤╨┐╨╕╤Б╨║╨░ ╨╜╨░ 1 ╨╝╨╡╤Б╤П╤Ж", amount=int(SUBSCRIPTION_STARS))]

    # ╨Ю╤В╨┐╤А╨░╨▓╨╗╤П╨╡╨╝ invoice: currency XTR тАФ ╨╛╨┐╨╗╨░╤В╨░ Telegram Stars
    await context.bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token="XTR",
        currency="XTR",
        prices=prices,
        start_parameter="subscribe"
    )

    # ╨Я╨╛╤П╤Б╨╜╤П╤О╤Й╨╡╨╡ ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╡
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "╨Э╨░╨╢╨╝╨╕╤В╨╡ ╨║╨╜╨╛╨┐╨║╤Г ╨Ю╨┐╨╗╨░╤В╨╕╤В╤М ╨▓ ╤Б╤З╤С╤В╨╡ ╨▓╤Л╤И╨╡, ╤З╤В╨╛╨▒╤Л ╨╖╨░╨▓╨╡╤А╤И╨╕╤В╤М ╨╛╨┐╨╗╨░╤В╤Г ╤З╨╡╤А╨╡╨╖ Telegram Stars.\n"
                "╨Я╨╛╤Б╨╗╨╡ ╤Г╤Б╨┐╨╡╤И╨╜╨╛╨╣ ╨╛╨┐╨╗╨░╤В╤Л ╨┐╨╛╨┤╨┐╨╕╤Б╨║╨░ ╨░╨║╤В╨╕╨▓╨╕╤А╤Г╨╡╤В╤Б╤П ╨░╨▓╤В╨╛╨╝╨░╤В╨╕╤З╨╡╤Б╨║╨╕."
            )
        )
    except Exception:
        pass


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """╨Я╨╛╨┤╤В╨▓╨╡╤А╨╢╨┤╨░╨╡╨╝ ╨┐╤А╨╡╨┤╤З╨╡╨║-╨░╤Г╤В ╨┤╨╗╤П ╤Б╤З╤С╤В╨░ (╨▓ ╤В.╤З. ╨┤╨╗╤П Stars)."""
    try:
        query = update.pre_checkout_query
    except AttributeError:
        return
    try:
        await query.answer(ok=True)
    except Exception:
        # ╨Т ╤Б╨╗╤Г╤З╨░╨╡ ╨╛╤И╨╕╨▒╨║╨╕ ╨┐╤А╨╛╨▒╤Г╨╡╨╝ ╨╛╤В╨║╨╗╨╛╨╜╨╕╤В╤М ╤Б ╨┐╨╛╤П╤Б╨╜╨╡╨╜╨╕╨╡╨╝
        try:
            await query.answer(ok=False, error_message="╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨┐╨╛╨┤╤В╨▓╨╡╤А╨┤╨╕╤В╤М ╨╛╨┐╨╗╨░╤В╤Г. ╨Я╨╛╨┐╤А╨╛╨▒╤Г╨╣╤В╨╡ ╨┐╨╛╨╖╨╢╨╡.")
        except Exception:
            pass


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """╨Ю╨▒╤А╨░╨▒╨╛╤В╨║╨░ ╤Г╤Б╨┐╨╡╤И╨╜╨╛╨╣ ╨╛╨┐╨╗╨░╤В╤Л: ╨░╨║╤В╨╕╨▓╨╕╤А╤Г╨╡╨╝/╨┐╤А╨╛╨┤╨╗╨╡╨▓╨░╨╡╨╝ ╨┐╨╛╨┤╨┐╨╕╤Б╨║╤Г."""
    try:
        sp = update.message.successful_payment if getattr(update, 'message', None) else None
        if not sp:
            return
        import datetime
        user = update.effective_user
        from db import get_subscription, add_or_update_subscription

        # ╨Я╤А╨╛╨┤╨╗╨╡╨╜╨╕╨╡ ╨╜╨░ 31 ╨┤╨╡╨╜╤М ╨╛╤В ╤В╨╡╨║╤Г╤Й╨╡╨╣ ╨┤╨░╤В╤Л ╨╕╨╗╨╕ ╨┤╨░╤В╤Л ╨╛╨║╨╛╨╜╤З╨░╨╜╨╕╤П ╨░╨║╤В╨╕╨▓╨╜╨╛╨╣ ╨┐╨╛╨┤╨┐╨╕╤Б╨║╨╕
        base = datetime.datetime.utcnow()
        try:
            current = None
            sub = get_subscription(user.id)
            if sub and sub[1]:
                try:
                    current = datetime.datetime.fromisoformat(sub[1])
                except Exception:
                    current = None
            if current and current > base:
                base = current
        except Exception:
            pass
        new_paid_until = base + datetime.timedelta(days=31)

        # ╨б╨╛╤Е╤А╨░╨╜╤П╨╡╨╝ ╨╕╨┤╨╡╨╜╤В╨╕╤Д╨╕╨║╨░╤В╨╛╤А ╨┐╨╗╨░╤В╨╡╨╢╨░ ╨╕╨╖ Telegram
        last_payment_id = None
        try:
            last_payment_id = getattr(sp, 'telegram_payment_charge_id', None) or getattr(sp, 'provider_payment_charge_id', None)
        except Exception:
            last_payment_id = None
        last_payment_id = f"stars:{last_payment_id or ''}"

        add_or_update_subscription(user.id, new_paid_until.isoformat(), last_payment_id)

        local_dt = new_paid_until.astimezone() if new_paid_until.tzinfo else new_paid_until
        await update.message.reply_text(
            f"╨б╨┐╨░╤Б╨╕╨▒╨╛! ╨Ю╨┐╨╗╨░╤В╨░ ╨┐╨╛╨╗╤Г╤З╨╡╨╜╨░. ╨Я╨╛╨┤╨┐╨╕╤Б╨║╨░ ╨░╨║╤В╨╕╨▓╨╜╨░ ╨┤╨╛ {local_dt.strftime('%d.%m.%Y %H:%M')} (MSK)."
        )
    except Exception:
        try:
            await update.message.reply_text("╨Ю╨┐╨╗╨░╤В╨░ ╤Г╤Б╨┐╨╡╤И╨╜╨╛ ╨┐╤А╨╛╤И╨╗╨░, ╨╜╨╛ ╨┐╤А╨╛╨╕╨╖╨╛╤И╨╗╨░ ╨╛╤И╨╕╨▒╨║╨░ ╨┐╤А╨╕ ╨░╨║╤В╨╕╨▓╨░╤Ж╨╕╨╕. ╨б╨▓╤П╨╢╨╕╤В╨╡╤Б╤М ╤Б ╨░╨┤╨╝╨╕╨╜╨╛╨╝.")
        except Exception:
            pass


# --- TOURS LIST (/tours) ---
async def tours(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """╨Я╨╛╨║╨░╨╖╨░╤В╤М ╤Б╨┐╨╕╤Б╨╛╨║ ╨▓╤Б╨╡╤Е ╤В╤Г╤А╨╛╨▓ ╤Б ╨║╨╜╨╛╨┐╨║╨░╨╝╨╕ ╨┤╨╗╤П ╨╛╤В╨║╤А╤Л╤В╨╕╤П ╨┐╨╛╨┤╤А╨╛╨▒╨╜╨╛╤Б╤В╨╡╨╣."""
    try:
        rows = db.get_all_tours() or []
    except Exception as e:
        await update.message.reply_text(f"╨Ю╤И╨╕╨▒╨║╨░ ╨┐╨╛╨╗╤Г╤З╨╡╨╜╨╕╤П ╤Б╨┐╨╕╤Б╨║╨░ ╤В╤Г╤А╨╛╨▓: {e}")
        return
    # ╨Ю╤В╤Д╨╕╨╗╤М╤В╤А╤Г╨╡╨╝ ╨▒╤Г╨┤╤Г╤Й╨╕╨╡ ╤В╤Г╤А╤Л (start_date > now)
    import datetime
    try:
        from zoneinfo import ZoneInfo
        _tz = ZoneInfo("Europe/Moscow")
        now = datetime.datetime.now(_tz)
    except Exception:
        # Fallback: ╨┐╤А╨╕╨▒╨╗╨╕╨╖╨╕╤В╨╡╨╗╤М╨╜╨╛ ╨Ь╤Б╨║ = UTC+3
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
        _tz = None
    filtered = []
    for r in rows:
        # r: (id, name, start, deadline, end, status, winners)
        try:
            start_dt = datetime.datetime.strptime(str(r[2]), "%d.%m.%y")
            deadline_dt = datetime.datetime.strptime(str(r[3]), "%d.%m.%y %H:%M")
            if _tz is not None:
                start_dt = start_dt.replace(tzinfo=_tz)
                deadline_dt = deadline_dt.replace(tzinfo=_tz)
            if start_dt <= now < deadline_dt:
                filtered.append(r)
        except Exception:
            # ╨╡╤Б╨╗╨╕ ╨╜╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╤А╨░╤Б╨┐╨░╤А╤Б╨╕╤В╤М ╨┤╨░╤В╤Г тАФ ╨┐╨╡╤А╨╡╤Б╤В╤А╨░╤Е╤Г╨╡╨╝╤Б╤П ╨╕ ╨╜╨╡ ╨┐╨╛╨║╨░╨╖╤Л╨▓╨░╨╡╨╝ ╤В╨░╨║╨╛╨╣ ╤В╤Г╤А
            continue
    rows = filtered
    if not rows:
        await update.message.reply_text("╨Э╨╡╤В ╨░╨║╤В╨╕╨▓╨╜╤Л╤Е ╤В╤Г╤А╨╛╨▓. ╨Ч╨░╨│╨╗╤П╨╜╨╕╤В╨╡ ╨┐╨╛╨╖╨╢╨╡!")
        return
    # ╨д╨╛╤А╨╝╨╕╤А╤Г╨╡╨╝ ╤Б╨┐╨╕╤Б╨╛╨║ ╨╕ ╨║╨╜╨╛╨┐╨║╨╕
    lines = ["*╨Ф╨╛╤Б╤В╤Г╨┐╨╜╤Л╨╡ ╤В╤Г╤А╤Л:*"]
    buttons = []
    for r in rows:
        # r: (id, name, start, deadline, end, status, winners)
        tid, name, start, deadline, end, status, winners = r
        lines.append(f"тАв #{tid} тАФ {name} [{status}]")
        buttons.append([InlineKeyboardButton(f"╨Ю╤В╨║╤А╤Л╤В╤М #{tid}", callback_data=f"tour_open_{tid}")])
    await update.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')


async def tour_open_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """╨Ю╤В╨║╤А╤Л╤В╤М ╨╕╨╜╤Д╨╛╤А╨╝╨░╤Ж╨╕╤О ╨┐╨╛ ╨▓╤Л╨▒╤А╨░╨╜╨╜╨╛╨╝╤Г ╤В╤Г╤А╤Г: ╨┤╨░╤В╤Л, ╤Б╤В╨░╤В╤Г╤Б, ╨║╨░╤А╤В╨╕╨╜╨║╨░ (╨╡╤Б╨╗╨╕ ╨╡╤Б╤В╤М)."""
    query = update.callback_query
    await query.answer()
    data = query.data  # tour_open_<id>
    try:
        tid = int(data.replace('tour_open_', ''))
    except Exception:
        await query.edit_message_text("╨Э╨╡╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Л╨╣ ╨╖╨░╨┐╤А╨╛╤Б ╤В╤Г╤А╨░.")
        return
    row = None
    try:
        row = db.get_tour_by_id(tid)
    except Exception:
        row = None
    if not row:
        await query.edit_message_text("╨в╤Г╤А ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜.")
        return
    # ╨С╨╗╨╛╨║╨╕╤А╤Г╨╡╨╝ ╨┐╤А╨╛╤Б╨╝╨╛╤В╤А ╨▒╤Г╨┤╤Г╤Й╨╕╤Е ╤В╤Г╤А╨╛╨▓
    try:
        import datetime
        start_dt = datetime.datetime.strptime(str(row[2]), "%d.%m.%y")
        if datetime.datetime.now() < start_dt:
            await query.edit_message_text("╨в╤Г╤А ╨╡╤Й╤С ╨╜╨╡ ╨╜╨░╤З╨░╨╗╤Б╤П. ╨Ч╨░╨│╨╗╤П╨╜╨╕╤В╨╡ ╨┐╨╛╨╖╨╢╨╡!")
            return
    except Exception:
        pass
    # row: (id, name, start, deadline, end, status, winners, image_filename, image_file_id)
    # 1) ╨Т╤Б╨╡╨│╨┤╨░ ╨┐╤Л╤В╨░╨╡╨╝╤Б╤П ╨╛╤В╨┐╤А╨░╨▓╨╕╤В╤М ╨║╨░╤А╤В╨╕╨╜╨║╤Г ╤В╤Г╤А╨░
    image_sent = False
    image_file_id = row[8] if len(row) >= 9 else ''
    if image_file_id:
        try:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_file_id)
            image_sent = True
        except Exception:
            logger.warning("send_photo by file_id failed in tour_open_callback", exc_info=True)
    if not image_sent:
        try:
            fname = row[7] if len(row) > 7 else ''
            if fname:
                fpath = os.path.join(IMAGES_DIR, fname)
                if os.path.exists(fpath):
                    with open(fpath, 'rb') as fp:
                        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=InputFile(fp, filename=fname))
                        image_sent = True
        except Exception:
            logger.error("send_photo from local file failed in tour_open_callback", exc_info=True)

    # 2) ╨Я╤А╨╛╨▓╨╡╤А╤П╨╡╨╝, ╤Б╨╛╨▒╤А╨░╨╜ ╨╗╨╕ ╤Г╨╢╨╡ ╤Б╨╛╤Б╤В╨░╨▓ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤П ╨┤╨╗╤П ╤Н╤В╨╛╨│╨╛ ╤В╤Г╤А╨░
    user_id = update.effective_user.id if update.effective_user else None
    user_roster = None
    try:
        if user_id:
            user_roster = db.get_user_tour_roster(user_id, row[0])
    except Exception:
        user_roster = None

    if user_roster and isinstance(user_roster, dict) and user_roster.get('roster'):
        # ╨Я╨╛╨║╨░╨╖╨░╤В╤М ╤Б╨╛╤Б╤В╨░╨▓ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤П ╨▓ ╨╖╨░╨┐╤А╨╛╤И╨╡╨╜╨╜╨╛╨╝ ╤Д╨╛╤А╨╝╨░╤В╨╡
        roster = user_roster['roster']
        captain_id = user_roster.get('captain_id')
        spent = user_roster.get('spent', 0)
        try:
            budget = db.get_budget() or 0
        except Exception:
            budget = 0

        def name_club(pid):
            try:
                p = db.get_player_by_id(int(pid))
                if p:
                    # p: (id, name, position, club, nation, age, price)
                    return f"{p[1]} ({p[3]})"
            except Exception:
                pass
            return str(pid)

        # ╨Т╤А╨░╤В╨░╤А╤М
        goalie_line = ""
        try:
            gid = roster.get('goalie')
            if gid:
                goalie_line = name_club(gid)
        except Exception:
            pass

        # ╨Ч╨░╤Й╨╕╤В╨╜╨╕╨║╨╕
        defenders_line = ""
        try:
            dids = roster.get('defenders', []) or []
            defenders_line = " - ".join([name_club(x) for x in dids if x])
        except Exception:
            pass

        # ╨Э╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╡
        forwards_line = ""
        try:
            fids = roster.get('forwards', []) or []
            forwards_line = " - ".join([name_club(x) for x in fids if x])
        except Exception:
            pass

        # ╨Ъ╨░╨┐╨╕╤В╨░╨╜
        captain_line = ""
        try:
            if captain_id:
                captain_line = name_club(captain_id)
        except Exception:
            pass

        lines = [
            goalie_line,
            defenders_line,
            forwards_line,
            "",
            f"╨Ъ╨░╨┐╨╕╤В╨░╨╜: {captain_line}" if captain_line else "╨Ъ╨░╨┐╨╕╤В╨░╨╜: тАФ",
            f"╨Я╨╛╤В╤А╨░╤З╨╡╨╜╨╛: {spent}/{budget}",
        ]
        text = "\n".join([l for l in lines if l is not None])
        # ╨Х╤Б╨╗╨╕ ╨┤╨╡╨┤╨╗╨░╨╣╨╜ ╨╡╤Й╤С ╨╜╨╡ ╨╕╤Б╤В╤С╨║ тАФ ╨┐╨╛╨║╨░╨╖╨░╤В╤М ╨║╨╜╨╛╨┐╨║╤Г "╨Я╨╡╤А╨╡╤Б╨╛╨▒╤А╨░╤В╤М ╤Б╨╛╤Б╤В╨░╨▓"
        reply_markup = None
        try:
            import datetime
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            try:
                from zoneinfo import ZoneInfo
                now = datetime.datetime.now(ZoneInfo("Europe/Moscow"))
            except Exception:
                now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
            deadline_dt = datetime.datetime.strptime(str(row[3]), "%d.%m.%y %H:%M")
            # Treat deadline as MSK time
            try:
                from zoneinfo import ZoneInfo as _ZI
                deadline_dt = deadline_dt.replace(tzinfo=_ZI("Europe/Moscow"))
            except Exception:
                # Fallback: naive but aligned by shifting now above
                pass
            if now < deadline_dt:
                reply_markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton('╨Я╨╡╤А╨╡╤Б╨╛╨▒╤А╨░╤В╤М ╤Б╨╛╤Б╤В╨░╨▓', callback_data='restart_tour')]]
                )
        except Exception:
            reply_markup = None
        try:
            await query.edit_message_text(text, reply_markup=reply_markup)
        except Exception:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)
        return ConversationHandler.END if 'ConversationHandler' in globals() else None
    else:
        # ╨б╨╛╤Б╤В╨░╨▓╨░ ╨╜╨╡╤В тАФ ╨┐╨╛╨║╨░╨╖╨░╤В╤М ╨╕╨╜╤Д╨╛ ╨╕ ╨┐╤А╨╡╨┤╨╗╨╛╨╢╨╕╤В╤М ╨╜╨░╤З╨░╤В╤М ╤Б╨▒╨╛╤А╨║╤Г ╤З╨╡╤А╨╡╨╖ entry-point ╨║╨╜╨╛╨┐╨║╨╛╨╣
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        text = (
            f"╨в╤Г╤А #{row[0]} тАФ {row[1]}\n"
            f"╨б╤В╨░╤В╤Г╤Б: {row[5]}\n"
            f"╨б╤В╨░╤А╤В: {row[2]}\n╨Ф╨╡╨┤╨╗╨░╨╣╨╜: {row[3]}\n╨Ю╨║╨╛╨╜╤З╨░╨╜╨╕╨╡: {row[4]}\n\n"
            f"╨Э╨░╨╢╨╝╨╕╤В╨╡ ╨║╨╜╨╛╨┐╨║╤Г ╨╜╨╕╨╢╨╡, ╤З╤В╨╛╨▒╤Л ╨╜╨░╤З╨░╤В╤М ╤Б╨▒╨╛╤А╨║╤Г ╤Б╨╛╤Б╤В╨░╨▓╨░."
        )
        # Show button only if before deadline (MSK)
        show_button = False
        try:
            import datetime
            try:
                from zoneinfo import ZoneInfo
                now = datetime.datetime.now(ZoneInfo("Europe/Moscow"))
            except Exception:
                now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
            deadline_dt = datetime.datetime.strptime(str(row[3]), "%d.%m.%y %H:%M")
            try:
                from zoneinfo import ZoneInfo as _ZI
                deadline_dt = deadline_dt.replace(tzinfo=_ZI("Europe/Moscow"))
            except Exception:
                pass
            show_button = now < deadline_dt
        except Exception:
            show_button = False
        if show_button:
            keyboard = [[InlineKeyboardButton("╨б╨╛╨▒╤А╨░╤В╤М ╤Б╨╛╤Б╤В╨░╨▓", callback_data=f"tour_build_{row[0]}")]]
            rm = InlineKeyboardMarkup(keyboard)
        else:
            rm = None
            text = (
                f"╨в╤Г╤А #{row[0]} тАФ {row[1]}\n"
                f"╨б╤В╨░╤В╤Г╤Б: {row[5]}\n"
                f"╨б╤В╨░╤А╤В: {row[2]}\n╨Ф╨╡╨┤╨╗╨░╨╣╨╜: {row[3]}\n╨Ю╨║╨╛╨╜╤З╨░╨╜╨╕╨╡: {row[4]}\n\n"
                f"╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗. ╨б╨▒╨╛╤А ╤Б╨╛╤Б╤В╨░╨▓╨░ ╨╖╨░╨║╤А╤Л╤В."
            )
        try:
            await query.edit_message_text(text, reply_markup=rm)
        except Exception:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=rm)
        # ╨Э╨╡ ╨░╨║╤В╨╕╨▓╨╕╤А╤Г╨╡╨╝ CH ╨╜╨░╨┐╤А╤П╨╝╤Г╤О тАФ ╨▓╤Е╨╛╨┤ ╤З╨╡╤А╨╡╨╖ ╨║╨╜╨╛╨┐╨║╤Г 'tour_build_<id>'
        return


async def tour_build_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """╨б╤В╨░╤А╤В ╤Б╨▒╨╛╤А╨║╨╕ ╤Б╨╛╤Б╤В╨░╨▓╨░ ╨┐╨╛ ╨▓╤Л╨▒╤А╨░╨╜╨╜╨╛╨╝╤Г ╤В╤Г╤А╤Г: ╨┤╨╡╨╗╨╡╨│╨╕╤А╤Г╨╡╨╝ ╨▓ tour_start ╨║╨░╨║ entry-point."""
    query = update.callback_query
    await query.answer()
    # ╨Ь╨╛╨╢╨╜╨╛ ╤Б╨╛╤Е╤А╨░╨╜╨╕╤В╤М ╨▓╤Л╨▒╤А╨░╨╜╨╜╤Л╨╣ tour_id, ╨╡╤Б╨╗╨╕ ╨┐╨╛╨╜╨░╨┤╨╛╨▒╨╕╤В╤Б╤П ╨▓ ╨▒╤Г╨┤╤Г╤Й╨╡╨╝
    try:
        tid = int(query.data.replace('tour_build_', ''))
        context.user_data['selected_tour_id'] = tid
    except Exception:
        tid = None
    # ╨Ч╨░╨┐╤Г╤Б╨║╨░╨╡╨╝ ╤Б╤Ж╨╡╨╜╨░╤А╨╕╨╣ ╤Б╨▒╨╛╤А╨║╨╕ ╤Б╨╛╤Б╤В╨░╨▓╨░
    return await tour_start(update, context)


# --- CHALLENGE ---
async def challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    # ╨в╨╛╨╗╤М╨║╨╛ ╨┤╨╗╤П ╨┐╨╛╨┤╨┐╨╕╤Б╤З╨╕╨║╨╛╨▓
    try:
        from db import is_subscription_active
        if not is_subscription_active(user.id):
            await update.message.reply_text("╨д╤Г╨╜╨║╤Ж╨╕╤П ╨┤╨╛╤Б╤В╤Г╨┐╨╜╨░ ╤В╨╛╨╗╤М╨║╨╛ ╨┐╨╛╨┤╨┐╨╕╤Б╤З╨╕╨║╨░╨╝. ╨Ю╤Д╨╛╤А╨╝╨╕╤В╨╡ ╨┐╨╛╨┤╨┐╨╕╤Б╨║╤Г: /subscribe")
            return
    except Exception:
        await update.message.reply_text("╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨┐╤А╨╛╨▓╨╡╤А╨╕╤В╤М ╨┐╨╛╨┤╨┐╨╕╤Б╨║╤Г. ╨Я╨╛╨┐╤А╨╛╨▒╤Г╨╣╤В╨╡ ╨┐╨╛╨╖╨╢╨╡ ╨╕╨╗╨╕ ╨╛╤Д╨╛╤А╨╝╨╕╤В╨╡ /subscribe.")
        return

    # ╨б╨┐╨╕╤Б╨╛╨║ ╨┤╨╛╤Б╤В╤Г╨┐╨╜╤Л╤Е ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╨╡╨╣: ╨▓╤Б╨╡ ╤Б╨╛ ╤Б╤В╨░╤В╤Г╤Б╨╛╨╝ "╨░╨║╤В╨╕╨▓╨╡╨╜" ╨╕ "╨▓ ╨╕╨│╤А╨╡". ╨Х╤Б╨╗╨╕ ╤В╨░╨║╨╕╤Е ╨╜╨╡╤В тАФ ╨┐╨╛╨║╨░╨╖╨░╤В╤М ╨┐╨╛╤Б╨╗╨╡╨┤╨╜╨╕╨╣ "╨╖╨░╨▓╨╡╤А╤И╨╡╨╜".
    challenges = []
    try:
        challenges = db.get_all_challenges() or []
    except Exception:
        challenges = []

    active_or_play = [c for c in challenges if len(c) > 5 and c[5] in ("╨░╨║╤В╨╕╨▓╨╡╨╜", "╨▓ ╨╕╨│╤А╨╡")]
    last_finished = None
    if challenges:
        # ╨▓╤Л╨▒╤А╨░╤В╤М ╨┐╨╛╤Б╨╗╨╡╨┤╨╜╨╕╨╣ ╨╖╨░╨▓╨╡╤А╤И╨╡╨╜╨╜╤Л╨╣ ╨┐╨╛ end_date
        try:
            import datetime
            finished = [c for c in challenges if len(c) > 5 and c[5] == "╨╖╨░╨▓╨╡╤А╤И╨╡╨╜"]
            def parse_iso(s):
                try:
                    return datetime.datetime.fromisoformat(str(s))
                except Exception:
                    return datetime.datetime.min
            if finished:
                last_finished = sorted(finished, key=lambda c: parse_iso(c[3]) or datetime.datetime.min)[-1]
        except Exception:
            pass

    list_to_show = active_or_play if active_or_play else ([last_finished] if last_finished else [])

    if not list_to_show:
        await update.message.reply_text("╨б╨╡╨╣╤З╨░╤Б ╨╜╨╡╤В ╨┤╨╛╤Б╤В╤Г╨┐╨╜╤Л╤Е ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╨╡╨╣. ╨Ч╨░╨│╨╗╤П╨╜╨╕╤В╨╡ ╨┐╨╛╨╖╨╢╨╡.")
        return

    lines = ["*╨Ф╨╛╤Б╤В╤Г╨┐╨╜╤Л╨╡ ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╨╕:*"]
    # ╨Т╤Б╨┐╨╛╨╝╨╛╨│╨░╤В╨╡╨╗╤М╨╜╨░╤П ╤Д╤Г╨╜╨║╤Ж╨╕╤П: ISO -> ╤В╨╡╨║╤Б╤В ╨▓ ╨Ь╨б╨Ъ (Europe/Moscow)
    def iso_to_msk_text(dt_str: str) -> str:
        import datetime as _dt
        months = [
            "╤П╨╜╨▓╨░╤А╤П", "╤Д╨╡╨▓╤А╨░╨╗╤П", "╨╝╨░╤А╤В╨░", "╨░╨┐╤А╨╡╨╗╤П", "╨╝╨░╤П", "╨╕╤О╨╜╤П",
            "╨╕╤О╨╗╤П", "╨░╨▓╨│╤Г╤Б╤В╨░", "╤Б╨╡╨╜╤В╤П╨▒╤А╤П", "╨╛╨║╤В╤П╨▒╤А╤П", "╨╜╨╛╤П╨▒╤А╤П", "╨┤╨╡╨║╨░╨▒╤А╤П"
        ]
        if not dt_str:
            return ""
        try:
            dt = _dt.datetime.fromisoformat(str(dt_str))
        except Exception:
            return str(dt_str)
        # ╨б╤З╨╕╤В╨░╨╡╨╝, ╤З╤В╨╛ ╤Е╤А╨░╨╜╨╕╨╝╨╛╨╡ ╨▓╤А╨╡╨╝╤П тАФ UTC (╨╜╨░╨╕╨▓╨╜╨╛╨╡ -> ╨┐╤А╨╛╤Б╤В╨░╨▓╨╕╨╝ UTC)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        else:
            dt = dt.astimezone(_dt.timezone.utc)
        # ╨Я╨╡╤А╨╡╨▓╨╛╨┤ ╨▓ ╨Ь╨б╨Ъ
        try:
            from zoneinfo import ZoneInfo  # Python 3.9+
            msk = dt.astimezone(ZoneInfo("Europe/Moscow"))
        except Exception:
            # ╨д╨╛╨╗╨▒╤Н╨║: ╤Д╨╕╨║╤Б╨╕╤А╨╛╨▓╨░╨╜╨╜╤Л╨╣ UTC+3 (╨Ь╨╛╤Б╨║╨▓╨░ ╨▒╨╡╨╖ ╨┐╨╡╤А╨╡╤Е╨╛╨┤╨░)
            msk = dt.astimezone(_dt.timezone(_dt.timedelta(hours=3)))
        day = msk.day
        month_name = months[msk.month - 1]
        time_part = msk.strftime("%H:%M")
        return f"{day} {month_name} {time_part} (╨╝╤Б╨║)"
    buttons = []
    for c in list_to_show:
        # c: (id, start, deadline, end, image_filename, status, [image_file_id])
        cid = c[0]
        deadline = c[2]
        end = c[3]
        status = c[5] if len(c) > 5 else ''
        if status == '╨╖╨░╨▓╨╡╤А╤И╨╡╨╜':
            line = f"ЁЯФ║ тДЦ{cid} [╨╖╨░╨▓╨╡╤А╤И╨╡╨╜] ╨┐╨╛╤Б╨╝╨╛╤В╤А╨╡╤В╤М ╤А╨╡╨╖╤Г╨╗╤М╤В╨░╤В╤Л"
        elif status == '╨▓ ╨╕╨│╤А╨╡':
            line = f"ЁЯФ╣ тДЦ{cid} [╨╜╨░╤З╨░╨╗╤Б╤П] ╨┐╨╛╨┤╨▓╨╡╨┤╨╡╨╜╨╕╨╡ ╨╕╤В╨╛╨│╨╛╨▓: {iso_to_msk_text(end)}"
        elif status == '╨░╨║╤В╨╕╨▓╨╡╨╜':
            line = f"ЁЯФ╕ тДЦ{cid} [╤Б╨▒╨╛╤А ╤Б╨╛╤Б╤В╨░╨▓╨╛╨▓] ╨┤╨╡╨┤╨╗╨░╨╣╨╜ ╤Б╨▒╨╛╤А╨║╨╕ ╤Б╨╛╤Б╤В╨░╨▓╨░: {iso_to_msk_text(deadline)}"
        else:
            line = f"тДЦ{cid} [{status}]"
        lines.append(line)
        buttons.append([InlineKeyboardButton(f"╨Ю╤В╨║╤А╤Л╤В╤М #{cid}", callback_data=f"challenge_open_{cid}")])

    await update.message.reply_text("\n\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')


async def challenge_open_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    try:
        cid = int(data.replace("challenge_open_", ""))
    except Exception:
        await query.edit_message_text("╨Э╨╡╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Л╨╣ ╨▓╤Л╨▒╨╛╤А ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╨░.")
        return

    # ╨Э╨░╨╣╨┤╨╡╨╝ ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢ ╨┐╨╛ id
    ch = None
    try:
        rows = db.get_all_challenges() or []
        for r in rows:
            if r[0] == cid:
                ch = r
                break
    except Exception:
        ch = None
    if not ch:
        await query.edit_message_text("╨з╨╡╨╗╨╗╨╡╨╜╨┤╨╢ ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜.")
        return

    # ╨Я╨╛╨┐╤А╨╛╨▒╤Г╨╡╨╝ ╨╛╤В╨┐╤А╨░╨▓╨╕╤В╤М ╨║╨░╤А╤В╨╕╨╜╨║╤Г ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╨░ ╨║╨░╨║ ╤Д╨╛╤В╨╛
    image_sent = False
    image_file_id = ch[6] if len(ch) >= 7 else ''
    if image_file_id:
        try:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_file_id)
            image_sent = True
        except Exception:
            logger.warning("send_photo by file_id failed in open_callback", exc_info=True)
    if not image_sent:
        try:
            fname = ch[4] if len(ch) > 4 else ''
            if fname:
                fpath = os.path.join(IMAGES_DIR, fname)
                if os.path.exists(fpath):
                    with open(fpath, 'rb') as fp:
                        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=InputFile(fp, filename=fname))
                        image_sent = True
        except Exception:
            logger.error("send_photo from local file failed in open_callback", exc_info=True)

    # ╨Х╤Б╨╗╨╕ ╤Г ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤П ╤Г╨╢╨╡ ╨╡╤Б╤В╤М ╨╖╨░╨┐╨╕╤Б╤М ╨╜╨░ ╤Н╤В╨╛╤В ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢ тАФ ╨┐╨╛╨║╨░╨╖╨░╤В╤М ╤В╨╡╨║╤Г╤Й╨╕╨╣ ╤Б╨╛╤Б╤В╨░╨▓ ╨╕ ╨║╨╜╨╛╨┐╨║╨╕ ╨Ю╤В╨╝╨╡╨╜╨╕╤В╤М/╨Я╨╡╤А╨╡╤Б╨╛╨▒╤А╨░╤В╤М
    uid = update.effective_user.id if update.effective_user else None
    entry = None
    try:
        if uid:
            entry = db.challenge_get_entry(ch[0], uid)
    except Exception:
        entry = None

    status = ch[5] if len(ch) > 5 else ''
    # ╨а╨░╨╖╤А╨╡╤И╨░╨╡╨╝ ╤Б╨▒╨╛╤А╨║╤Г ╤Б╨╛╤Б╤В╨░╨▓╨░ ╤В╨╛╨╗╤М╨║╨╛ ╨║╨╛╨│╨┤╨░ ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢ ╨░╨║╤В╨╕╨▓╨╡╨╜ (╨╝╨╡╨╢╨┤╤Г start ╨╕ deadline).
    # ╨б╤В╨░╤В╤Г╤Б ╤Г╨╢╨╡ ╨┐╨╡╤А╨╡╤Б╤З╨╕╤В╤Л╨▓╨░╨╡╤В╤Б╤П ╨╜╨░ ╤З╤В╨╡╨╜╨╕╨╕ ╨▓ db.py, ╨┐╨╛╤Н╤В╨╛╨╝╤Г ╨╜╨╡ ╨┐╨╡╤А╨╡╤Б╤З╨╕╤В╤Л╨▓╨░╨╡╨╝ ╨▓╤А╨╡╨╝╤П ╨╖╨┤╨╡╤Б╤М ╨┐╨╛╨▓╤В╨╛╤А╨╜╨╛.
    if (status or '').lower() != '╨░╨║╤В╨╕╨▓╨╡╨╜':
        await query.edit_message_text("╨з╨╡╨╗╨╗╨╡╨╜╨┤╨╢ ╨╜╨╡╨┤╨╛╤Б╤В╤Г╨┐╨╡╨╜: ╨╗╨╕╨▒╨╛ ╨╡╤Й╤С ╨╜╨╡ ╨╜╨░╤З╨░╨╗╤Б╤П, ╨╗╨╕╨▒╨╛ ╨┤╨╡╨┤╨╗╨░╨╣╨╜ ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗.")
        return
    if entry:
        # ╨Х╤Б╨╗╨╕ ╨╖╨░╨┐╨╕╤Б╤М ╨╛╤В╨╝╨╡╨╜╨╡╨╜╨░/╨▓╨╛╨╖╨▓╤А╨░╤Й╨╡╨╜╨░ тАФ ╤Б╤З╨╕╤В╨░╨╡╨╝, ╤З╤В╨╛ ╨╖╨░╨┐╨╕╤Б╨╕ ╨╜╨╡╤В
        try:
            st = (entry[5] or '').lower()
            if st in ('canceled', 'refunded'):
                entry = None
        except Exception:
            pass

    if entry:
        # entry: (id, stake, forward_id, defender_id, goalie_id, status)
        # ╨б╨╛╤Е╤А╨░╨╜╨╕╨╝ id ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╨░ ╨▓ ╨║╨╛╨╜╤В╨╡╨║╤Б╤В ╨┤╨╗╤П ╨┐╨╛╤Б╨╗╨╡╨┤╤Г╤О╤Й╨╕╤Е ╨┤╨╡╨╣╤Б╤В╨▓╨╕╨╣ (╨Ю╤В╨╝╨╡╨╜╨╕╤В╤М/╨Я╨╡╤А╨╡╤Б╨╛╨▒╤А╨░╤В╤М)
        context.user_data['challenge_id'] = ch[0]
        fwd_id = entry[2]
        d_id = entry[3]
        g_id = entry[4]
        try:
            fwd = db.get_player_by_id(fwd_id) if fwd_id else None
            d = db.get_player_by_id(d_id) if d_id else None
            g = db.get_player_by_id(g_id) if g_id else None
            def fmt(p):
                return f"{p[1]} ({p[3]})" if p else "тАФ"
            picked_line = f"{fmt(fwd)} - {fmt(d)} - {fmt(g)}"
        except Exception:
            picked_line = "тАФ"
        stake = entry[1]
        # ╨Ы╨╛╨║╨░╨╗╤М╨╜╤Л╨╣ ╤Д╨╛╤А╨╝╨░╤В╤В╨╡╤А ╨Ь╨б╨Ъ
        def iso_to_msk_text(dt_str: str) -> str:
            import datetime as _dt
            months = [
                "╤П╨╜╨▓╨░╤А╤П", "╤Д╨╡╨▓╤А╨░╨╗╤П", "╨╝╨░╤А╤В╨░", "╨░╨┐╤А╨╡╨╗╤П", "╨╝╨░╤П", "╨╕╤О╨╜╤П",
                "╨╕╤О╨╗╤П", "╨░╨▓╨│╤Г╤Б╤В╨░", "╤Б╨╡╨╜╤В╤П╨▒╤А╤П", "╨╛╨║╤В╤П╨▒╤А╤П", "╨╜╨╛╤П╨▒╤А╤П", "╨┤╨╡╨║╨░╨▒╤А╤П"
            ]
            if not dt_str:
                return "тАФ"
            try:
                dt = _dt.datetime.fromisoformat(str(dt_str))
            except Exception:
                return str(dt_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_dt.timezone.utc)
            else:
                dt = dt.astimezone(_dt.timezone.utc)
            try:
                from zoneinfo import ZoneInfo
                msk = dt.astimezone(ZoneInfo("Europe/Moscow"))
            except Exception:
                msk = dt.astimezone(_dt.timezone(_dt.timedelta(hours=3)))
            day = msk.day
            month_name = months[msk.month - 1]
            time_part = msk.strftime("%H:%M")
            return f"{day} {month_name} ╨▓ {time_part} (╨╝╤Б╨║)"

        deadline_text = iso_to_msk_text(ch[2])
        end_text = iso_to_msk_text(ch[3])
        status_display = '╤А╨╡╨│╨╕╤Б╤В╤А╨░╤Ж╨╕╤П ╤Б╨╛╤Б╤В╨░╨▓╨╛╨▓' if (status == '╨░╨║╤В╨╕╨▓╨╡╨╜') else status
        txt = (
            f"╨з╨╡╨╗╨╗╨╡╨╜╨┤╨╢ тДЦ{ch[0]}\n"
            f"╨б╤В╨░╤В╤Г╤Б: {status_display}\n\n"
            f"╨Ф╨╡╨┤╨╗╨░╨╣╨╜: {deadline_text}\n"
            f"╨Я╨╛╨┤╨▓╨╡╨┤╨╡╨╜╨╕╨╡ ╨╕╤В╨╛╨│╨╛╨▓: {end_text}\n\n"
            f"╨Т╨░╤И ╤Б╨╛╤Б╤В╨░╨▓: {picked_line}\n"
            f"╨г╤А╨╛╨▓╨╡╨╜╤М ╨▓╤Л╨╖╨╛╨▓╨░: {stake} HC"
        )
        buttons = [
            [InlineKeyboardButton('╨Ю╤В╨╝╨╡╨╜╨╕╤В╤М', callback_data='challenge_cancel')],
            [InlineKeyboardButton('╨Я╨╡╤А╨╡╤Б╨╛╨▒╤А╨░╤В╤М', callback_data='challenge_reshuffle')],
        ]
        await context.bot.send_message(chat_id=update.effective_chat.id, text=txt, reply_markup=InlineKeyboardMarkup(buttons))
        return

    # ╨Ь╨╡╨╜╤О ╨┤╨╡╨╣╤Б╤В╨▓╨╕╨╣ ╨┐╨╛ ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╤Г (╨╡╤Б╨╗╨╕ ╨╖╨░╨┐╨╕╤Б╨╕ ╨╜╨╡╤В)
    # ╨б╨╛╤Е╤А╨░╨╜╨╕╨╝ id ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╨░ ╨▓ ╨║╨╛╨╜╤В╨╡╨║╤Б╤В ╨┤╨╗╤П ╨▓╨╛╨╖╨╝╨╛╨╢╨╜╨╛╨│╨╛ ╨╜╨░╤З╨░╨╗╨░ ╤Б╨▒╨╛╤А╨║╨╕
    context.user_data['challenge_id'] = ch[0]
    text = (
        f"╨з╨╡╨╗╨╗╨╡╨╜╨┤╨╢ #{ch[0]}\n"
        f"╨б╤В╨░╤В╤Г╤Б: {status}\n"
        f"╨б╤В╨░╤А╤В: {ch[1]}\n╨Ф╨╡╨┤╨╗╨░╨╣╨╜: {ch[2]}\n╨Ю╨║╨╛╨╜╤З╨░╨╜╨╕╨╡: {ch[3]}"
    )
    buttons = [[InlineKeyboardButton("╨Ш╨╜╤Д╨╛", callback_data=f"challenge_info_{ch[0]}")]]
    if status == "╨░╨║╤В╨╕╨▓╨╡╨╜":
        buttons.append([InlineKeyboardButton("╨б╨╛╨▒╤А╨░╤В╤М ╤Б╨╛╤Б╤В╨░╨▓", callback_data=f"challenge_build_{ch[0]}")])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=InlineKeyboardMarkup(buttons))


async def challenge_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        cid = int(query.data.replace("challenge_info_", ""))
    except Exception:
        await query.edit_message_text("╨Э╨╡╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Л╨╣ ╨╖╨░╨┐╤А╨╛╤Б.")
        return
    # ╨Э╨░╨╣╨┤╨╡╨╝ ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢
    ch = None
    try:
        rows = db.get_all_challenges() or []
        for r in rows:
            if r[0] == cid:
                ch = r
                break
    except Exception:
        ch = None
    if not ch:
        await query.edit_message_text("╨з╨╡╨╗╨╗╨╡╨╜╨┤╨╢ ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜.")
        return
    status = ch[5] if len(ch) > 5 else ''
    txt = (
        f"╨Ш╨╜╤Д╨╛╤А╨╝╨░╤Ж╨╕╤П ╨┐╨╛ ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╤Г #{ch[0]}\n"
        f"╨б╤В╨░╤В╤Г╤Б: {status}\n"
        f"╨б╤В╨░╤А╤В: {ch[1]}\n╨Ф╨╡╨┤╨╗╨░╨╣╨╜: {ch[2]}\n╨Ю╨║╨╛╨╜╤З╨░╨╜╨╕╨╡: {ch[3]}\n\n"
        f"╨Х╤Б╨╗╨╕ ╤Б╤В╨░╤В╤Г╤Б '╨░╨║╤В╨╕╨▓╨╡╨╜' тАФ ╨╝╨╛╨╢╨╡╤В╨╡ ╤Б╨╛╨▒╤А╨░╤В╤М ╤Б╨╛╤Б╤В╨░╨▓."
    )
    await query.edit_message_text(txt)

def _parse_shop_items(text: str):
    items = []
    if not text:
        return items
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        if not (line.startswith('ЁЯФ╕') or line.startswith('тАв') or line.startswith('-')):
            continue
        # ╨г╨▒╨╕╤А╨░╨╡╨╝ ╨╝╨░╤А╨║╨╡╤А
        raw = line.lstrip('ЁЯФ╕').lstrip('тАв').lstrip('-').strip()
        # ╨а╨░╨╖╨┤╨╡╨╗╨╕╤В╨╡╨╗╤М тАФ ╨╝╨╛╨╢╨╡╤В ╨▒╤Л╤В╤М ╨┤╨╗╨╕╨╜╨╜╨╛╨╡ ╤В╨╕╤А╨╡ ╨╕╨╗╨╕ ╨┤╨╡╤Д╨╕╤Б
        sep = 'тАФ' if 'тАФ' in raw else (' - ' if ' - ' in raw else '-')
        if sep not in raw:
            # ╨Я╤А╨╛╨┐╤Г╤Б╨║╨░╨╡╨╝ ╨╜╨╡╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Л╨╡ ╤Б╤В╤А╨╛╨║╨╕
            continue
        name, price = raw.split(sep, 1)
        name = name.strip()
        price = price.strip()
        if name:
            items.append((name, price))
    return items

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """╨Я╨╛╨║╨░╨╖╨░╤В╤М ╤Б╨╛╨┤╨╡╤А╨╢╨╕╨╝╨╛╨╡ ╨╝╨░╨│╨░╨╖╨╕╨╜╨░: ╤В╨╡╨║╤Б╤В + ╨║╨░╤А╤В╨╕╨╜╨║╨░ + ╨╕╨╜╨╗╨░╨╣╨╜-╨║╨╜╨╛╨┐╨║╨╕ ╤В╨╛╨▓╨░╤А╨╛╨▓."""
    try:
        text, image_filename, image_file_id = db.get_shop_content()
    except Exception as e:
        await update.message.reply_text(f"╨Ю╤И╨╕╨▒╨║╨░ ╨┐╨╛╨╗╤Г╤З╨╡╨╜╨╕╤П ╨┤╨░╨╜╨╜╤Л╤Е ╨╝╨░╨│╨░╨╖╨╕╨╜╨░: {e}")
        return
    if not text and not image_filename and not image_file_id:
        await update.message.reply_text("╨Ь╨░╨│╨░╨╖╨╕╨╜ ╨┐╨╛╨║╨░ ╨┐╤Г╤Б╤В. ╨Ч╨░╨│╨╗╤П╨╜╨╕╤В╨╡ ╨┐╨╛╨╖╨╢╨╡.")
        return
    # ╨Я╨╛╤Б╤В╤А╨╛╨╕╨╝ ╨╕╨╜╨╗╨░╨╣╨╜-╨║╨╜╨╛╨┐╨║╨╕ ╨╕╨╖ ╤В╨╡╨║╤Б╤В╨░
    items = _parse_shop_items(text or '')
    buttons = []
    for idx, (name, price) in enumerate(items, start=1):
        label = f"{name} тАФ {price}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"shop_item_{idx}")])
    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    caption = text if text else None
    # ╨Я╨╛╨┐╤Л╤В╨░╨╡╨╝╤Б╤П ╨╛╤В╨┐╤А╨░╨▓╨╕╤В╤М ╤Д╨╛╤В╨╛ ╨┐╨╛ file_id
    if image_file_id:
        try:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_file_id, caption=caption, reply_markup=reply_markup)
            return
        except Exception:
            logger.warning("send_photo by file_id failed in /shop", exc_info=True)
    # ╨Я╨╛╨┐╤А╨╛╨▒╤Г╨╡╨╝ ╨╛╤В╨┐╤А╨░╨▓╨╕╤В╤М ╨╗╨╛╨║╨░╨╗╤М╨╜╤Л╨╣ ╤Д╨░╨╣╨╗
    if image_filename:
        fpath = os.path.join(IMAGES_DIR, image_filename)
        if os.path.exists(fpath):
            try:
                with open(fpath, 'rb') as fp:
                    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=InputFile(fp, filename=image_filename), caption=caption, reply_markup=reply_markup)
                    return
            except Exception:
                logger.error("send_photo from local file failed in /shop", exc_info=True)
    # ╨Х╤Б╨╗╨╕ ╤Д╨╛╤В╨╛ ╨╜╨╡ ╨┐╨╛╨╗╤Г╤З╨╕╨╗╨╛╤Б╤М тАФ ╨╛╤В╨┐╤А╨░╨▓╨╕╨╝ ╨┐╤А╨╛╤Б╤В╨╛ ╤В╨╡╨║╤Б╤В
    if caption:
        await update.message.reply_text(caption, reply_markup=reply_markup)
    else:
        await update.message.reply_text("╨Ь╨░╨│╨░╨╖╨╕╨╜ ╨╜╨╡╨┤╨╛╤Б╤В╤Г╨┐╨╡╨╜.")

async def shop_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # shop_item_<n>
    try:
        await query.edit_message_reply_markup(reply_markup=query.message.reply_markup)
    except BadRequest as e:
        # ╨Ш╨│╨╜╨╛╤А╨╕╤А╤Г╨╡╨╝ 'Message is not modified'
        if 'Message is not modified' not in str(e):
            raise
    try:
        idx = int(data.replace('shop_item_', ''))
    except Exception:
        idx = None
    # ╨Я╨╛╨╗╤Г╤З╨╕╨╝ ╤Б╨┐╨╕╤Б╨╛╨║ ╤В╨╛╨▓╨░╤А╨╛╨▓ ╨╖╨░╨╜╨╛╨▓╨╛ ╨╕╨╖ ╨С╨Ф
    try:
        text, _, _ = db.get_shop_content()
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"╨Ю╤И╨╕╨▒╨║╨░ ╤З╤В╨╡╨╜╨╕╤П ╨╝╨░╨│╨░╨╖╨╕╨╜╨░: {e}")
        return
    items = _parse_shop_items(text or '')
    if not idx or idx < 1 or idx > len(items):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="╨Э╨╡╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Л╨╣ ╨▓╤Л╨▒╨╛╤А ╤В╨╛╨▓╨░╤А╨░.")
        return
    name, price_str = items[idx - 1]
    # ╨Ш╨╖╨▓╨╗╨╡╤З╤С╨╝ ╤З╨╕╤Б╨╗╨╛ ╨╕╨╖ ╤Б╤В╤А╨╛╨║╨╕ ╤Ж╨╡╨╜╤Л (╨╜╨░╨┐╤А╨╕╨╝╨╡╤А, '35 000 HC' -> 35000)
    digits = ''.join(ch for ch in price_str if ch.isdigit())
    try:
        price = int(digits) if digits else 0
    except Exception:
        price = 0
    # ╨С╨░╨╗╨░╨╜╤Б ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤П
    user = update.effective_user
    balance = 0
    try:
        row = db.get_user_by_id(user.id)
        if row and len(row) > 3 and isinstance(row[3], (int, float)):
            balance = int(row[3])
        elif row and len(row) > 3:
            # ╨Э╨░ ╤Б╨╗╤Г╤З╨░╨╣, ╨╡╤Б╨╗╨╕ ╤Е╤А╨░╨╜╨╕╤В╤Б╤П ╤Б╤В╤А╨╛╨║╨╛╨╣
            try:
                balance = int(str(row[3]))
            except Exception:
                balance = 0
    except Exception:
        balance = 0
    if price <= 0:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"╨в╨╛╨▓╨░╤А: {name}\n╨ж╨╡╨╜╨░: {price_str}\n\n╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╤А╨░╤Б╨┐╨╛╨╖╨╜╨░╤В╤М ╤Ж╨╡╨╜╤Г. ╨б╨▓╤П╨╢╨╕╤В╨╡╤Б╤М ╤Б ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╨╛╨╝.")
        return
    if balance < price:
        need = price - balance
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"╨в╨╛╨▓╨░╤А: {name}\n╨ж╨╡╨╜╨░: {price_str}\n\n"
                f"╨Э╨╡╨┤╨╛╤Б╤В╨░╤В╨╛╤З╨╜╨╛ ╤Б╤А╨╡╨┤╤Б╤В╨▓: ╨╜╨╡ ╤Е╨▓╨░╤В╨░╨╡╤В {need} HC.\n"
                f"╨Т╤Л ╨╝╨╛╨╢╨╡╤В╨╡ ╨┐╨╛╨┤╨║╨╗╤О╤З╨╕╤В╤М ╨┐╨╛╨┤╨┐╨╕╤Б╨║╤Г /subscribe ╨╖╨░ 299 ╤А╤Г╨▒/╨╝╨╡╤Б╤П╤Ж, ╤З╤В╨╛╨▒╤Л ╨▒╤Л╤Б╤В╤А╨╡╨╡ ╨╜╨░╨║╨░╨┐╨╗╨╕╨▓╨░╤В╤М HC."
            )
        )
        return
    # ╨С╨░╨╗╨░╨╜╤Б╨░ ╨┤╨╛╤Б╤В╨░╤В╨╛╤З╨╜╨╛ тАФ ╨┐╤А╨╛╨▒╤Г╨╡╨╝ ╤Б╨┐╨╕╤Б╨░╤В╤М HC
    try:
        db.update_hc_balance(user.id, -price)
        new_balance = max(0, balance - price)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╤Б╨┐╨╕╤Б╨░╤В╤М HC: {e}")
        return
    # ╨б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╡ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤О
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"╨в╨╛╨▓╨░╤А: {name}\n╨ж╨╡╨╜╨░: {price_str}\n\n"
            f"╨Я╨╛╨║╤Г╨┐╨║╨░ ╨┐╤А╨╕╨╜╤П╤В╨░! ╨б ╨▓╨░╤И╨╡╨│╨╛ ╨▒╨░╨╗╨░╨╜╤Б╨░ ╤Б╨┐╨╕╤Б╨░╨╜╨╛ {price} HC.\n"
            f"╨в╨╡╨║╤Г╤Й╨╕╨╣ ╨▒╨░╨╗╨░╨╜╤Б: {new_balance} HC."
        )
    )
    # ╨г╨▓╨╡╨┤╨╛╨╝╨╗╨╡╨╜╨╕╨╡ ╨░╨┤╨╝╨╕╨╜╨░(╨╛╨▓)
    try:
        admin_text = (
            "ЁЯЫТ ╨Ч╨░╨┐╤А╨╛╤Б ╨╜╨░ ╨┐╨╛╨║╤Г╨┐╨║╤Г\n\n"
            f"╨Я╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤М: {user.full_name} (@{user.username or '-'}, id={user.id})\n"
            f"╨в╨╛╨▓╨░╤А: {name}\n"
            f"╨ж╨╡╨╜╨░: {price_str}\n"
            f"╨б╨┐╨╕╤Б╨░╨╜╨╛: {price} HC\n"
            f"╨Э╨╛╨▓╤Л╨╣ ╨▒╨░╨╗╨░╨╜╤Б: {new_balance} HC\n"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text)
    except Exception:
        logger.warning("Failed to notify admin about shop purchase", exc_info=True)


async def challenge_build_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        cid = int(query.data.replace("challenge_build_", ""))
    except Exception:
        await query.edit_message_text("╨Э╨╡╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Л╨╣ ╨╖╨░╨┐╤А╨╛╤Б.")
        return
    # ╨Я╤А╨╛╨▓╨╡╤А╨╕╨╝, ╤З╤В╨╛ ╨▓╤Л╨▒╤А╨░╨╜╨╜╤Л╨╣ ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢ ╨░╨║╤В╨╕╨▓╨╡╨╜
    ch = None
    try:
        rows = db.get_all_challenges() or []
        for r in rows:
            if r[0] == cid:
                ch = r
                break
    except Exception:
        ch = None
    if not ch:
        await query.edit_message_text("╨з╨╡╨╗╨╗╨╡╨╜╨┤╨╢ ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜.")
        return
    status = ch[5] if len(ch) > 5 else ''
    if (status or '').lower() != 'ръЄштхэ':
        await query.edit_message_text("╤сюЁ ёюёЄртр эхфюёЄєяхэ: ўхыыхэфц эх ръЄштхэ.")
        return
    # ╨Я╨╡╤А╨╡╨╕╤Б╨┐╨╛╨╗╤М╨╖╤Г╨╡╨╝ ╤В╨╡╨║╤Г╤Й╤Г╤О ╨╝╨╡╤Е╨░╨╜╨╕╨║╤Г: ╨▓╤Л╨▒╨╛╤А ╤Г╤А╨╛╨▓╨╜╤П ╨▓╤Л╨╖╨╛╨▓╨░
    text = (
        "╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╤Г╤А╨╛╨▓╨╡╨╜╤М ╨▓╤Л╨╖╨╛╨▓╨░ ╨┤╨╗╤П ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╨░:\n\n"
        "тЪбя╕П 50 HC\nтЪбя╕П 100 HC\nтЪбя╕П 500 HC"
    )
    keyboard = [
        [
            InlineKeyboardButton('тЪбя╕П 50 HC', callback_data='challenge_level_50'),
            InlineKeyboardButton('тЪбя╕П 100 HC', callback_data='challenge_level_100'),
            InlineKeyboardButton('тЪбя╕П 500 HC', callback_data='challenge_level_500'),
        ]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def challenge_level_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    # Guard: deadline not passed for current challenge
    try:
        cid_guard = context.user_data.get('challenge_id')
        if cid_guard and _challenge_deadline_passed(cid_guard):
            await query.edit_message_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╨░ ╨┐╤А╨╛╤И╤С╨╗. ╨б╨▒╨╛╤А ╤Б╨╛╤Б╤В╨░╨▓╨░ ╨╖╨░╨║╤А╤Л╤В.")
            return
    except Exception:
        pass
    level = data.replace('challenge_level_', '')
    try:
        level_int = int(level)
    except Exception:
        await query.edit_message_text("╨Э╨╡╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Л╨╣ ╤Г╤А╨╛╨▓╨╡╨╜╤М ╨▓╤Л╨╖╨╛╨▓╨░.")
        return
    user = update.effective_user
    user_row = db.get_user_by_id(user.id)
    balance = user_row[3] if user_row else 0
    if balance < level_int:
        text = (
            f"╨Э╨╡╨┤╨╛╤Б╤В╨░╤В╨╛╤З╨╜╨╛ HC ╨┤╨╗╤П ╤Г╤А╨╛╨▓╨╜╤П {level_int} HC.\n"
            f"╨в╨╡╨║╤Г╤Й╨╕╨╣ ╨▒╨░╨╗╨░╨╜╤Б: {balance} HC.\n\n"
            "╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨┤╨╛╤Б╤В╤Г╨┐╨╜╤Л╨╣ ╤Г╤А╨╛╨▓╨╡╨╜╤М ╨▓╤Л╨╖╨╛╨▓╨░:"
        )
        keyboard = [
            [
                InlineKeyboardButton('тЪбя╕П 50 HC', callback_data='challenge_level_50'),
                InlineKeyboardButton('тЪбя╕П 100 HC', callback_data='challenge_level_100'),
                InlineKeyboardButton('тЪбя╕П 500 HC', callback_data='challenge_level_500'),
            ]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    # ╨С╨░╨╗╨░╨╜╤Б ╨┤╨╛╤Б╤В╨░╤В╨╛╤З╨╡╨╜ тАФ ╤Б╨┐╨╕╤Б╤Л╨▓╨░╨╡╨╝ ╨╕ ╤Б╨╛╨╖╨┤╨░╤С╨╝ ╨╖╨░╤П╨▓╨║╤Г
    cid = context.user_data.get('challenge_id')
    if not cid:
        await query.edit_message_text("╨Ю╤И╨╕╨▒╨║╨░: ╨╜╨╡╤В ╨▓╤Л╨▒╤А╨░╨╜╨╜╨╛╨│╨╛ ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╨░. ╨Ю╤В╨║╤А╨╛╨╣╤В╨╡ ╨╖╨░╨╜╨╛╨▓╨╛ ╤З╨╡╤А╨╡╨╖ /challenge.")
        return
    ok = db.create_challenge_entry_and_charge(cid, user.id, level_int)
    if not ok:
        await query.edit_message_text("╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╤Б╨╛╨╖╨┤╨░╤В╤М ╨╖╨░╤П╨▓╨║╤Г: ╨▓╨╛╨╖╨╝╨╛╨╢╨╜╨╛, ╨╖╨░╨┐╨╕╤Б╤М ╤Г╨╢╨╡ ╤Б╤Г╤Й╨╡╤Б╤В╨▓╤Г╨╡╤В ╨╕╨╗╨╕ ╨╜╨╡╨┤╨╛╤Б╤В╨░╤В╨╛╤З╨╜╨╛ HC.")
        return
    context.user_data['challenge_level'] = level_int
    context.user_data['challenge_remaining_positions'] = ['╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣', '╨╖╨░╤Й╨╕╤В╨╜╨╕╨║', '╨▓╤А╨░╤В╨░╤А╤М']
    # ╨Я╨╛╨║╨░╨╖╨░╤В╤М ╨▓╤Л╨▒╨╛╤А ╨┐╨╛╨╖╨╕╤Ж╨╕╨╕
    buttons = [
        [InlineKeyboardButton('╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣', callback_data='challenge_pick_pos_╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣')],
        [InlineKeyboardButton('╨╖╨░╤Й╨╕╤В╨╜╨╕╨║', callback_data='challenge_pick_pos_╨╖╨░╤Й╨╕╤В╨╜╨╕╨║')],
        [InlineKeyboardButton('╨▓╤А╨░╤В╨░╤А╤М', callback_data='challenge_pick_pos_╨▓╤А╨░╤В╨░╤А╤М')],
    ]
    await query.edit_message_text(
        f"╨г╤А╨╛╨▓╨╡╨╜╤М ╨▓╤Л╨╖╨╛╨▓╨░ ╨▓╤Л╨▒╤А╨░╨╜: {level_int} HC. ╨б ╨▓╨░╤И╨╡╨│╨╛ ╨▒╨░╨╗╨░╨╜╤Б╨░ ╤Б╨┐╨╕╤Б╨░╨╜╨╛ {level_int} HC.\n╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨┐╨╛╨╖╨╕╤Ж╨╕╤О:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def challenge_pick_pos_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Guard: deadline not passed
    try:
        cid_guard = context.user_data.get('challenge_id')
        if cid_guard and _challenge_deadline_passed(cid_guard):
            await query.edit_message_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╨░ ╨┐╤А╨╛╤И╤С╨╗. ╨Т╤Л╨▒╨╛╤А ╨╕╨│╤А╨╛╨║╨╛╨▓ ╨╖╨░╨║╤А╤Л╤В.")
            return
    except Exception:
        pass
    pos = query.data.replace('challenge_pick_pos_', '')
    remaining = context.user_data.get('challenge_remaining_positions', ['╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣', '╨╖╨░╤Й╨╕╤В╨╜╨╕╨║', '╨▓╤А╨░╤В╨░╤А╤М'])
    if pos not in remaining:
        await query.edit_message_text("╨н╤В╨░ ╨┐╨╛╨╖╨╕╤Ж╨╕╤П ╤Г╨╢╨╡ ╨▓╤Л╨▒╤А╨░╨╜╨░. ╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨┤╤А╤Г╨│╤Г╤О.")
        return
    context.user_data['challenge_current_pos'] = pos
    context.user_data['challenge_expect_team'] = True
    await query.edit_message_text(f"╨Т╤Л ╨▓╤Л╨▒╤А╨░╨╗╨╕ ╨┐╨╛╨╖╨╕╤Ж╨╕╤О: {pos}. ╨в╨╡╨┐╨╡╤А╤М ╨▓╨▓╨╡╨┤╨╕╤В╨╡ ╨╜╨░╨╖╨▓╨░╨╜╨╕╨╡ ╨║╨╛╨╝╨░╨╜╨┤╤Л ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╡╨╝.")


async def challenge_team_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Guard: deadline not passed
    try:
        cid_guard = context.user_data.get('challenge_id')
        if cid_guard and _challenge_deadline_passed(cid_guard):
            await update.effective_message.reply_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╨░ ╨┐╤А╨╛╤И╤С╨╗. ╨Т╤Л╨▒╨╛╤А ╨╕╨│╤А╨╛╨║╨╛╨▓ ╨╖╨░╨║╤А╤Л╤В.")
            return
    except Exception:
        pass
    # ╨Ю╨▒╤А╨░╨▒╨░╤В╤Л╨▓╨░╨╡╨╝ ╤В╨╡╨║╤Б╤В ╨╜╨░╨╖╨▓╨░╨╜╨╕╤П ╨║╨╛╨╝╨░╨╜╨┤╤Л ╤В╨╛╨╗╤М╨║╨╛ ╨╡╤Б╨╗╨╕ ╨╛╨╢╨╕╨┤╨░╨╡╨╝
    if not context.user_data.get('challenge_expect_team'):
        return
    team_text = (update.message.text or '').strip()
    context.user_data['challenge_expect_team'] = False
    context.user_data['challenge_team_query'] = team_text
    pos = context.user_data.get('challenge_current_pos')
    # ╨б╨┐╨╕╤Б╨╛╨║ ╨╕╨│╤А╨╛╨║╨╛╨▓ ╨┐╨╛ ╨┐╨╛╨╖╨╕╤Ж╨╕╨╕ ╨╕ ╨╜╨░╨╖╨▓╨░╨╜╨╕╤О ╨║╨╛╨╝╨░╨╜╨┤╤Л
    from db import get_all_players
    all_players = get_all_players()
    team_lower = team_text.lower()
    filtered = [p for p in all_players if (p[2] or '').lower() == pos and team_lower in str(p[3] or '').lower()]
    if not filtered:
        await update.message.reply_text("╨Ш╨│╤А╨╛╨║╨╕ ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜╤Л ╨┐╨╛ ╤Г╨║╨░╨╖╨░╨╜╨╜╤Л╨╝ ╤Д╨╕╨╗╤М╤В╤А╨░╨╝. ╨Я╨╛╨▓╤В╨╛╤А╨╕╤В╨╡ ╨▓╤Л╨▒╨╛╤А ╨┐╨╛╨╖╨╕╤Ж╨╕╨╕.")
        # ╨Т╨╡╤А╨╜╤С╨╝ ╨╝╨╡╨╜╤О ╨┐╨╛╨╖╨╕╤Ж╨╕╨╣ (╨╛╤Б╤В╨░╨▓╤И╨╕╨╡╤Б╤П)
        remaining = context.user_data.get('challenge_remaining_positions', ['╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣', '╨╖╨░╤Й╨╕╤В╨╜╨╕╨║', '╨▓╤А╨░╤В╨░╤А╤М'])
        btns = [[InlineKeyboardButton(x, callback_data=f"challenge_pick_pos_{x}")] for x in remaining]
        await update.message.reply_text("╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨┐╨╛╨╖╨╕╤Ж╨╕╤О:", reply_markup=InlineKeyboardMarkup(btns))
        return
    # ╨Я╨╛╤Б╤В╤А╨╛╨╕╤В╤М ╨║╨╗╨░╨▓╨╕╨░╤В╤Г╤А╤Г ╨╕╨│╤А╨╛╨║╨╛╨▓
    kb = []
    for p in filtered:
        kb.append([InlineKeyboardButton(f"{p[1]} ({p[3]})", callback_data=f"challenge_pick_player_{p[0]}")])
    await update.message.reply_text("╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨╕╨│╤А╨╛╨║╨░:", reply_markup=InlineKeyboardMarkup(kb))


async def challenge_pick_player_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Guard: deadline not passed
    try:
        cid_guard = context.user_data.get('challenge_id')
        if cid_guard and _challenge_deadline_passed(cid_guard):
            await query.edit_message_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╨░ ╨┐╤А╨╛╤И╤С╨╗. ╨Т╤Л╨▒╨╛╤А ╨╕╨│╤А╨╛╨║╨╛╨▓ ╨╖╨░╨║╤А╤Л╤В.")
            return
    except Exception:
        pass
    try:
        pid = int(query.data.replace('challenge_pick_player_', ''))
    except Exception:
        await query.edit_message_text("╨Э╨╡╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Л╨╣ ╨▓╤Л╨▒╨╛╤А ╨╕╨│╤А╨╛╨║╨░.")
        return
    cid = context.user_data.get('challenge_id')
    pos = context.user_data.get('challenge_current_pos')
    if not cid or not pos:
        await query.edit_message_text("╨Ъ╨╛╨╜╤В╨╡╨║╤Б╤В ╨▓╤Л╨▒╨╛╤А╨░ ╤Г╤В╨╡╤А╤П╨╜. ╨Э╨░╤З╨╜╨╕╤В╨╡ ╨╖╨░╨╜╨╛╨▓╨╛: /challenge")
        return
    # ╨б╨╛╤Е╤А╨░╨╜╤П╨╡╨╝ ╨┐╨╕╨║
    try:
        db.challenge_set_pick(cid, update.effective_user.id, pos, pid)
        p = db.get_player_by_id(pid)
        picked_name = f"{p[1]} ({p[3]})" if p else f"id={pid}"
        await query.edit_message_text(f"╨Т╤Л ╨▓╤Л╨▒╤А╨░╨╗╨╕: {picked_name}")
    except Exception as e:
        await query.edit_message_text(f"╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╤Б╨╛╤Е╤А╨░╨╜╨╕╤В╤М ╨▓╤Л╨▒╨╛╤А: {e}")
        return
    # ╨Ю╨▒╨╜╨╛╨▓╨╗╤П╨╡╨╝ ╤Б╨┐╨╕╤Б╨╛╨║ ╨╛╤Б╤В╨░╨▓╤И╨╕╤Е╤Б╤П ╨┐╨╛╨╖╨╕╤Ж╨╕╨╣
    remaining = context.user_data.get('challenge_remaining_positions', ['╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣', '╨╖╨░╤Й╨╕╤В╨╜╨╕╨║', '╨▓╤А╨░╤В╨░╤А╤М'])
    try:
        remaining.remove(pos)
    except ValueError:
        pass
    context.user_data['challenge_remaining_positions'] = remaining
    if remaining:
        # ╨Я╨╛╨║╨░╨╖╨░╤В╤М ╨╛╤Б╤В╨░╨▓╤И╨╕╨╡╤Б╤П ╨┐╨╛╨╖╨╕╤Ж╨╕╨╕
        btns = [[InlineKeyboardButton(x, callback_data=f"challenge_pick_pos_{x}")] for x in remaining]
        await context.bot.send_message(chat_id=update.effective_chat.id, text="╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╤Б╨╗╨╡╨┤╤Г╤О╤Й╤Г╤О ╨┐╨╛╨╖╨╕╤Ж╨╕╤О:", reply_markup=InlineKeyboardMarkup(btns))
        return
    # ╨Т╤Б╨╡ ╤В╤А╨╕ ╨┐╨╛╨╖╨╕╤Ж╨╕╨╕ ╨▓╤Л╨▒╤А╨░╨╜╤Л тАФ ╤Д╨╕╨╜╨░╨╗╨╕╨╖╨░╤Ж╨╕╤П
    try:
        db.challenge_finalize(cid, update.effective_user.id)
    except Exception:
        pass
    # ╨б╨▓╨╛╨┤╨║╨░
    try:
        fwd_id = db.challenge_get_entry(cid, update.effective_user.id)[2]
        d_id = db.challenge_get_entry(cid, update.effective_user.id)[3]
        g_id = db.challenge_get_entry(cid, update.effective_user.id)[4]
        fwd = db.get_player_by_id(fwd_id) if fwd_id else None
        d = db.get_player_by_id(d_id) if d_id else None
        g = db.get_player_by_id(g_id) if g_id else None
        def fmt(p):
            return f"{p[1]} ({p[3]})" if p else "-"
        picked_line = f"{fmt(fwd)} - {fmt(d)} - {fmt(g)}"
    except Exception:
        picked_line = "-"
    # ╨Э╨░╨╣╨┤╤С╨╝ ╨┤╨╡╨┤╨╗╨░╨╣╨╜ ╨╕ ╤Б╤В╨░╨▓╨║╤Г
    ch = None
    try:
        ch = db.get_challenge_by_id(cid)
    except Exception:
        ch = None
    # ╨д╨╛╤А╨╝╨░╤В╨╕╤А╤Г╨╡╨╝ ╨┤╨░╤В╤Г ╨┐╨╛╨┤╨▓╨╡╨┤╨╡╨╜╨╕╤П ╨╕╤В╨╛╨│╨╛╨▓ (╨╕╤Б╨┐╨╛╨╗╤М╨╖╤Г╨╡╨╝ ╨║╨╛╨╜╨╡╤Ж ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╨░ ch[3])
    def iso_to_msk_text(dt_str: str) -> str:
        import datetime as _dt
        months = [
            "╤П╨╜╨▓╨░╤А╤П", "╤Д╨╡╨▓╤А╨░╨╗╤П", "╨╝╨░╤А╤В╨░", "╨░╨┐╤А╨╡╨╗╤П", "╨╝╨░╤П", "╨╕╤О╨╜╤П",
            "╨╕╤О╨╗╤П", "╨░╨▓╨│╤Г╤Б╤В╨░", "╤Б╨╡╨╜╤В╤П╨▒╤А╤П", "╨╛╨║╤В╤П╨▒╤А╤П", "╨╜╨╛╤П╨▒╤А╤П", "╨┤╨╡╨║╨░╨▒╤А╤П"
        ]
        if not dt_str:
            return "тАФ"
        try:
            dt = _dt.datetime.fromisoformat(str(dt_str))
        except Exception:
            return str(dt_str)
        # ╤Б╤З╨╕╤В╨░╨╡╨╝, ╤З╤В╨╛ ╤Е╤А╨░╨╜╨╕╤В╤Б╤П UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        else:
            dt = dt.astimezone(_dt.timezone.utc)
        try:
            from zoneinfo import ZoneInfo
            msk = dt.astimezone(ZoneInfo("Europe/Moscow"))
        except Exception:
            msk = dt.astimezone(_dt.timezone(_dt.timedelta(hours=3)))
        day = msk.day
        month_name = months[msk.month - 1]
        time_part = msk.strftime("%H:%M")
        return f"{day} {month_name} ╨▓ {time_part} (╨╝╤Б╨║)"

    end_iso = ch[3] if ch else ""
    end_text = iso_to_msk_text(end_iso)
    stake = context.user_data.get('challenge_level')
    txt = (
        f"{picked_line}\n"
        f"╨Я╨╛╨┤╨▓╨╡╨┤╨╡╨╜╨╕╨╡ ╨╕╤В╨╛╨│╨╛╨▓: {end_text}\n"
        f"╨Т╨░╤И ╤Г╤А╨╛╨▓╨╡╨╜╤М ╨▓╤Л╨╖╨╛╨▓╨░: {stake} HC"
    )
    buttons = [
        [InlineKeyboardButton('╨Ю╤В╨╝╨╡╨╜╨╕╤В╤М', callback_data='challenge_cancel')],
        [InlineKeyboardButton('╨Я╨╡╤А╨╡╤Б╨╛╨▒╤А╨░╤В╤М', callback_data='challenge_reshuffle')],
    ]
    await context.bot.send_message(chat_id=update.effective_chat.id, text=txt, reply_markup=InlineKeyboardMarkup(buttons))


async def challenge_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = context.user_data.get('challenge_id')
    if not cid:
        await query.edit_message_text("╨Ю╤В╨╝╨╡╨╜╨░ ╨╜╨╡╨┤╨╛╤Б╤В╤Г╨┐╨╜╨░: ╨╜╨╡╤В ╨░╨║╤В╨╕╨▓╨╜╨╛╨╣ ╨╖╨░╨┐╨╕╤Б╨╕.")
        return
    refunded = db.challenge_cancel_and_refund(cid, update.effective_user.id)
    if refunded:
        # ╨Э╨░ ╨▓╤Б╤П╨║╨╕╨╣ ╤Б╨╗╤Г╤З╨░╨╣ ╨╛╤З╨╕╤Б╤В╨╕╨╝ ╨┐╨╕╨║╨╕
        try:
            db.challenge_reset_picks(cid, update.effective_user.id)
        except Exception:
            pass
        await query.edit_message_text("╨Ч╨░╤П╨▓╨║╨░ ╨╛╤В╨╝╨╡╨╜╨╡╨╜╨░, ╤Б╨╛╤Б╤В╨░╨▓ ╨╛╤З╨╕╤Й╨╡╨╜, HC ╨▓╨╛╨╖╨▓╤А╨░╤Й╨╡╨╜╤Л ╨╜╨░ ╨▒╨░╨╗╨░╨╜╤Б.")
    else:
        await query.edit_message_text("╨Ч╨░╤П╨▓╨║╨░ ╤Г╨╢╨╡ ╨╖╨░╨▓╨╡╤А╤И╨╡╨╜╨░ ╨╕╨╗╨╕ ╨╛╤В╤Б╤Г╤В╤Б╤В╨▓╤Г╨╡╤В. ╨Т╨╛╨╖╨▓╤А╨░╤В ╨╜╨╡╨▓╨╛╨╖╨╝╨╛╨╢╨╡╨╜.")


async def challenge_reshuffle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Guard: deadline not passed
    try:
        cid_guard = context.user_data.get('challenge_id')
        if cid_guard and _challenge_deadline_passed(cid_guard):
            await query.edit_message_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤З╨╡╨╗╨╗╨╡╨╜╨┤╨╢╨░ ╨┐╤А╨╛╤И╤С╨╗. ╨Я╨╡╤А╨╡╤Б╨▒╨╛╤А╨║╨░ ╨╜╨╡╨┤╨╛╤Б╤В╤Г╨┐╨╜╨░.")
            return
    except Exception:
        pass
    cid = context.user_data.get('challenge_id')
    if not cid:
        await query.edit_message_text("╨Я╨╡╤А╨╡╤Б╨▒╨╛╤А╨║╨░ ╨╜╨╡╨┤╨╛╤Б╤В╤Г╨┐╨╜╨░: ╨╜╨╡╤В ╨░╨║╤В╨╕╨▓╨╜╨╛╨╣ ╨╖╨░╨┐╨╕╤Б╨╕.")
        return
    try:
        db.challenge_reset_picks(cid, update.effective_user.id)
        context.user_data['challenge_remaining_positions'] = ['╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣', '╨╖╨░╤Й╨╕╤В╨╜╨╕╨║', '╨▓╤А╨░╤В╨░╤А╤М']
        btns = [[InlineKeyboardButton(x, callback_data=f"challenge_pick_pos_{x}")] for x in context.user_data['challenge_remaining_positions']]
        await query.edit_message_text("╨б╨▒╤А╨╛╤Б ╨▓╤Л╨┐╨╛╨╗╨╜╨╡╨╜. ╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨┐╨╛╨╖╨╕╤Ж╨╕╤О:", reply_markup=InlineKeyboardMarkup(btns))
    except Exception as e:
        await query.edit_message_text(f"╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨┐╨╡╤А╨╡╤Б╨╛╨▒╤А╨░╤В╤М: {e}")


TOUR_START, TOUR_FORWARD_1, TOUR_FORWARD_2, TOUR_FORWARD_3, TOUR_DEFENDER_1, TOUR_DEFENDER_2, TOUR_GOALIE, TOUR_CAPTAIN, PREMIUM_TEAM, PREMIUM_POSITION = range(10)

async def tour_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ╨Я╨╛╨╗╤Г╤З╨░╨╡╨╝ ╨╛╨▒╤К╨╡╨║╤В ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╤П ╨┤╨╗╤П ╨╛╤В╨▓╨╡╤В╨░ (╤Г╨╜╨╕╨▓╨╡╤А╤Б╨░╨╗╤М╨╜╨╛ ╨┤╨╗╤П Update ╨╕ CallbackQuery)
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message

    # ╨Я╤А╨╛╨▓╨╡╤А╤П╨╡╨╝ ╨░╨║╤В╨╕╨▓╨╜╤Г╤О ╨┐╨╛╨┤╨┐╨╕╤Б╨║╤Г
    try:
        from db import is_subscription_active
        user = update.effective_user
        if not is_subscription_active(user.id):
            await message.reply_text(
                "╨Я╨╛╨┤╨┐╨╕╤Б╨║╨░ ╨╜╨╡ ╨░╨║╤В╨╕╨▓╨╜╨░. ╨Ю╤Д╨╛╤А╨╝╨╕╤В╨╡ ╨╕╨╗╨╕ ╨┐╤А╨╛╨┤╨╗╨╕╤В╨╡ ╨┐╨╛╨┤╨┐╨╕╤Б╨║╤Г ╨║╨╛╨╝╨░╨╜╨┤╨╛╨╣ /subscribe, ╨╖╨░╤В╨╡╨╝ ╨┐╨╛╨▓╤В╨╛╤А╨╕╤В╨╡ ╨┐╨╛╨┐╤Л╤В╨║╤Г."
            )
            return ConversationHandler.END
    except Exception:
        # ╨Я╤А╨╕ ╨╛╤И╨╕╨▒╨║╨╡ ╨┐╤А╨╛╨▓╨╡╤А╨║╨╕ ╨╜╨╡ ╨▒╨╗╨╛╨║╨╕╤А╤Г╨╡╨╝, ╨╜╨╛ ╨┤╨░╤С╨╝ ╨┐╨╛╨┤╤Б╨║╨░╨╖╨║╤Г
        try:
            await message.reply_text("╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨┐╤А╨╛╨▓╨╡╤А╨╕╤В╤М ╨┐╨╛╨┤╨┐╨╕╤Б╨║╤Г. ╨Х╤Б╨╗╨╕ ╨┤╨╛╤Б╤В╤Г╨┐ ╨╛╨│╤А╨░╨╜╨╕╤З╨╡╨╜, ╨╕╤Б╨┐╨╛╨╗╤М╨╖╤Г╨╣╤В╨╡ /subscribe.")
        except Exception:
            pass

    # --- ╨Ю╨┐╤А╨╡╨┤╨╡╨╗╤П╨╡╨╝ ╨░╨║╤В╨╕╨▓╨╜╤Л╨╣ ╤В╤Г╤А ---
    from db import get_active_tour
    active_tour = get_active_tour()
    if not active_tour:
        await message.reply_text("╨Э╨╡╤В ╨░╨║╤В╨╕╨▓╨╜╨╛╨│╨╛ ╤В╤Г╤А╨░ ╨┤╨╗╤П ╤Б╨▒╨╛╤А╨░ ╤Б╨╛╤Б╤В╨░╨▓╨░. ╨Ю╨▒╤А╨░╤В╨╕╤В╨╡╤Б╤М ╨║ ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╤Г.")
        return ConversationHandler.END
async def tour_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    # ╨Я╨╛╨╗╤Г╤З╨░╨╡╨╝ ╨╛╨▒╤К╨╡╨║╤В ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╤П ╨┤╨╗╤П ╨╛╤В╨▓╨╡╤В╨░ (╤Г╨╜╨╕╨▓╨╡╤А╤Б╨░╨╗╤М╨╜╨╛ ╨┤╨╗╤П Update ╨╕ CallbackQuery)
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message

    # --- ╨Ю╨┐╤А╨╡╨┤╨╡╨╗╤П╨╡╨╝ ╨░╨║╤В╨╕╨▓╨╜╤Л╨╣ ╤В╤Г╤А ---
    from db import get_active_tour, get_user_tour_roster, get_player_by_id
    active_tour = get_active_tour()
    if not active_tour:
        await message.reply_text("╨Э╨╡╤В ╨░╨║╤В╨╕╨▓╨╜╨╛╨│╨╛ ╤В╤Г╤А╨░ ╨┤╨╗╤П ╤Б╨▒╨╛╤А╨░ ╤Б╨╛╤Б╤В╨░╨▓╨░. ╨Ю╨▒╤А╨░╤В╨╕╤В╨╡╤Б╤М ╨║ ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╤Г.")
        return ConversationHandler.END
    context.user_data['active_tour_id'] = active_tour['id']
    # Guard: stop if deadline already passed
    try:
        dl = datetime.datetime.strptime(str(active_tour.get('deadline')), "%d.%m.%y %H:%M")
        if datetime.datetime.now() >= dl:
            await message.reply_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤В╤Г╤А╨░ ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗. ╨б╨▒╨╛╤А ╨╕ ╨╕╨╖╨╝╨╡╨╜╨╡╨╜╨╕╤П ╤Б╨╛╤Б╤В╨░╨▓╨░ ╨╖╨░╨║╤А╤Л╤В╤Л.")
            return ConversationHandler.END
    except Exception:
        pass

    user_id = update.effective_user.id
    tour_id = active_tour['id']
    user_roster = get_user_tour_roster(user_id, tour_id)
    if user_roster and user_roster.get('roster'):
        # ╨д╨╛╤А╨╝╨░╤В╨╕╤А╤Г╨╡╨╝ ╤Б╨╛╤Б╤В╨░╨▓ ╨┤╨╗╤П ╨▓╤Л╨▓╨╛╨┤╨░
        def format_user_roster_md(roster_data):
            from utils import escape_md
            roster = roster_data['roster']
            captain_id = roster_data.get('captain_id')
            spent = roster_data.get('spent', 0)
            # ╨Я╨╛╨╗╤Г╤З╨░╨╡╨╝ ╨╕╨╜╤Д╤Г ╨┐╨╛ ╨╕╨│╤А╨╛╨║╨░╨╝
            goalie = get_player_by_id(roster.get('goalie'))
            defenders = [get_player_by_id(pid) for pid in roster.get('defenders', [])]
            forwards = [get_player_by_id(pid) for pid in roster.get('forwards', [])]
            def fmt(p):
                if not p: return "-"
                return f"{p[1]} ({p[3]})"
            g_str = escape_md(fmt(goalie))
            d_str = escape_md(f"{fmt(defenders[0])} - {fmt(defenders[1])}") if len(defenders) == 2 else "-"
            f_str = escape_md(f"{fmt(forwards[0])} - {fmt(forwards[1])} - {fmt(forwards[2])}") if len(forwards) == 3 else "-"
            captain = None
            for p in [goalie] + defenders + forwards:
                if p and p[0] == captain_id:
                    captain = fmt(p)
            cap_str = f"╨Ъ╨░╨┐╨╕╤В╨░╨╜: {escape_md(captain)}" if captain else "╨Ъ╨░╨┐╨╕╤В╨░╨╜: -"
            lines = [
                '*╨Т╨░╤И ╤Б╨╛╤Е╤А╨░╨╜╤С╨╜╨╜╤Л╨╣ ╤Б╨╛╤Б╤В╨░╨▓:*',
                '',
                g_str,
                d_str,
                f_str,
                '',
                cap_str,
                f'╨Я╨╛╤В╤А╨░╤З╨╡╨╜╨╛: *{escape_md(str(spent))}* HC'
            ]
            return '\n'.join(lines)

        text = format_user_roster_md(user_roster)
        keyboard = [[InlineKeyboardButton('╨Я╨╡╤А╨╡╤Б╨╛╨▒╤А╨░╤В╤М ╤Б╨╛╤Б╤В╨░╨▓', callback_data='restart_tour')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(text, reply_markup=reply_markup, parse_mode="MarkdownV2")
        return ConversationHandler.END

    # --- ╨Х╤Б╨╗╨╕ ╤Б╨╛╤Б╤В╨░╨▓╨░ ╨╜╨╡╤В, ╨╖╨░╨┐╤Г╤Б╨║╨░╨╡╨╝ ╨╛╨▒╤Л╤З╨╜╤Л╨╣ ╤Б╤Ж╨╡╨╜╨░╤А╨╕╨╣ ╨▓╤Л╨▒╨╛╤А╨░ ---
    # 1. ╨Ю╤В╨┐╤А╨░╨▓╨╕╤В╤М ╨║╨░╤А╤В╨╕╨╜╨║╤Г ╤В╤Г╤А╨░ ╨╕ ╨▓╨▓╨╛╨┤╨╜╤Л╨╣ ╤В╨╡╨║╤Б╤В ╤Б ╨▒╤О╨┤╨╢╨╡╤В╨╛╨╝
    budget = db.get_budget() or 0
    roster = db.get_tour_roster_with_player_info()
    forwards = [p for p in roster if p[3].lower() == '╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣']
    defenders = [p for p in roster if p[3].lower() == '╨╖╨░╤Й╨╕╤В╨╜╨╕╨║']
    goalies = [p for p in roster if p[3].lower() == '╨▓╤А╨░╤В╨░╤А╤М']
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
    # ╨Ю╤В╨┐╤А╨░╨▓╨╕╤В╤М ╨║╨░╤А╤В╨╕╨╜╨║╤Г (╨╡╤Б╨╗╨╕ ╨╡╤Б╤В╤М)
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
        logger.error(f'╨Ю╤И╨╕╨▒╨║╨░ ╨┐╤А╨╕ ╨╛╤В╨┐╤А╨░╨▓╨║╨╡ ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╤П ╤В╤Г╤А╨░: {e}')
    # ╨Т╨▓╨╛╨┤╨╜╤Л╨╣ ╤В╨╡╨║╤Б╤В
    # ╨д╨╛╤А╨╝╨╕╤А╤Г╨╡╨╝ ╤Б╤В╤А╨╛╨║╤Г ╨┤╨╡╨┤╨╗╨░╨╣╨╜╨░
    deadline = active_tour.get('deadline', '')
    deadline_str = str(deadline).replace('.', '\\.')
    # ╨д╨╛╤А╨╝╨╕╤А╤Г╨╡╨╝ ╨║╤А╨░╤Б╨╕╨▓╤Л╨╣ ╤В╨╡╨║╤Б╤В ╤Б MarkdownV2
    intro = rf"""*╨б╨┐╨╕╤Б╨╛╨║ ╨╕╨│╤А╨╛╨║╨╛╨▓ ╨╜╨░ ╤В╨╡╨║╤Г╤Й╨╕╨╣ ╤В╤Г╤А\!* ╨Т╤Л╨▒╨╡╤А╨╕ ╨║ ╤Б╨╡╨▒╨╡ ╨▓ ╤Б╨╛╤Б╤В╨░╨▓:
ЁЯФ╕3 ╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╤Е
ЁЯФ╕2 ╨╖╨░╤Й╨╕╤В╨╜╨╕╨║╨╛╨▓
ЁЯФ╕1 ╨▓╤А╨░╤В╨░╤А╤П

╨Э╨░╨╖╨╜╨░╤З╤М ╨╛╨┤╨╜╨╛╨│╨╛ ╨┐╨╛╨╗╨╡╨▓╨╛╨│╨╛ ╨╕╨│╤А╨╛╨║╨░ ╨╕╨╖ ╤Б╨╛╤Б╤В╨░╨▓╨░ ╨║╨░╨┐╨╕╤В╨░╨╜╨╛╨╝ \(╨╡╨│╨╛ ╨╛╤З╨║╨╕ ╤Г╨╝╨╜╨╛╨╢╨╕╨╝ ╨╜╨░ ╤Е1\.5\)

*╨Т╨░╤И ╨▒╤О╨┤╨╢╨╡╤В: {budget}*

╨Я╤А╨╕╨╜╨╕╨╝╨░╨╡╨╝ ╤Б╨╛╤Б╤В╨░╨▓╤Л ╨┤╨╛: {deadline_str}"""

    # ╨Х╤Б╨╗╨╕ ╤Г ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤П ╨░╨║╤В╨╕╨▓╨╜╨░╤П ╨┐╨╛╨┤╨┐╨╕╤Б╨║╨░ тАФ ╨┤╨╛╨▒╨░╨▓╨╕╨╝ ╨▒╨╗╨╛╨║ ╨┐╤А╨╛ ╨┐╤А╨╡╨╝╨╕╤Г╨╝
    try:
        from db import is_subscription_active
        if is_subscription_active(update.effective_user.id):
            premium_line = "\n\nЁЯТО  ╨Я╤А╨╡╨╝╨╕╤Г╨╝: ╤Г ╤В╨╡╨▒╤П ╨┤╨╛╤Б╤В╤Г╨┐╨╡╨╜ ╨┐╨╡╤А╤Б╨╛╨╜╨░╨╗╤М╨╜╤Л╨╣ ╨▒╨╛╨╜╤Г╤Б тАФ \\+1 ╨╕╨│╤А╨╛╨║ ╨▓ ╨┐╤Г╨╗ \\(" \
                           "+ ╨┤╨╛╤Б╤В╤Г╨┐╨╜╨╛: 1/1 \\) ╨Т╤Л╨▒╨╕╤А╨░╨╣ ╤Б ╤Г╨╝╨╛╨╝!"
            # ╨Ш╤Б╨┐╤А╨░╨▓╨╕╨╝ ╤Б╤В╤А╨╛╨║╤Г ╨╜╨░ ╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Г╤О ╨▒╨╡╨╖ ╨║╨╛╨╜╨║╨░╤В╨╡╨╜╨░╤Ж╨╕╨╕ ╨┤╨╗╤П ╤З╨╕╤В╨░╨╡╨╝╨╛╤Б╤В╨╕
            premium_line = "\n\nЁЯТО  ╨Я╤А╨╡╨╝╨╕╤Г╨╝: ╤Г ╤В╨╡╨▒╤П ╨┤╨╛╤Б╤В╤Г╨┐╨╡╨╜ ╨┐╨╡╤А╤Б╨╛╨╜╨░╨╗╤М╨╜╤Л╨╣ ╨▒╨╛╨╜╤Г╤Б тАФ \\+1 ╨╕╨│╤А╨╛╨║ ╨▓ ╨┐╤Г╨╗ \\(" \
                           "╨┤╨╛╤Б╤В╤Г╨┐╨╜╨╛: 1/1\\) ╨Т╤Л╨▒╨╕╤А╨░╨╣ ╤Б ╤Г╨╝╨╛╨╝\\!"
            intro = intro + premium_line
    except Exception:
        pass

    await message.reply_text(intro, parse_mode="MarkdownV2")
    # ╨Ф╨╗╤П ╨┐╤А╨╡╨╝╨╕╤Г╨╝-╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╨╡╨╣ тАФ ╨┐╨╛╨║╨░╨╖╨░╤В╤М ╨║╨╜╨╛╨┐╨║╤Г ╨░╨║╤В╨╕╨▓╨░╤Ж╨╕╨╕ ╨▒╨╛╨╜╤Г╤Б╨░
    try:
        from db import is_subscription_active
        if is_subscription_active(update.effective_user.id):
            print("[DEBUG] tour_start: user has active subscription, showing premium button")
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton('╨Ф╨╛╨▒╨░╨▓╨╕╤В╤М ╨╕╨│╤А╨╛╨║╨░ ╨▓ ╨┐╤Г╨╗', callback_data='premium_add_pool')]]
            )
            sent = await message.reply_text('ЁЯТО ╨Я╤А╨╡╨╝╨╕╤Г╨╝-╨╛╨┐╤Ж╨╕╤П', reply_markup=kb)
            try:
                # ╨Ч╨░╨┐╨╛╨╝╨╜╨╕╨╝ ╨┤╨╗╤П ╨┤╨╕╨░╨│╨╜╨╛╤Б╤В╨╕╨║╨╕ id ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╤П ╤Б ╨┐╤А╨╡╨╝╨╕╤Г╨╝-╨║╨╜╨╛╨┐╨║╨╛╨╣
                context.user_data['premium_button_chat_id'] = sent.chat_id
                context.user_data['premium_button_message_id'] = sent.message_id
                print(f"[DEBUG] tour_start: premium button message_id={sent.message_id}")
            except Exception as e:
                print(f"[WARN] tour_start: failed to store premium button ids: {e}")
    except Exception:
        pass
    # ╨б╤А╨░╨╖╤Г ╨┐╨╛╨║╨░╨╖╤Л╨▓╨░╨╡╨╝ ╨▓╤Л╨▒╨╛╤А ╨┐╨╡╤А╨▓╨╛╨│╨╛ ╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╡╨│╨╛!
    return await tour_forward_1(update, context)


async def premium_add_pool_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ╨Ю╨▒╤А╨░╨▒╨╛╤В╨║╨░ ╨╜╨░╨╢╨░╤В╨╕╤П ╨┐╤А╨╡╨╝╨╕╤Г╨╝-╨║╨╜╨╛╨┐╨║╨╕: ╤Д╨╕╨║╤Б╨╕╤А╤Г╨╡╨╝ ╤Д╨╗╨░╨│ ╨▓ user_data
    query = update.callback_query
    try:
        print(f"[DEBUG] premium_add_pool_callback: received callback data={query.data}")
    except Exception:
        pass
    await query.answer()
    try:
        from db import is_subscription_active
        if not is_subscription_active(update.effective_user.id):
            print("[DEBUG] premium_add_pool_callback: subscription inactive")
            await query.message.reply_text("╨Я╤А╨╡╨╝╨╕╤Г╨╝ ╨╜╨╡╨┤╨╛╤Б╤В╤Г╨┐╨╡╨╜. ╨Ю╤Д╨╛╤А╨╝╨╕╤В╨╡ /subscribe, ╤З╤В╨╛╨▒╤Л ╨░╨║╤В╨╕╨▓╨╕╤А╨╛╨▓╨░╤В╤М ╨▒╨╛╨╜╤Г╤Б.")
            return TOUR_FORWARD_1
    except Exception:
        print("[WARN] premium_add_pool_callback: failed to check subscription")
    # ╨г╤Б╤В╨░╨╜╨╛╨▓╨╕╨╝ ╤Д╨╗╨░╨│╨╕ ╨┐╤А╨╡╨╝╨╕╤Г╨╝-╤А╨╡╨╢╨╕╨╝╨░: ╨┤╨╛╨▒╨░╨▓╨╗╨╡╨╜╨╕╨╡ ╨▓ ╨┐╤Г╨╗ (╨▒╨╡╨╖ ╨░╨▓╤В╨╛╨┤╨╛╨▒╨░╨▓╨╗╨╡╨╜╨╕╤П ╨▓ ╤Б╨╛╤Б╤В╨░╨▓)
    context.user_data['premium_extra_available'] = True
    context.user_data['premium_mode'] = 'add_to_pool'
    print("[DEBUG] premium_add_pool_callback: premium_extra_available=True set")
    # ╨г╨┤╨░╨╗╨╕╨╝ ╨┐╤А╨╡╨┤╤Л╨┤╤Г╤Й╨╡╨╡ ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╡ ╤Б ╨▓╤Л╨▒╨╛╤А╨╛╨╝ ╨╕╨│╤А╨╛╨║╨╛╨▓, ╨╡╤Б╨╗╨╕ ╤Б╨╛╤Е╤А╨░╨╜╨╡╨╜╨╛
    try:
        chat_id = context.user_data.get('last_choice_chat_id')
        msg_id = context.user_data.get('last_choice_message_id')
        if chat_id and msg_id:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            print(f"[DEBUG] premium_add_pool_callback: deleted last choice message id={msg_id}")
            # ╨Ю╤З╨╕╤Б╤В╨╕╨╝ ╤Б╨╛╤Е╤А╨░╨╜╤С╨╜╨╜╤Л╨╡ ╨╖╨╜╨░╤З╨╡╨╜╨╕╤П
            context.user_data.pop('last_choice_chat_id', None)
            context.user_data.pop('last_choice_message_id', None)
    except Exception:
        print("[WARN] premium_add_pool_callback: failed to delete last choice message")
    # ╨в╨░╨║╨╢╨╡ ╤Г╨┤╨░╨╗╨╕╨╝ ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╡ ╤Б ╤Б╨░╨╝╨╛╨╣ ╨┐╤А╨╡╨╝╨╕╤Г╨╝-╨║╨╜╨╛╨┐╨║╨╛╨╣
    try:
        await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
        print(f"[DEBUG] premium_add_pool_callback: deleted premium button message id={query.message.message_id}")
    except Exception:
        print("[WARN] premium_add_pool_callback: failed to delete premium button message")
    await query.message.reply_text("ЁЯТО ╨Я╨╡╤А╤Б╨╛╨╜╨░╨╗╤М╨╜╤Л╨╣ ╨▒╨╛╨╜╤Г╤Б ╨░╨║╤В╨╕╨▓╨╕╤А╨╛╨▓╨░╨╜: +1 ╨╕╨│╤А╨╛╨║ ╨▓ ╨┐╤Г╨╗.\n\n╨Э╨░╨┐╨╕╤И╨╕╤В╨╡ ╨║╨╛╨╝╨░╨╜╨┤╤Г ╨╕╨│╤А╨╛╨║╨░")
    return PREMIUM_TEAM


async def premium_team_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ╨Я╨╛╨╗╤Г╤З╨░╨╡╨╝ ╤В╨╡╨║╤Б╤В ╨║╨╛╨╝╨░╨╜╨┤╤Л ╨╕ ╨┐╤А╨╛╤Б╨╕╨╝ ╨▓╤Л╨▒╤А╨░╤В╤М ╨┐╨╛╨╖╨╕╤Ж╨╕╤О
    team_text = update.message.text.strip()
    context.user_data['premium_team_query'] = team_text
    try:
        print(f"[DEBUG] premium_team_input: received team text='{team_text}'")
    except Exception:
        pass
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton('╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣', callback_data='premium_pos_╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣')],
        [InlineKeyboardButton('╨╖╨░╤Й╨╕╤В╨╜╨╕╨║', callback_data='premium_pos_╨╖╨░╤Й╨╕╤В╨╜╨╕╨║')],
        [InlineKeyboardButton('╨▓╤А╨░╤В╨░╤А╤М', callback_data='premium_pos_╨▓╤А╨░╤В╨░╤А╤М')],
    ])
    await update.message.reply_text('╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨┐╨╛╨╖╨╕╤Ж╨╕╤О ╨╕╨│╤А╨╛╨║╨░', reply_markup=kb)
    return PREMIUM_POSITION


async def premium_position_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    pos = data.replace('premium_pos_', '')
    context.user_data['premium_position'] = pos
    print(f"[DEBUG] premium_position_selected: pos={pos}")
    # ╨Я╨╛╨║╨░╨╢╨╡╨╝ ╤Б╨┐╨╕╤Б╨╛╨║ ╨╕╨│╤А╨╛╨║╨╛╨▓, ╨╛╤В╤Д╨╕╨╗╤М╤В╤А╨╛╨▓╨░╨╜╨╜╤Л╤Е ╨┐╨╛ ╨║╨╛╨╝╨░╨╜╨┤╨╡ ╨╕ ╨┐╨╛╨╖╨╕╤Ж╨╕╨╕ (╨Ш╨Ч ╨Т╨б╨Х╨Щ ╨С╨Р╨Ч╨л ╨Ш╨У╨а╨Ю╨Ъ╨Ю╨Т)
    try:
        team_text = (context.user_data.get('premium_team_query') or '').strip().lower()
        from db import get_all_players
        all_players = get_all_players()  # (id, name, position, club, nation, age, price)
        budget = context.user_data.get('tour_budget', 0)
        spent = context.user_data.get('tour_selected', {}).get('spent', 0)
        left = max(0, budget - spent)
        # ╨Ш╤Б╨║╨╗╤О╤З╨╡╨╜╨╕╤П ╨┐╨╛ ╤Г╨╢╨╡ ╨▓╤Л╨▒╤А╨░╨╜╨╜╤Л╨╝
        selected = context.user_data.get('tour_selected', {})
        exclude_ids = []
        next_state = TOUR_FORWARD_1
        if pos == '╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣':
            exclude_ids = selected.get('forwards', [])
            next_state = TOUR_FORWARD_1
        elif pos == '╨╖╨░╤Й╨╕╤В╨╜╨╕╨║':
            exclude_ids = selected.get('defenders', [])
            # ╨Т╤Л╨▒╨╡╤А╨╡╨╝ ╨┐╨╛╨┤╤Е╨╛╨┤╤П╤Й╨╡╨╡ ╤Б╨╛╤Б╤В╨╛╤П╨╜╨╕╨╡ ╨▓ ╨╖╨░╨▓╨╕╤Б╨╕╨╝╨╛╤Б╤В╨╕ ╨╛╤В ╤Г╨╢╨╡ ╨▓╤Л╨▒╤А╨░╨╜╨╜╤Л╤Е
            next_state = TOUR_DEFENDER_1 if len(exclude_ids) == 0 else TOUR_DEFENDER_2
        elif pos == '╨▓╤А╨░╤В╨░╤А╤М':
            gid = selected.get('goalie')
            exclude_ids = [gid] if gid else []
            next_state = TOUR_GOALIE
        # ╨д╨╕╨╗╤М╤В╤А╨░╤Ж╨╕╤П ╨┐╨╛ ╨┐╨╛╨╖╨╕╤Ж╨╕╨╕, ╨║╨╛╨╝╨░╨╜╨┤╨╡, ╨▒╤О╨┤╨╢╨╡╤В╤Г ╨╕ ╨╕╤Б╨║╨╗╤О╤З╨╡╨╜╨╕╤П╨╝
        def team_match(t):
            try:
                return team_text in str(t or '').lower()
            except Exception:
                return False
        # ╨Ш╤Б╨║╨╗╤О╤З╨╕╨╝ ╨╕╨│╤А╨╛╨║╨╛╨▓, ╤Г╨╢╨╡ ╨▓╨║╨╗╤О╤З╤С╨╜╨╜╤Л╤Е ╨▓ ╤В╤Г╤А╨╛╨▓╤Л╨╣ ╤А╨╛╤Б╤В╨╡╤А
        tour_roster = context.user_data.get('tour_roster', [])
        tour_ids = set([tr[1] for tr in tour_roster])  # p.id ╨╕╨╖ ╤В╤Г╤А╨╛╨▓╨╛╨│╨╛ ╤Б╨┐╨╕╤Б╨║╨░
        # ╨Ш╨╜╨┤╨╡╨║╤Б╤Л ╨▓ players: 0-id,1-name,2-position,3-club,6-price
        filtered = [
            p for p in all_players
            if p[2].lower() == pos
            and p[0] not in exclude_ids
            and p[0] not in tour_ids
            and (p[6] or 0) <= left
            and team_match(p[3])
        ]
        print(f"[DEBUG] premium_position_selected: team='{team_text}', found={len(filtered)} players in DB (excluding tour roster), left={left}")
        if not filtered:
            await query.message.reply_text("╨Я╨╛ ╨╖╨░╨┤╨░╨╜╨╜╤Л╨╝ ╤Д╨╕╨╗╤М╤В╤А╨░╨╝ ╨╕╨│╤А╨╛╨║╨╛╨▓ ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜╨╛. ╨Ш╨╖╨╝╨╡╨╜╨╕╤В╨╡ ╨║╨╛╨╝╨░╨╜╨┤╤Г ╨╕╨╗╨╕ ╨┐╨╛╨╖╨╕╤Ж╨╕╤О.")
            return next_state
        # ╨Я╨╛╤Б╤В╤А╨╛╨╕╨╝ ╨║╨╗╨░╨▓╨╕╨░╤В╤Г╤А╤Г
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = []
        for p in filtered:
            btn_text = f"{p[1]} тАФ {p[6]} HC"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pick_{p[0]}_{pos}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = f"╨Э╨░╨╣╨┤╨╡╨╜╨╜╤Л╨╡ ╨╕╨│╤А╨╛╨║╨╕ ({pos}, ╨║╨╛╨╝╨░╨╜╨┤╨░ ╤Б╨╛╨┤╨╡╤А╨╢╨╕╤В: '{team_text}') тАФ ╨╛╤Б╤В╨░╨╗╨╛╤Б╤М HC: {left}"
        sent = await query.message.reply_text(text, reply_markup=reply_markup)
        # ╨б╨╛╤Е╤А╨░╨╜╨╕╨╝, ╤З╤В╨╛╨▒╤Л ╨╝╨╛╤З╤М ╤Г╨┤╨░╨╗╨╕╤В╤М ╨┤╨░╨╗╨╡╨╡ ╨┐╤А╨╕ ╨╜╨╡╨╛╨▒╤Е╨╛╨┤╨╕╨╝╨╛╤Б╤В╨╕
        try:
            context.user_data['last_choice_chat_id'] = sent.chat_id
            context.user_data['last_choice_message_id'] = sent.message_id
        except Exception:
            pass
        return next_state
    except Exception as e:
        print(f"[ERROR] premium_position_selected building list: {e}")
        await query.message.reply_text(f"╨Ю╤И╨╕╨▒╨║╨░ ╨┐╨╛╤Б╤В╤А╨╛╨╡╨╜╨╕╤П ╤Б╨┐╨╕╤Б╨║╨░: {e}")
        return TOUR_FORWARD_1

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

async def send_player_choice(update, context, position, exclude_ids, next_state, budget):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    # ╨г╨╜╨╕╨▓╨╡╤А╤Б╨░╨╗╤М╨╜╨╛ ╨┐╨╛╨╗╤Г╤З╨░╨╡╨╝ message ╨┤╨╗╤П reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message
    # ╨Я╨╛╨╗╤Г╤З╨░╨╡╨╝ ╨░╨║╤В╤Г╨░╨╗╤М╨╜╤Л╨╣ ╤А╨╛╤Б╤В╨╡╤А
    roster = context.user_data['tour_roster']
    # ╨д╨╕╨╗╤М╤В╤А╤Г╨╡╨╝ ╨┐╨╛ ╨┐╨╛╨╖╨╕╤Ж╨╕╨╕ ╨╕ ╨╕╤Б╨║╨╗╤О╤З╨╡╨╜╨╕╤П╨╝
    players = [p for p in roster if p[3].lower() == position and p[1] not in exclude_ids and p[7] <= budget]
    if not players:
        # ╨Я╤А╨╛╨▓╨╡╤А╨║╨░: ╨╡╤Б╨╗╨╕ ╨╜╨╡ ╤Е╨▓╨░╤В╨░╨╡╤В HC ╨┤╨╗╤П ╨╛╨▒╤П╨╖╨░╤В╨╡╨╗╤М╨╜╨╛╨│╨╛ ╨▓╤Л╨▒╨╛╤А╨░
        text = (
            'ЁЯЪи ╨Т╤Л ╨┐╤А╨╕╨▓╤Л╤Б╨╕╨╗╨╕ ╨┐╨╛╤В╨╛╨╗╨╛╨║ ╨╖╨░╤А╨┐╨╗╨░╤В. ╨Я╨╡╤А╨╡╤Б╨╛╨▒╨╡╤А╨╕╤В╨╡ ╤Б╨╛╤Б╤В╨░╨▓, ╤З╤В╨╛╨▒╤Л ╨▓╨┐╨╕╤Б╨░╤В╤М╤Б╤П ╨▓ ╨╗╨╕╨╝╨╕╤В.'
        )
        keyboard = [
            [InlineKeyboardButton('╨Я╨╡╤А╨╡╤Б╨╛╨▒╤А╨░╤В╤М ╤Б╨╛╤Б╤В╨░╨▓', callback_data='restart_tour')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(text, reply_markup=reply_markup)
        return ConversationHandler.END
    keyboard = []
    for p in players:
        btn_text = f"{p[2]} тАФ {p[7]} HC"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pick_{p[1]}_{position}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ {position} (╨╛╤Б╤В╨░╨╗╨╛╤Б╤М HC: {budget})"
    sent_msg = await message.reply_text(text, reply_markup=reply_markup)
    # ╨Ч╨░╨┐╨╛╨╝╨╜╨╕╨╝ ╨┐╨╛╤Б╨╗╨╡╨┤╨╜╨╡╨╡ ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╡ ╤Б ╨▓╤Л╨▒╨╛╤А╨╛╨╝, ╤З╤В╨╛╨▒╤Л ╨╝╨╛╤З╤М ╤Г╨┤╨░╨╗╨╕╤В╤М ╨┐╤А╨╕ ╨░╨║╤В╨╕╨▓╨░╤Ж╨╕╨╕ ╨┐╤А╨╡╨╝╨╕╤Г╨╝-╤А╨╡╨╢╨╕╨╝╨░
    try:
        context.user_data['last_choice_chat_id'] = sent_msg.chat_id
        context.user_data['last_choice_message_id'] = sent_msg.message_id
    except Exception:
        pass
    return next_state
    keyboard = []
    for p in players:
        btn_text = f"{p[2]} тАФ {p[7]} HC"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pick_{p[1]}_{position}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ {position} (╨╛╤Б╤В╨░╨╗╨╛╤Б╤М HC: {budget})"
    await message.reply_text(text, reply_markup=reply_markup)
    return next_state

async def tour_forward_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _tour_deadline_passed(context):
        await update.effective_message.reply_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤В╤Г╤А╨░ ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗. ╨б╨▒╨╛╤А ╨╕ ╨╕╨╖╨╝╨╡╨╜╨╡╨╜╨╕╤П ╤Б╨╛╤Б╤В╨░╨▓╨░ ╨╖╨░╨║╤А╤Л╤В╤Л.")
        return ConversationHandler.END
    budget = context.user_data['tour_budget']
    picked = context.user_data['tour_selected']['forwards']
    return await send_player_choice(update, context, '╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣', picked, TOUR_FORWARD_2, budget)


async def tour_forward_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _tour_deadline_passed(context):
        await update.effective_message.reply_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤В╤Г╤А╨░ ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗. ╨б╨╛╤Б╤В╨░╨▓ ╨▒╨╛╨╗╤М╤И╨╡ ╨╝╨╡╨╜╤П╤В╤М ╨╜╨╡╨╗╤М╨╖╤П.")
        return ConversationHandler.END
    try:
        query = update.callback_query
        await query.answer()
        data = query.data
        print(f"Callback data: {data}", flush=True)
        # ╨Ю╨╢╨╕╨┤╨░╨╡╤В╤Б╤П ╤Д╨╛╤А╨╝╨░╤В pick_<player_id>_╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣
        if not data.startswith('pick_') or '_╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣' not in data:
            await query.edit_message_text('╨Э╨╡╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Л╨╣ ╨▓╤Л╨▒╨╛╤А.')
            return TOUR_FORWARD_1
        pid = int(data.split('_')[1])
        # ╨Я╨╛╨╗╤Г╤З╨░╨╡╨╝ ╨╕╨│╤А╨╛╨║╨░ ╨┐╨╛ id
        roster = context.user_data['tour_roster']
        player = next((p for p in roster if p[1] == pid), None)
        added_personal = False
        if not player:
            # Fallback: ╨╕╤Й╨╡╨╝ ╨▓ ╨╛╨▒╤Й╨╡╨╣ ╨С╨Ф ╨╕╨│╤А╨╛╨║╨╛╨▓
            try:
                pdb = db.get_player_by_id(pid)
                if pdb:
                    # ╨Я╤А╨╡╨╛╨▒╤А╨░╨╖╤Г╨╡╨╝ ╨║ ╤Д╨╛╤А╨╝╨░╤В╤Г: (tr.cost, p.id, p.name, p.position, p.club, p.nation, p.age, p.price)
                    player = (pdb[6], pdb[0], pdb[1], pdb[2], pdb[3], pdb[4], pdb[5], pdb[6])
                    # ╨Ф╨╛╨▒╨░╨▓╨╕╨╝ ╤Н╤В╨╛╨│╨╛ ╨╕╨│╤А╨╛╨║╨░ ╨▓ ╨┐╨╡╤А╤Б╨╛╨╜╨░╨╗╤М╨╜╤Л╨╣ ╤В╤Г╤А╨╛╨▓╤Л╨╣ ╤Б╨┐╨╕╤Б╨╛╨║ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤П, ╨╡╤Б╨╗╨╕ ╨╡╤Й╤С ╨╜╨╡╤В
                    try:
                        if not any(p_[1] == pdb[0] for p_ in roster):
                            context.user_data['tour_roster'].append(player)
                        added_personal = True
                        # ╨Я╨╛╨╝╨╡╤В╨╕╨╝ ╨╕╤Б╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╨╜╨╕╨╡ ╨┐╤А╨╡╨╝╨╕╤Г╨╝-╨▒╨╛╨╜╤Г╤Б╨░
                        context.user_data['premium_extra_available'] = False
                    except Exception:
                        pass
                else:
                    await query.edit_message_text('╨Ш╨│╤А╨╛╨║ ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜.')
                    return TOUR_FORWARD_1
            except Exception:
                await query.edit_message_text('╨Ш╨│╤А╨╛╨║ ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜.')
                return TOUR_FORWARD_1
        # ╨Х╤Б╨╗╨╕ ╨░╨║╤В╨╕╨▓╨╡╨╜ ╤А╨╡╨╢╨╕╨╝ ╨┤╨╛╨▒╨░╨▓╨╗╨╡╨╜╨╕╤П ╨▓ ╨┐╤Г╨╗ тАФ ╨╜╨╡ ╨┤╨╛╨▒╨░╨▓╨╗╤П╨╡╨╝ ╨▓ ╤Б╨╛╤Б╤В╨░╨▓, ╨░ ╤В╨╛╨╗╤М╨║╨╛ ╤А╨░╤Б╤И╨╕╤А╤П╨╡╨╝ ╨┐╤Г╨╗
        if context.user_data.get('premium_mode') == 'add_to_pool':
            try:
                # ╨г╨▒╨╡╨┤╨╕╨╝╤Б╤П, ╤З╤В╨╛ ╨╕╨│╤А╨╛╨║ ╨╡╤Б╤В╤М ╨▓ ╨┐╨╡╤А╤Б╨╛╨╜╨░╨╗╤М╨╜╨╛╨╝ ╨┐╤Г╨╗╨╡
                roster = context.user_data['tour_roster']
                if not any(p_[1] == player[1] for p_ in roster):
                    context.user_data['tour_roster'].append(player)
                # ╨Т╤Л╨║╨╗╤О╤З╨░╨╡╨╝ ╤А╨╡╨╢╨╕╨╝ ╨╕ ╤Б╨╢╨╕╨│╨░╨╡╨╝ ╨▒╨╛╨╜╤Г╤Б
                context.user_data['premium_mode'] = None
                context.user_data['premium_extra_available'] = False
                # ╨Я╨╛╨║╨░╨╢╨╡╨╝ ╨╛╨▒╤Л╤З╨╜╤Л╨╣ ╨▓╤Л╨▒╨╛╤А ╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╤Е ╤Б ╤Г╤З╤С╤В╨╛╨╝ ╤А╨░╤Б╤И╨╕╤А╨╡╨╜╨╜╨╛╨│╨╛ ╨┐╤Г╨╗╨░
                budget = context.user_data['tour_budget']
                spent = context.user_data['tour_selected']['spent']
                left = budget - spent
                picked = context.user_data['tour_selected']['forwards']
                await query.edit_message_text(f"╨Ф╨╛╨▒╨░╨▓╨╗╨╡╨╜ ╨▓ ╨▓╨░╤И ╨┐╤Г╨╗: {player[2]} ({player[4]}). ╨в╨╡╨┐╨╡╤А╤М ╨▓╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╡╨│╨╛.")
                next_state = TOUR_FORWARD_2 if len(picked) == 0 else TOUR_FORWARD_3
                return await send_player_choice(update, context, '╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣', picked, next_state, left)
            except Exception as e:
                await query.edit_message_text(f"╨Ю╤И╨╕╨▒╨║╨░ ╨┤╨╛╨▒╨░╨▓╨╗╨╡╨╜╨╕╤П ╨▓ ╨┐╤Г╨╗: {e}")
                return TOUR_FORWARD_1
        # ╨Я╤А╨╛╨▓╨╡╤А╤П╨╡╨╝ ╨▒╤О╨┤╨╢╨╡╤В
        budget = context.user_data['tour_budget']
        spent = context.user_data['tour_selected']['spent']
        if spent + player[7] > budget:
            await query.edit_message_text(f'╨Э╨╡╨┤╨╛╤Б╤В╨░╤В╨╛╤З╨╜╨╛ HC ╨┤╨╗╤П ╨▓╤Л╨▒╨╛╤А╨░ {player[1]}!')
            return TOUR_FORWARD_1
        # ╨б╨╛╤Е╤А╨░╨╜╤П╨╡╨╝ ╨▓╤Л╨▒╨╛╤А
        context.user_data['tour_selected']['forwards'].append(pid)
        context.user_data['tour_selected']['spent'] += player[7]
        left = budget - context.user_data['tour_selected']['spent']
        player_name = escape_md(str(player[2]))
        cost = escape_md(str(player[7]))
        left_str = escape_md(str(left))
        msg = f'╨Т╤Л ╨▓╤Л╨▒╤А╨░╨╗╨╕ {player_name} \\({cost}\\)\n\n*╨Ю╤Б╤В╨░╨▓╤И╨╕╨╣╤Б╤П ╨▒╤О╨┤╨╢╨╡╤В: {left_str}*'
        await query.edit_message_text(msg, parse_mode="MarkdownV2")
        if len(context.user_data['tour_selected']['forwards']) == 1:
            print("tour_forward_callback SUCCESS: ╨┐╨╡╤А╨╡╤Е╨╛╨┤ ╨║ tour_forward_2", flush=True)
            return await tour_forward_2(update, context)
        elif len(context.user_data['tour_selected']['forwards']) == 2:
            print("tour_forward_callback SUCCESS: ╨┐╨╡╤А╨╡╤Е╨╛╨┤ ╨║ tour_forward_3", flush=True)
            return await tour_forward_3(update, context)
        elif len(context.user_data['tour_selected']['forwards']) == 3:
            print("tour_forward_callback SUCCESS: ╨┐╨╡╤А╨╡╤Е╨╛╨┤ ╨║ tour_defender_1", flush=True)
            await tour_defender_1(update, context)
            return TOUR_DEFENDER_1
    except Exception as e:
        print(f"tour_forward_callback ERROR: {e}", flush=True)
        logger.exception("Exception in tour_forward_callback")
        await query.edit_message_text(f"╨Ю╤И╨╕╨▒╨║╨░: {e}")
        return TOUR_FORWARD_1
    finally:
        print("tour_forward_callback FINISHED", flush=True)


async def tour_forward_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _tour_deadline_passed(context):
        await update.effective_message.reply_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤В╤Г╤А╨░ ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗. ╨б╨▒╨╛╤А ╨╕ ╨╕╨╖╨╝╨╡╨╜╨╡╨╜╨╕╤П ╤Б╨╛╤Б╤В╨░╨▓╨░ ╨╖╨░╨║╤А╤Л╤В╤Л.")
        return ConversationHandler.END
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = context.user_data['tour_selected']['forwards']
    return await send_player_choice(update, context, '╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣', picked, TOUR_FORWARD_3, left)


async def tour_forward_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _tour_deadline_passed(context):
        await update.effective_message.reply_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤В╤Г╤А╨░ ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗. ╨б╨▒╨╛╤А ╨╕ ╨╕╨╖╨╝╨╡╨╜╨╡╨╜╨╕╤П ╤Б╨╛╤Б╤В╨░╨▓╨░ ╨╖╨░╨║╤А╤Л╤В╤Л.")
        return ConversationHandler.END
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = context.user_data['tour_selected']['forwards']
    # ╨Я╨╛╨║╨░╨╖╤Л╨▓╨░╨╡╨╝ ╨║╨╗╨░╨▓╨╕╨░╤В╤Г╤А╤Г ╨┤╨╗╤П ╤В╤А╨╡╤В╤М╨╡╨│╨╛ ╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╡╨│╨╛, next_state тАФ TOUR_FORWARD_3
    return await send_player_choice(update, context, '╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣', picked, TOUR_FORWARD_3, left)

async def tour_defender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _tour_deadline_passed(context):
        await update.effective_message.reply_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤В╤Г╤А╨░ ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗. ╨б╨╛╤Б╤В╨░╨▓ ╨▒╨╛╨╗╤М╤И╨╡ ╨╝╨╡╨╜╤П╤В╤М ╨╜╨╡╨╗╤М╨╖╤П.")
        return ConversationHandler.END
    try:
        query = update.callback_query
        await query.answer()
        data = query.data
        print(f"Callback data: {data}", flush=True)
        # ╨Ю╨╢╨╕╨┤╨░╨╡╤В╤Б╤П ╤Д╨╛╤А╨╝╨░╤В pick_<player_id>_╨╖╨░╤Й╨╕╤В╨╜╨╕╨║
        if not data.startswith('pick_') or '_╨╖╨░╤Й╨╕╤В╨╜╨╕╨║' not in data:
            await query.edit_message_text('╨Э╨╡╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Л╨╣ ╨▓╤Л╨▒╨╛╤А.')
            return TOUR_DEFENDER_1
        pid = int(data.split('_')[1])
        roster = context.user_data['tour_roster']
        player = next((p for p in roster if p[1] == pid), None)
        added_personal = False
        if not player:
            # Fallback: ╨╕╤Й╨╡╨╝ ╨▓ ╨╛╨▒╤Й╨╡╨╣ ╨С╨Ф ╨╕╨│╤А╨╛╨║╨╛╨▓
            try:
                pdb = db.get_player_by_id(pid)
                if pdb:
                    player = (pdb[6], pdb[0], pdb[1], pdb[2], pdb[3], pdb[4], pdb[5], pdb[6])
                    try:
                        if not any(p_[1] == pdb[0] for p_ in roster):
                            context.user_data['tour_roster'].append(player)
                        added_personal = True
                        context.user_data['premium_extra_available'] = False
                    except Exception:
                        pass
                else:
                    await query.edit_message_text('╨Ш╨│╤А╨╛╨║ ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜.')
                    return TOUR_DEFENDER_1
            except Exception:
                await query.edit_message_text('╨Ш╨│╤А╨╛╨║ ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜.')
                return TOUR_DEFENDER_1
        # ╨а╨╡╨╢╨╕╨╝ ╨┤╨╛╨▒╨░╨▓╨╗╨╡╨╜╨╕╤П ╨▓ ╨┐╤Г╨╗ тАФ ╨▒╨╡╨╖ ╨░╨▓╤В╨╛╨┤╨╛╨▒╨░╨▓╨╗╨╡╨╜╨╕╤П ╨▓ ╤Б╨╛╤Б╤В╨░╨▓
        if context.user_data.get('premium_mode') == 'add_to_pool':
            try:
                roster = context.user_data['tour_roster']
                if not any(p_[1] == player[1] for p_ in roster):
                    context.user_data['tour_roster'].append(player)
                context.user_data['premium_mode'] = None
                context.user_data['premium_extra_available'] = False
                budget = context.user_data['tour_budget']
                spent = context.user_data['tour_selected']['spent']
                left = budget - spent
                # ╨Я╨╛╤Б╨╗╨╡ ╨┤╨╛╨▒╨░╨▓╨╗╨╡╨╜╨╕╤П ╨▓ ╨┐╤Г╨╗ ╨▓╤Б╨╡╨│╨┤╨░ ╨▓╨╛╨╖╨▓╤А╨░╤Й╨░╨╡╨╝╤Б╤П ╨║ ╨▓╤Л╨▒╨╛╤А╤Г ╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╤Е
                forwards_picked = context.user_data['tour_selected']['forwards']
                await query.edit_message_text(f"╨Ф╨╛╨▒╨░╨▓╨╗╨╡╨╜ ╨▓ ╨▓╨░╤И ╨┐╤Г╨╗: {player[2]} ({player[4]}). ╨в╨╡╨┐╨╡╤А╤М ╨▓╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╡╨│╨╛.")
                next_state = TOUR_FORWARD_2 if len(forwards_picked) == 0 else TOUR_FORWARD_3
                return await send_player_choice(update, context, '╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣', forwards_picked, next_state, left)
            except Exception as e:
                await query.edit_message_text(f"╨Ю╤И╨╕╨▒╨║╨░ ╨┤╨╛╨▒╨░╨▓╨╗╨╡╨╜╨╕╤П ╨▓ ╨┐╤Г╨╗: {e}")
                return TOUR_FORWARD_1
        budget = context.user_data['tour_budget']
        spent = context.user_data['tour_selected']['spent']
        if spent + player[7] > budget:
            await query.edit_message_text(f'╨Э╨╡╨┤╨╛╤Б╤В╨░╤В╨╛╤З╨╜╨╛ HC ╨┤╨╗╤П ╨▓╤Л╨▒╨╛╤А╨░ {player[1]}!')
            return TOUR_DEFENDER_1
        context.user_data['tour_selected']['defenders'].append(pid)
        context.user_data['tour_selected']['spent'] += player[7]
        left = budget - context.user_data['tour_selected']['spent']
        player_name = escape_md(str(player[2]))
        cost = escape_md(str(player[7]))
        left_str = escape_md(str(left))
        msg = f'╨Т╤Л ╨▓╤Л╨▒╤А╨░╨╗╨╕ {player_name} \\({cost}\\)\n\n*╨Ю╤Б╤В╨░╨▓╤И╨╕╨╣╤Б╤П ╨▒╤О╨┤╨╢╨╡╤В: {left_str}*'
        await query.edit_message_text(msg, parse_mode="MarkdownV2")
        if len(context.user_data['tour_selected']['defenders']) == 1:
            print("tour_defender_callback SUCCESS: ╨┐╨╡╤А╨╡╤Е╨╛╨┤ ╨║ tour_defender_2", flush=True)
            return await tour_defender_2(update, context)
        elif len(context.user_data['tour_selected']['defenders']) == 2:
            print("tour_defender_callback SUCCESS: ╨┐╨╡╤А╨╡╤Е╨╛╨┤ ╨║ tour_goalie", flush=True)
            await tour_goalie(update, context)
            return TOUR_GOALIE
    except Exception as e:
        print(f"tour_defender_callback ERROR: {e}", flush=True)
        logger.exception("Exception in tour_defender_callback")
        await query.edit_message_text(f"╨Ю╤И╨╕╨▒╨║╨░: {e}")
        return TOUR_DEFENDER_1
    finally:
        print("tour_defender_callback FINISHED", flush=True)


async def tour_defender_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _tour_deadline_passed(context):
        await update.effective_message.reply_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤В╤Г╤А╨░ ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗. ╨б╨▒╨╛╤А ╨╕ ╨╕╨╖╨╝╨╡╨╜╨╡╨╜╨╕╤П ╤Б╨╛╤Б╤В╨░╨▓╨░ ╨╖╨░╨║╤А╤Л╤В╤Л.")
        return ConversationHandler.END
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = context.user_data['tour_selected']['defenders']
    return await send_player_choice(update, context, '╨╖╨░╤Й╨╕╤В╨╜╨╕╨║', picked, TOUR_DEFENDER_2, left)

async def tour_defender_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _tour_deadline_passed(context):
        await update.effective_message.reply_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤В╤Г╤А╨░ ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗. ╨б╨▒╨╛╤А ╨╕ ╨╕╨╖╨╝╨╡╨╜╨╡╨╜╨╕╤П ╤Б╨╛╤Б╤В╨░╨▓╨░ ╨╖╨░╨║╤А╤Л╤В╤Л.")
        return ConversationHandler.END
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = context.user_data['tour_selected']['defenders']
    # ╨Я╨╛╨║╨░╨╖╤Л╨▓╨░╨╡╨╝ ╨║╨╗╨░╨▓╨╕╨░╤В╤Г╤А╤Г ╨┤╨╗╤П ╨▓╤В╨╛╤А╨╛╨│╨╛ ╨╖╨░╤Й╨╕╤В╨╜╨╕╨║╨░, next_state тАФ TOUR_DEFENDER_2
    return await send_player_choice(update, context, '╨╖╨░╤Й╨╕╤В╨╜╨╕╨║', picked, TOUR_DEFENDER_2, left)

async def tour_goalie_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _tour_deadline_passed(context):
        await update.effective_message.reply_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤В╤Г╤А╨░ ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗. ╨б╨╛╤Б╤В╨░╨▓ ╨▒╨╛╨╗╤М╤И╨╡ ╨╝╨╡╨╜╤П╤В╤М ╨╜╨╡╨╗╤М╨╖╤П.")
        return ConversationHandler.END
    try:
        query = update.callback_query
        await query.answer()
        data = query.data
        print(f"Callback data: {data}", flush=True)
        # ╨Ю╨╢╨╕╨┤╨░╨╡╤В╤Б╤П ╤Д╨╛╤А╨╝╨░╤В pick_<player_id>_╨▓╤А╨░╤В╨░╤А╤М
        if not data.startswith('pick_') or '_╨▓╤А╨░╤В╨░╤А╤М' not in data:
            await query.edit_message_text('╨Э╨╡╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Л╨╣ ╨▓╤Л╨▒╨╛╤А.')
            return TOUR_GOALIE
        pid = int(data.split('_')[1])
        roster = context.user_data['tour_roster']
        player = next((p for p in roster if p[1] == pid), None)
        added_personal = False
        if not player:
            # Fallback: ╨╕╤Й╨╡╨╝ ╨▓ ╨╛╨▒╤Й╨╡╨╣ ╨С╨Ф ╨╕╨│╤А╨╛╨║╨╛╨▓
            try:
                pdb = db.get_player_by_id(pid)
                if pdb:
                    player = (pdb[6], pdb[0], pdb[1], pdb[2], pdb[3], pdb[4], pdb[5], pdb[6])
                    try:
                        if not any(p_[1] == pdb[0] for p_ in roster):
                            context.user_data['tour_roster'].append(player)
                        added_personal = True
                        context.user_data['premium_extra_available'] = False
                    except Exception:
                        pass
                else:
                    await query.edit_message_text('╨Ш╨│╤А╨╛╨║ ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜.')
                    return TOUR_GOALIE
            except Exception:
                await query.edit_message_text('╨Ш╨│╤А╨╛╨║ ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜.')
                return TOUR_GOALIE
        # ╨а╨╡╨╢╨╕╨╝ ╨┤╨╛╨▒╨░╨▓╨╗╨╡╨╜╨╕╤П ╨▓ ╨┐╤Г╨╗ тАФ ╨▒╨╡╨╖ ╨░╨▓╤В╨╛╨┤╨╛╨▒╨░╨▓╨╗╨╡╨╜╨╕╤П ╨▓ ╤Б╨╛╤Б╤В╨░╨▓
        if context.user_data.get('premium_mode') == 'add_to_pool':
            try:
                roster = context.user_data['tour_roster']
                if not any(p_[1] == player[1] for p_ in roster):
                    context.user_data['tour_roster'].append(player)
                context.user_data['premium_mode'] = None
                context.user_data['premium_extra_available'] = False
                budget = context.user_data['tour_budget']
                spent = context.user_data['tour_selected']['spent']
                left = budget - spent
                # ╨Я╨╛╤Б╨╗╨╡ ╨┤╨╛╨▒╨░╨▓╨╗╨╡╨╜╨╕╤П ╨▓ ╨┐╤Г╨╗ ╨▓╤Б╨╡╨│╨┤╨░ ╨▓╨╛╨╖╨▓╤А╨░╤Й╨░╨╡╨╝╤Б╤П ╨║ ╨▓╤Л╨▒╨╛╤А╤Г ╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╤Е
                forwards_picked = context.user_data['tour_selected']['forwards']
                await query.edit_message_text(f"╨Ф╨╛╨▒╨░╨▓╨╗╨╡╨╜ ╨▓ ╨▓╨░╤И ╨┐╤Г╨╗: {player[2]} ({player[4]}). ╨в╨╡╨┐╨╡╤А╤М ╨▓╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╡╨│╨╛.")
                next_state = TOUR_FORWARD_2 if len(forwards_picked) == 0 else TOUR_FORWARD_3
                return await send_player_choice(update, context, '╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╨╣', forwards_picked, next_state, left)
            except Exception as e:
                await query.edit_message_text(f"╨Ю╤И╨╕╨▒╨║╨░ ╨┤╨╛╨▒╨░╨▓╨╗╨╡╨╜╨╕╤П ╨▓ ╨┐╤Г╨╗: {e}")
                return TOUR_FORWARD_1
        budget = context.user_data['tour_budget']
        spent = context.user_data['tour_selected']['spent']
        if spent + player[7] > budget:
            await query.edit_message_text(f'╨Э╨╡╨┤╨╛╤Б╤В╨░╤В╨╛╤З╨╜╨╛ HC ╨┤╨╗╤П ╨▓╤Л╨▒╨╛╤А╨░ {player[1]}!')
            return TOUR_GOALIE
        context.user_data['tour_selected']['goalie'] = pid
        context.user_data['tour_selected']['spent'] += player[7]
        left = budget - context.user_data['tour_selected']['spent']
        player_name = escape_md(str(player[2]))
        cost = escape_md(str(player[7]))
        left_str = escape_md(str(left))
        msg = f'╨Т╤Л ╨▓╤Л╨▒╤А╨░╨╗╨╕ {player_name} \\({cost}\\)\n\n*╨Ю╤Б╤В╨░╨▓╤И╨╕╨╣╤Б╤П ╨▒╤О╨┤╨╢╨╡╤В: {left_str}*'
        await query.edit_message_text(msg, parse_mode="MarkdownV2")
        # ╨Я╨╛╨║╨░╨╖╤Л╨▓╨░╨╡╨╝ ╤Н╤В╨░╨┐ ╨▓╤Л╨▒╨╛╤А╨░ ╨║╨░╨┐╨╕╤В╨░╨╜╨░
        return await tour_captain(update, context)
    except Exception as e:
        print(f"tour_goalie_callback ERROR: {e}", flush=True)
        logger.exception("Exception in tour_goalie_callback")
        await query.edit_message_text(f"╨Ю╤И╨╕╨▒╨║╨░: {e}")
        return TOUR_GOALIE
    finally:
        print("tour_goalie_callback FINISHED", flush=True)


async def tour_goalie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _tour_deadline_passed(context):
        await update.effective_message.reply_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤В╤Г╤А╨░ ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗. ╨б╨▒╨╛╤А ╨╕ ╨╕╨╖╨╝╨╡╨╜╨╡╨╜╨╕╤П ╤Б╨╛╤Б╤В╨░╨▓╨░ ╨╖╨░╨║╤А╤Л╤В╤Л.")
        return ConversationHandler.END
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = []
    # ╨Т╤А╨░╤В╨░╤А╤М ╤В╨╛╨╗╤М╨║╨╛ ╨╛╨┤╨╕╨╜, ╨╜╨╡ ╨╜╤Г╨╢╨╡╨╜ exclude ╨║╤А╨╛╨╝╨╡ ╤Г╨╢╨╡ ╨▓╤Л╨▒╤А╨░╨╜╨╜╨╛╨│╨╛
    if context.user_data['tour_selected']['goalie']:
        picked = [context.user_data['tour_selected']['goalie']]
    return await send_player_choice(update, context, '╨▓╤А╨░╤В╨░╤А╤М', picked, TOUR_CAPTAIN, left)


async def tour_captain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _tour_deadline_passed(context):
        await update.effective_message.reply_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤В╤Г╤А╨░ ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗. ╨б╨╛╤Б╤В╨░╨▓ ╨▒╨╛╨╗╤М╤И╨╡ ╨╝╨╡╨╜╤П╤В╤М ╨╜╨╡╨╗╤М╨╖╤П.")
        return ConversationHandler.END
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    # ╨г╨╜╨╕╨▓╨╡╤А╤Б╨░╨╗╤М╨╜╨╛ ╨┐╨╛╨╗╤Г╤З╨░╨╡╨╝ message ╨┤╨╗╤П reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message

    selected = context.user_data['tour_selected']
    roster = context.user_data['tour_roster']
    # ╨б╨╛╨▒╨╕╤А╨░╨╡╨╝ id ╨┐╨╛╨╗╨╡╨▓╤Л╤Е ╨╕╨│╤А╨╛╨║╨╛╨▓
    field_ids = selected['forwards'] + selected['defenders']
    # ╨Я╨╛╨╗╤Г╤З╨░╨╡╨╝ ╨╕╨╜╤Д╤Г ╨┐╨╛ ╨╕╨│╤А╨╛╨║╨░╨╝
    candidates = [p for p in roster if p[1] in field_ids]
    keyboard = [
        [InlineKeyboardButton(f"{p[2]} ({p[3]})", callback_data=f"pick_captain_{p[1]}")]
        for p in candidates
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "╨Э╨░╨╖╨╜╨░╤З╤М ╨╛╨┤╨╜╨╛╨│╨╛ ╨┐╨╛╨╗╨╡╨▓╨╛╨│╨╛ ╨╕╨│╤А╨╛╨║╨░ ╨╕╨╖ ╤Б╨╛╤Б╤В╨░╨▓╨░ ╨║╨░╨┐╨╕╤В╨░╨╜╨╛╨╝. ╨Х╨│╨╛ ╨╕╤В╨╛╨│╨╛╨▓╤Л╨╡ ╨╛╤З╨║╨╕ ╤Г╨╝╨╜╨╛╨╢╨╕╨╝ ╨╜╨░ 1.5"
    await message.reply_text(text, reply_markup=reply_markup)
    return TOUR_CAPTAIN

# --- ╨Ю╨▒╤А╨░╨▒╨╛╤В╤З╨╕╨║ ╨▓╤Л╨▒╨╛╤А╨░ ╨║╨░╨┐╨╕╤В╨░╨╜╨░ ---
async def tour_captain_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _tour_deadline_passed(context):
        await update.effective_message.reply_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤В╤Г╤А╨░ ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗. ╨б╨╛╤Б╤В╨░╨▓ ╨▒╨╛╨╗╤М╤И╨╡ ╨╝╨╡╨╜╤П╤В╤М ╨╜╨╡╨╗╤М╨╖╤П.")
        return ConversationHandler.END
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith('pick_captain_'):
        await query.edit_message_text('╨Э╨╡╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Л╨╣ ╨▓╤Л╨▒╨╛╤А ╨║╨░╨┐╨╕╤В╨░╨╜╨░.')
        return TOUR_CAPTAIN
    captain_id = int(data.replace('pick_captain_', ''))
    selected = context.user_data['tour_selected']
    roster = context.user_data['tour_roster']
    field_ids = selected['forwards'] + selected['defenders']
    if captain_id not in field_ids:
        await query.edit_message_text('╨Ъ╨░╨┐╨╕╤В╨░╨╜ ╨┤╨╛╨╗╨╢╨╡╨╜ ╨▒╤Л╤В╤М ╨┐╨╛╨╗╨╡╨▓╤Л╨╝ ╨╕╨│╤А╨╛╨║╨╛╨╝ ╨╕╨╖ ╨▓╨░╤И╨╡╨│╨╛ ╤Б╨╛╤Б╤В╨░╨▓╨░!')
        return TOUR_CAPTAIN
    context.user_data['tour_selected']['captain'] = captain_id
    # ╨д╨╛╤А╨╝╨╕╤А╤Г╨╡╨╝ ╨║╤А╨░╤Б╨╕╨▓╨╛╨╡ ╨╕╤В╨╛╨│╨╛╨▓╨╛╨╡ ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╡ ╤Б ╨║╨░╤Б╤В╨╛╨╝╨╜╤Л╨╝ ╤Н╨╝╨╛╨┤╨╖╨╕
    # def custom_emoji_entity(emoji_id, offset):
    #     return MessageEntity(
    #         type=MessageEntityType.CUSTOM_EMOJI,
    #         offset=offset,
    #         length=1,  # ASCII-╤Б╨╕╨╝╨▓╨╛╨╗
    #         custom_emoji_id=str(emoji_id)
    #     )

    def get_name(pid, captain=False):
        p = next((x for x in roster if x[1]==pid), None)
        if not p:
            return str(pid)
        base = f"{p[2]} ({p[4]})"
        if captain:
            return f"ЁЯПЕ {base}"
        return base

    def format_final_roster_md(goalie, defenders, forwards, captain, spent, budget):
        lines = [
            '*╨Т╨░╤И ╨╕╤В╨╛╨│╨╛╨▓╤Л╨╣ ╤Б╨╛╤Б╤В╨░╨▓:*',
            '',
            escape_md(goalie),
            escape_md(defenders),
            escape_md(forwards),
            '',
            f'╨Ъ╨░╨┐╨╕╤В╨░╨╜: {escape_md(captain)}',
            f'╨Я╨╛╤В╤А╨░╤З╨╡╨╜╨╛: *{escape_md(str(spent))}*/*{escape_md(str(budget))}*'
        ]
        return '\n'.join(lines)

    goalie_str = get_name(selected['goalie'])
    defenders_str = f"{get_name(selected['defenders'][0])} - {get_name(selected['defenders'][1])}"
    forwards_str = (
        f"{get_name(selected['forwards'][0])} - "
        f"{get_name(selected['forwards'][1])} - "
        f"{get_name(selected['forwards'][2])}"
    )
    captain_str = get_name(captain_id)
    spent = selected['spent']
    budget = context.user_data.get('tour_budget', 0)

    user_id = update.effective_user.id
    tour_id = context.user_data.get('active_tour_id', 1)
    roster_dict = {
        'goalie': selected['goalie'],
        'defenders': selected['defenders'],
        'forwards': selected['forwards']
    }
    from db import save_user_tour_roster
    # Final guard before saving
    if _tour_deadline_passed(context):
        await update.effective_message.reply_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤В╤Г╤А╨░ ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗. ╨б╨╛╤Б╤В╨░╨▓ ╨▒╨╛╨╗╤М╤И╨╡ ╨╝╨╡╨╜╤П╤В╤М ╨╜╨╡╨╗╤М╨╖╤П.")
        return ConversationHandler.END
    save_user_tour_roster(user_id, tour_id, roster_dict, captain_id, spent)

    text = format_final_roster_md(goalie_str, defenders_str, forwards_str, captain_str, spent, budget)
    keyboard = [[InlineKeyboardButton('╨Я╨╡╤А╨╡╤Б╨╛╨▒╤А╨░╤В╤М ╤Б╨╛╤Б╤В╨░╨▓', callback_data='restart_tour')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )
    return ConversationHandler.END


async def restart_tour_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from db import get_active_tour, clear_user_tour_roster
    query = update.callback_query
    await query.answer()
    if _tour_deadline_passed(context):
        await query.edit_message_text("╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤В╤Г╤А╨░ ╤Г╨╢╨╡ ╨┐╤А╨╛╤И╤С╨╗. ╨б╨▒╨╛╤А ╨╕ ╨╕╨╖╨╝╨╡╨╜╨╡╨╜╨╕╤П ╤Б╨╛╤Б╤В╨░╨▓╨░ ╨╖╨░╨║╤А╤Л╤В╤Л.")
        return ConversationHandler.END
    user_id = query.from_user.id
    active_tour = get_active_tour()
    if active_tour:
        tour_id = active_tour['id']
        clear_user_tour_roster(user_id, tour_id)
    # ╨Ч╨░╨┐╤Г╤Б╨║╨░╨╡╨╝ ╨┐╤А╨╛╤Ж╨╡╤Б╤Б ╨▓╤Л╨▒╨╛╤А╨░ ╤Б╨╛╤Б╤В╨░╨▓╨░ ╨╖╨░╨╜╨╛╨▓╨╛ ╤З╨╡╤А╨╡╨╖ /tour (ConversationHandler entry_point)
    await context.bot.send_message(chat_id=query.message.chat_id, text="/tour")
    return ConversationHandler.END

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from db import get_budget
    # ╨г╨╜╨╕╨▓╨╡╤А╤Б╨░╨╗╤М╨╜╨╛ ╨┐╨╛╨╗╤Г╤З╨░╨╡╨╝ message ╨┤╨╗╤П reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message
    budget = get_budget()
    budget_str = str(budget).replace("-", r"\-") if budget is not None else 'N/A'
    text = rf"""*╨Я╤А╨░╨▓╨╕╨╗╨░ ╨╕╨│╤А╤Л:*

╨б╨╛╨▒╨╡╤А╨╕╤В╨╡ ╤Б╨▓╨╛╤О ╨║╨╛╨╝╨░╨╜╨┤╤Г ╨╕╨╖ 6 ╨╕╨│╤А╨╛╨║╨╛╨▓ \(3 ╨╜╨░╨┐╨░╨┤╨░╤О╤Й╨╕╤Е, 2 ╨╖╨░╤Й╨╕╤В╨╜╨╕╨║╨░, 1 ╨▓╤А╨░╤В╨░╤А╤М\) ╤Б ╨╛╨│╤А╨░╨╜╨╕╤З╨╡╨╜╨╜╤Л╨╝ ╨▒╤О╨┤╨╢╨╡╤В╨╛╨╝\. ╨г ╨║╨░╨╢╨┤╨╛╨│╨╛ ╨╕╨│╤А╨╛╨║╨░ ╤Б╨▓╨╛╤П ╤Б╤В╨╛╨╕╨╝╨╛╤Б╤В╤М \- 10, 30, 40 ╨╕╨╗╨╕ 50 ╨╡╨┤╨╕╨╜╨╕╤Ж\.

тЪбя╕П ╨Э╨░╨╖╨╜╨░╤З╤М ╨╛╨┤╨╜╨╛╨│╨╛ ╨┐╨╛╨╗╨╡╨▓╨╛╨│╨╛ ╨╕╨│╤А╨╛╨║╨░ ╨╕╨╖ ╤Б╨╛╤Б╤В╨░╨▓╨░ ╨║╨░╨┐╨╕╤В╨░╨╜╨╛╨╝

*╨Т╨░╤И ╨▒╤О╨┤╨╢╨╡╤В: {budget_str}*

╨б╨╛╨▒╤А╨░╤В╤М ╤Б╨╛╤Б╤В╨░╨▓ \- /tour"""
    await message.reply_text(text, parse_mode="MarkdownV2")

async def hc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ╨г╨╜╨╕╨▓╨╡╤А╤Б╨░╨╗╤М╨╜╨╛ ╨┐╨╛╨╗╤Г╤З╨░╨╡╨╝ message ╨┤╨╗╤П reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message

    user = update.effective_user
    data = db.get_user_by_id(user.id)
    if data:
        await message.reply_text(f'ЁЯТ░ ╨в╨▓╨╛╨╣ ╨▒╨░╨╗╨░╨╜╤Б: {data[3]} HC')
    else:
        await message.reply_text(
            'ЁЯЪл ╨в╨╡╨▒╤П ╨╡╤Й╨╡ ╨╜╨╡╤В ╨▓ ╤Б╨┐╨╕╤Б╨║╨╡ ╨│╨╡╨╜╨╝╨╡╨╜╨╡╨┤╨╢╨╡╤А╨╛╨▓ ╨д╨╡╨╜╤В╨╡╨╖╨╕ ╨Ф╤А╨░╤Д╤В ╨Ъ╨е╨Ы\n\n'
            '╨Ч╨░╤А╨╡╨│╨╕╤Б╤В╤А╨╕╤А╤Г╨╣╤Б╤П ╤З╨╡╤А╨╡╨╖ /start тАФ ╨╕ ╨▓╨┐╨╡╤А╤С╨┤ ╨║ ╤Б╨▒╨╛╤А╨║╨╡ ╤Б╨╛╤Б╤В╨░╨▓╨░!'
        )

