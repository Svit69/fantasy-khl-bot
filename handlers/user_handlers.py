from telegram import Update, InputFile, ReplyKeyboardMarkup, MessageEntity, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from telegram.error import BadRequest
from telegram.constants import MessageEntityType
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
import db
import os
from utils import is_admin, IMAGES_DIR, logger, CHALLENGE_IMAGE_PATH_FILE

def escape_md(text):
    # Р’СЃРµ СЃРїРµС†СЃРёРјРІРѕР»С‹ MarkdownV2
    for ch in r'\_*[]()~`>#+-=|{}.!':
        text = text.replace(ch, '\\' + ch)
    return text

async def send_player_selected_message(query, player, budget, context):
    left = budget - context.user_data['tour_selected']['spent']
    player_name = escape_md(str(player[2]))
    cost = escape_md(str(player[7]))
    left_str = escape_md(str(left))
    msg = f'Р’С‹ РІС‹Р±СЂР°Р»Рё {player_name} \\({cost}\\)\n\n*РћСЃС‚Р°РІС€РёР№СЃСЏ Р±СЋРґР¶РµС‚: {left_str}*'
    await query.edit_message_text(msg, parse_mode="MarkdownV2")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # РЈРЅРёРІРµСЂСЃР°Р»СЊРЅРѕ РїРѕР»СѓС‡Р°РµРј message РґР»СЏ reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message
    user = update.effective_user
    registered = db.register_user(user.id, user.username, user.full_name)

    # --- Р РµС„РµСЂР°Р»: РµСЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїСЂРёС€С‘Р» РїРѕ СЃСЃС‹Р»РєРµ ref_<id>,
    # Рё СЌС‚Рѕ РµРіРѕ РџР•Р Р’РђРЇ СЂРµРіРёСЃС‚СЂР°С†РёСЏ (registered == True), РЅР°С‡РёСЃР»СЏРµРј СЂРµС„РµСЂРµСЂСѓ +50 HC
    try:
        if registered and getattr(context, 'args', None):
            arg0 = context.args[0] if len(context.args) > 0 else ''
            if isinstance(arg0, str) and arg0.startswith('ref_'):
                ref_str = arg0[4:]
                if ref_str.isdigit():
                    referrer_id = int(ref_str)
                    if referrer_id != user.id:
                        # Р’СЃС‚Р°РІРёРј Р·Р°РїРёСЃСЊ СЂРµС„РµСЂР°Р»Р°, РµСЃР»Рё РґР»СЏ СЌС‚РѕРіРѕ user_id РµС‘ РµС‰С‘ РЅРµ Р±С‹Р»Рѕ
                        if db.add_referral_if_new(user.id, referrer_id):
                            # Р‘РѕРЅСѓСЃ Р·Р°РІРёСЃРёС‚ РѕС‚ Р°РєС‚РёРІРЅРѕСЃС‚Рё РїРѕРґРїРёСЃРєРё Сѓ СЂРµС„РµСЂРµСЂР°
                            try:
                                from db import is_subscription_active
                                bonus = 100 if is_subscription_active(referrer_id) else 50
                            except Exception:
                                bonus = 50
                            db.update_hc_balance(referrer_id, bonus)
                            # РЈРІРµРґРѕРјРёРј СЂРµС„РµСЂРµСЂР° (РµСЃР»Рё РјРѕР¶РЅРѕ)
                            try:
                                new_balance = db.get_user_by_id(referrer_id)
                                new_balance = new_balance[3] if new_balance else 'вЂ”'
                                await context.bot.send_message(
                                    chat_id=referrer_id,
                                    text=f'рџЋ‰ РџРѕ РІР°С€РµР№ СЂРµС„РµСЂР°Р»СЊРЅРѕР№ СЃСЃС‹Р»РєРµ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°Р»СЃСЏ РЅРѕРІС‹Р№ СѓС‡Р°СЃС‚РЅРёРє!\n+{bonus} HC РЅР°С‡РёСЃР»РµРЅРѕ. РўРµРєСѓС‰РёР№ Р±Р°Р»Р°РЅСЃ: {new_balance} HC.'
                                )
                            except Exception:
                                pass
                            # РЎРѕРѕР±С‰РёРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ, С‡С‚Рѕ РѕРЅ РїСЂРёС€С‘Р» РїРѕ СЃСЃС‹Р»РєРµ
                            try:
                                await message.reply_text('Р’С‹ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°Р»РёСЃСЊ РїРѕ СЂРµС„РµСЂР°Р»СЊРЅРѕР№ СЃСЃС‹Р»РєРµ вЂ” РґРѕР±СЂРѕ РїРѕР¶Р°Р»РѕРІР°С‚СЊ!')
                            except Exception:
                                pass
    except Exception as e:
        # РќРµ РїСЂРµСЂС‹РІР°РµРј СЃС‚Р°СЂС‚ РїСЂРё РѕС€РёР±РєРµ СЂРµС„РµСЂР°Р»СЊРЅРѕР№ РѕР±СЂР°Р±РѕС‚РєРё
        try:
            await message.reply_text(f"[WARN] РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё СЂРµС„РµСЂР°Р»Р°: {e}")
        except Exception:
            pass
    msg_id = f"Р’Р°С€ Telegram ID: {user.id}\n"
    if is_admin(user.id):
        keyboard = [["/tour", "/hc"], ["/send_tour_image", "/addhc", "/send_results", "/add_player", "/list_players"]]
        msg = (
            f'РџСЂРёРІРµС‚, {user.full_name}! РўС‹ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅ РєР°Рє Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ Fantasy KHL.\n\n'
            'Р”РѕСЃС‚СѓРїРЅС‹Рµ РєРѕРјР°РЅРґС‹:\n/tour вЂ” РїРѕРєР°Р·Р°С‚СЊ СЃРѕСЃС‚Р°РІ РЅР° С‚СѓСЂ\n/hc вЂ” Р±Р°Р»Р°РЅСЃ HC\n/send_tour_image вЂ” Р·Р°РіСЂСѓР·РёС‚СЊ Рё СЂР°Р·РѕСЃР»Р°С‚СЊ РёР·РѕР±СЂР°Р¶РµРЅРёРµ С‚СѓСЂР°\n/addhc вЂ” РЅР°С‡РёСЃР»РёС‚СЊ HC РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ\n/send_results вЂ” СЂР°Р·РѕСЃР»Р°С‚СЊ СЂРµР·СѓР»СЊС‚Р°С‚ С‚СѓСЂР°\n/add_player вЂ” РґРѕР±Р°РІРёС‚СЊ РёРіСЂРѕРєР°\n/list_players вЂ” СЃРїРёСЃРѕРє РёРіСЂРѕРєРѕРІ'
        )
    else:
        keyboard = [["/tour", "/hc", "/rules", "/shop"]]
        msg = (
            f'РџСЂРёРІРµС‚, {user.full_name}! Р”РѕР±СЂРѕ РїРѕР¶Р°Р»РѕРІР°С‚СЊ РІ Р¤РµРЅС‚РµР·Рё Р”СЂР°С„С‚ РљРҐР›\n\n'
            'рџ”ё РЎРѕР±РёСЂР°Р№ СЃРІРѕСЋ РєРѕРјР°РЅРґСѓ РЅР° РєР°Р¶РґС‹Р№ С‚СѓСЂ\n'
            'рџ”ё РЎР»РµРґРё Р·Р° СЂРµР·СѓР»СЊС‚Р°С‚Р°РјРё С‚СѓСЂРѕРІ\n'
            'рџ”ё Р—Р°СЂР°Р±Р°С‚С‹РІР°Р№ Рё РєРѕРїРё Hockey Coin (HC)\n'
            'рџ”ё РњРµРЅСЏР№ Hockey Coin (HC) РЅР° РїСЂРёР·С‹\n\n'
            'Р”РѕСЃС‚СѓРїРЅС‹Рµ РєРѕРјР°РЅРґС‹:\n'
            '/tour вЂ” С‚СѓСЂ Рё СѓРїСЂР°РІР»РµРЅРёРµ РєРѕРјР°РЅРґРѕР№\n'
            '/hc вЂ” С‚РІРѕР№ Р±Р°Р»Р°РЅСЃ Hockey Coin\n'
            '/rules вЂ” РїСЂР°РІРёР»Р° СЃР±РѕСЂРєРё СЃРѕСЃС‚Р°РІРѕРІ\n'
            '/shop вЂ” РјР°РіР°Р·РёРЅ РїСЂРёР·РѕРІ'
        )
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    if registered:
        await message.reply_text(msg_id + msg, reply_markup=markup)
    else:
        await message.reply_text(
            escape_md("вљ пёЏ РўС‹ СѓР¶Рµ РІ СЃРїРёСЃРєРµ РіРµРЅРµСЂР°Р»СЊРЅС‹С… РјРµРЅРµРґР¶РµСЂРѕРІ Р¤РµРЅС‚РµР·Рё Р”СЂР°С„С‚Р° РљРҐР›.\n\nР¤РѕСЂРјРёСЂСѓР№ СЃРѕСЃС‚Р°РІ Рё СЃР»РµРґРё Р·Р° СЂРµР·СѓР»СЊС‚Р°С‚Р°РјРё С‚СѓСЂРѕРІ - /tour"),
            reply_markup=markup,
            parse_mode="MarkdownV2"
        )

# --- TOUR ConversationHandler states ---

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    # РћРїСЂРµРґРµР»РёРј С‚РµРєСѓС‰РёР№ Р±РѕРЅСѓСЃ: 100 HC РїСЂРё Р°РєС‚РёРІРЅРѕР№ РїРѕРґРїРёСЃРєРµ, РёРЅР°С‡Рµ 50 HC
    try:
        from db import is_subscription_active
        bonus = 100 if is_subscription_active(user.id) else 50
    except Exception:
        bonus = 50
    text = (
        f"рџ”— Р’Р°С€Р° СЂРµС„РµСЂР°Р»СЊРЅР°СЏ СЃСЃС‹Р»РєР°:\n"
        f"{link}\n\n"
        f"РџСЂРёРіР»Р°С€Р°Р№С‚Рµ РґСЂСѓР·РµР№! Р—Р° РєР°Р¶РґРѕРіРѕ РЅРѕРІРѕРіРѕ СѓС‡Р°СЃС‚РЅРёРєР° РІС‹ РїРѕР»СѓС‡РёС‚Рµ +{bonus} HC РїРѕСЃР»Рµ РµРіРѕ СЂРµРіРёСЃС‚СЂР°С†РёРё."
    )
    keyboard = [[InlineKeyboardButton('РЎРєРѕРїРёСЂРѕРІР°С‚СЊ СЃСЃС‹Р»РєСѓ', url=link)]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from utils import create_yookassa_payment
    user = update.effective_user
    payment_url, payment_id = create_yookassa_payment(user.id)
    # РЎРѕС…СЂР°РЅСЏРµРј payment_id РІ Р‘Р” (РјРѕР¶РЅРѕ РґРѕР±Р°РІРёС‚СЊ С„СѓРЅРєС†РёСЋ)
    # db.save_payment_id(user.id, payment_id)
    # РџСЂРѕРІРµСЂРёРј СЃС‚Р°С‚СѓСЃ РїРѕРґРїРёСЃРєРё Рё РґР°С‚Сѓ РѕРєРѕРЅС‡Р°РЅРёСЏ
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
                # РџСЂРµРѕР±СЂР°Р·СѓРµРј Рє Р»РѕРєР°Р»СЊРЅРѕРјСѓ РІСЂРµРјРµРЅРё РґР»СЏ СѓРґРѕР±СЃС‚РІР°
                local_dt = dt.astimezone() if dt.tzinfo else dt
                end_line = f"\n<b>РџРѕРґРїРёСЃРєР° Р°РєС‚РёРІРЅР°</b> РґРѕ: <b>{local_dt.strftime('%d.%m.%Y %H:%M')}</b>"
    except Exception:
        pass

    benefits = (
        "\n\n<b>РџСЂРµРёРјСѓС‰РµСЃС‚РІР° РїРѕРґРїРёСЃРєРё:</b>\n"
        "вЂў Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Р№ РёРіСЂРѕРє РІ РїСѓР» РЅР° С‚СѓСЂ\n"
        "вЂў РџРѕРІС‹С€РµРЅРЅС‹Рµ СЂРµС„РµСЂР°Р»СЊРЅС‹Рµ Р±РѕРЅСѓСЃС‹\n"
        "вЂў РџСЂРёРѕСЂРёС‚РµС‚РЅР°СЏ РїРѕРґРґРµСЂР¶РєР°\n"
        "вЂў РќРѕРІС‹Рµ С„РёС‡Рё СЂР°РЅСЊС€Рµ РІСЃРµС…"
    )

    text = (
        f"рџ’і <b>РџРѕРґРїРёСЃРєР° РЅР° Fantasy KHL</b>\n\n"
        f"РЎС‚РѕРёРјРѕСЃС‚СЊ: <b>299 СЂСѓР±/РјРµСЃСЏС†</b>"
        f"{end_line}\n\n"
        f"РќР°Р¶РјРёС‚Рµ РєРЅРѕРїРєСѓ РЅРёР¶Рµ РґР»СЏ РѕРїР»Р°С‚С‹ С‡РµСЂРµР· Р®Kassa. РџРѕСЃР»Рµ СѓСЃРїРµС€РЅРѕР№ РѕРїР»Р°С‚С‹ РїРѕРґРїРёСЃРєР° Р°РєС‚РёРІРёСЂСѓРµС‚СЃСЏ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё."
        f"{benefits}"
    )
    keyboard = [[InlineKeyboardButton('РћРїР»Р°С‚РёС‚СЊ 299в‚Ѕ С‡РµСЂРµР· Р®Kassa', url=payment_url)]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# --- Telegram Stars payments ---

async def subscribe_stars(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """РћС„РѕСЂРјР»РµРЅРёРµ РїРѕРґРїРёСЃРєРё С‡РµСЂРµР· Telegram Stars (invoice)."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    # РРЅС„РѕСЂРјР°С†РёСЏ Рѕ С‚РµРєСѓС‰РµР№ РїРѕРґРїРёСЃРєРµ, РµСЃР»Рё Р°РєС‚РёРІРЅР°
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
                end_line = f"\n<b>РўРµРєСѓС‰Р°СЏ РїРѕРґРїРёСЃРєР° Р°РєС‚РёРІРЅР°</b> РґРѕ: <b>{local_dt.strftime('%d.%m.%Y %H:%M')}</b>"
    except Exception:
        pass

    # Р¤РѕСЂРјРёСЂСѓРµРј invoice РґР»СЏ Telegram Stars
    from utils import SUBSCRIPTION_STARS
    title = "РџРѕРґРїРёСЃРєР° Fantasy KHL вЂ” 1 РјРµСЃСЏС†"
    description = (
        "Р”РѕСЃС‚СѓРї Рє РїСЂРµРјРёСѓРј-С„СѓРЅРєС†РёСЏРј Рё Р±РѕРЅСѓСЃР°Рј РІ Р±РѕС‚Рµ." + end_line
    )
    payload = f"sub_{user.id}"
    prices = [LabeledPrice(label="РџРѕРґРїРёСЃРєР° РЅР° 1 РјРµСЃСЏС†", amount=int(SUBSCRIPTION_STARS))]

    # РћС‚РїСЂР°РІР»СЏРµРј invoice: currency XTR вЂ” РѕРїР»Р°С‚Р° Telegram Stars
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

    # РџРѕСЏСЃРЅСЏСЋС‰РµРµ СЃРѕРѕР±С‰РµРЅРёРµ
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "РќР°Р¶РјРёС‚Рµ РєРЅРѕРїРєСѓ РћРїР»Р°С‚РёС‚СЊ РІ СЃС‡С‘С‚Рµ РІС‹С€Рµ, С‡С‚РѕР±С‹ Р·Р°РІРµСЂС€РёС‚СЊ РѕРїР»Р°С‚Сѓ С‡РµСЂРµР· Telegram Stars.\n"
                "РџРѕСЃР»Рµ СѓСЃРїРµС€РЅРѕР№ РѕРїР»Р°С‚С‹ РїРѕРґРїРёСЃРєР° Р°РєС‚РёРІРёСЂСѓРµС‚СЃСЏ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё."
            )
        )
    except Exception:
        pass


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """РџРѕРґС‚РІРµСЂР¶РґР°РµРј РїСЂРµРґС‡РµРє-Р°СѓС‚ РґР»СЏ СЃС‡С‘С‚Р° (РІ С‚.С‡. РґР»СЏ Stars)."""
    try:
        query = update.pre_checkout_query
    except AttributeError:
        return
    try:
        await query.answer(ok=True)
    except Exception:
        # Р’ СЃР»СѓС‡Р°Рµ РѕС€РёР±РєРё РїСЂРѕР±СѓРµРј РѕС‚РєР»РѕРЅРёС‚СЊ СЃ РїРѕСЏСЃРЅРµРЅРёРµРј
        try:
            await query.answer(ok=False, error_message="РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґС‚РІРµСЂРґРёС‚СЊ РѕРїР»Р°С‚Сѓ. РџРѕРїСЂРѕР±СѓР№С‚Рµ РїРѕР·Р¶Рµ.")
        except Exception:
            pass


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """РћР±СЂР°Р±РѕС‚РєР° СѓСЃРїРµС€РЅРѕР№ РѕРїР»Р°С‚С‹: Р°РєС‚РёРІРёСЂСѓРµРј/РїСЂРѕРґР»РµРІР°РµРј РїРѕРґРїРёСЃРєСѓ."""
    try:
        sp = update.message.successful_payment if getattr(update, 'message', None) else None
        if not sp:
            return
        import datetime
        user = update.effective_user
        from db import get_subscription, add_or_update_subscription

        # РџСЂРѕРґР»РµРЅРёРµ РЅР° 31 РґРµРЅСЊ РѕС‚ С‚РµРєСѓС‰РµР№ РґР°С‚С‹ РёР»Рё РґР°С‚С‹ РѕРєРѕРЅС‡Р°РЅРёСЏ Р°РєС‚РёРІРЅРѕР№ РїРѕРґРїРёСЃРєРё
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

        # РЎРѕС…СЂР°РЅСЏРµРј РёРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ РїР»Р°С‚РµР¶Р° РёР· Telegram
        last_payment_id = None
        try:
            last_payment_id = getattr(sp, 'telegram_payment_charge_id', None) or getattr(sp, 'provider_payment_charge_id', None)
        except Exception:
            last_payment_id = None
        last_payment_id = f"stars:{last_payment_id or ''}"

        add_or_update_subscription(user.id, new_paid_until.isoformat(), last_payment_id)

        local_dt = new_paid_until.astimezone() if new_paid_until.tzinfo else new_paid_until
        await update.message.reply_text(
            f"РЎРїР°СЃРёР±Рѕ! РћРїР»Р°С‚Р° РїРѕР»СѓС‡РµРЅР°. РџРѕРґРїРёСЃРєР° Р°РєС‚РёРІРЅР° РґРѕ {local_dt.strftime('%d.%m.%Y %H:%M')} (MSK)."
        )
    except Exception:
        try:
            await update.message.reply_text("РћРїР»Р°С‚Р° СѓСЃРїРµС€РЅРѕ РїСЂРѕС€Р»Р°, РЅРѕ РїСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР° РїСЂРё Р°РєС‚РёРІР°С†РёРё. РЎРІСЏР¶РёС‚РµСЃСЊ СЃ Р°РґРјРёРЅРѕРј.")
        except Exception:
            pass


# --- TOURS LIST (/tours) ---
async def tours(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """РџРѕРєР°Р·Р°С‚СЊ СЃРїРёСЃРѕРє РІСЃРµС… С‚СѓСЂРѕРІ СЃ РєРЅРѕРїРєР°РјРё РґР»СЏ РѕС‚РєСЂС‹С‚РёСЏ РїРѕРґСЂРѕР±РЅРѕСЃС‚РµР№."""
    try:
        rows = db.get_all_tours() or []
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ СЃРїРёСЃРєР° С‚СѓСЂРѕРІ: {e}")
        return
    # РћС‚С„РёР»СЊС‚СЂСѓРµРј Р±СѓРґСѓС‰РёРµ С‚СѓСЂС‹ (start_date > now)
    import datetime
    now = datetime.datetime.now()
    filtered = []
    for r in rows:
        # r: (id, name, start, deadline, end, status, winners)
        try:
            start_dt = datetime.datetime.strptime(str(r[2]), "%d.%m.%y")
            if start_dt <= now:
                filtered.append(r)
        except Exception:
            # РµСЃР»Рё РЅРµ СѓРґР°Р»РѕСЃСЊ СЂР°СЃРїР°СЂСЃРёС‚СЊ РґР°С‚Сѓ вЂ” РїРµСЂРµСЃС‚СЂР°С…СѓРµРјСЃСЏ Рё РЅРµ РїРѕРєР°Р·С‹РІР°РµРј С‚Р°РєРѕР№ С‚СѓСЂ
            continue
    rows = filtered
    if not rows:
        await update.message.reply_text("РќРµС‚ Р°РєС‚РёРІРЅС‹С… С‚СѓСЂРѕРІ. Р—Р°РіР»СЏРЅРёС‚Рµ РїРѕР·Р¶Рµ!")
        return
    # Р¤РѕСЂРјРёСЂСѓРµРј СЃРїРёСЃРѕРє Рё РєРЅРѕРїРєРё
    lines = ["*Р”РѕСЃС‚СѓРїРЅС‹Рµ С‚СѓСЂС‹:*"]
    buttons = []
    for r in rows:
        # r: (id, name, start, deadline, end, status, winners)
        tid, name, start, deadline, end, status, winners = r
        lines.append(f"вЂў #{tid} вЂ” {name} [{status}]")
        buttons.append([InlineKeyboardButton(f"РћС‚РєСЂС‹С‚СЊ #{tid}", callback_data=f"tour_open_{tid}")])
    await update.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')


async def tour_open_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """РћС‚РєСЂС‹С‚СЊ РёРЅС„РѕСЂРјР°С†РёСЋ РїРѕ РІС‹Р±СЂР°РЅРЅРѕРјСѓ С‚СѓСЂСѓ: РґР°С‚С‹, СЃС‚Р°С‚СѓСЃ, РєР°СЂС‚РёРЅРєР° (РµСЃР»Рё РµСЃС‚СЊ)."""
    query = update.callback_query
    await query.answer()
    data = query.data  # tour_open_<id>
    try:
        tid = int(data.replace('tour_open_', ''))
    except Exception:
        await query.edit_message_text("РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ Р·Р°РїСЂРѕСЃ С‚СѓСЂР°.")
        return
    row = None
    try:
        row = db.get_tour_by_id(tid)
    except Exception:
        row = None
    if not row:
        await query.edit_message_text("РўСѓСЂ РЅРµ РЅР°Р№РґРµРЅ.")
        return
    # Р‘Р»РѕРєРёСЂСѓРµРј РїСЂРѕСЃРјРѕС‚СЂ Р±СѓРґСѓС‰РёС… С‚СѓСЂРѕРІ
    try:
        import datetime
        start_dt = datetime.datetime.strptime(str(row[2]), "%d.%m.%y")
        if datetime.datetime.now() < start_dt:
            await query.edit_message_text("РўСѓСЂ РµС‰С‘ РЅРµ РЅР°С‡Р°Р»СЃСЏ. Р—Р°РіР»СЏРЅРёС‚Рµ РїРѕР·Р¶Рµ!")
            return
    except Exception:
        pass
    # row: (id, name, start, deadline, end, status, winners, image_filename, image_file_id)
    # 1) Р’СЃРµРіРґР° РїС‹С‚Р°РµРјСЃСЏ РѕС‚РїСЂР°РІРёС‚СЊ РєР°СЂС‚РёРЅРєСѓ С‚СѓСЂР°
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

    # 2) РџСЂРѕРІРµСЂСЏРµРј, СЃРѕР±СЂР°РЅ Р»Рё СѓР¶Рµ СЃРѕСЃС‚Р°РІ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РґР»СЏ СЌС‚РѕРіРѕ С‚СѓСЂР°
    user_id = update.effective_user.id if update.effective_user else None
    user_roster = None
    try:
        if user_id:
            user_roster = db.get_user_tour_roster(user_id, row[0])
    except Exception:
        user_roster = None

    if user_roster and isinstance(user_roster, dict) and user_roster.get('roster'):
        # РџРѕРєР°Р·Р°С‚СЊ СЃРѕСЃС‚Р°РІ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РІ Р·Р°РїСЂРѕС€РµРЅРЅРѕРј С„РѕСЂРјР°С‚Рµ
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

        # Р’СЂР°С‚Р°СЂСЊ
        goalie_line = ""
        try:
            gid = roster.get('goalie')
            if gid:
                goalie_line = name_club(gid)
        except Exception:
            pass

        # Р—Р°С‰РёС‚РЅРёРєРё
        defenders_line = ""
        try:
            dids = roster.get('defenders', []) or []
            defenders_line = " - ".join([name_club(x) for x in dids if x])
        except Exception:
            pass

        # РќР°РїР°РґР°СЋС‰РёРµ
        forwards_line = ""
        try:
            fids = roster.get('forwards', []) or []
            forwards_line = " - ".join([name_club(x) for x in fids if x])
        except Exception:
            pass

        # РљР°РїРёС‚Р°РЅ
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
            f"РљР°РїРёС‚Р°РЅ: {captain_line}" if captain_line else "РљР°РїРёС‚Р°РЅ: вЂ”",
            f"РџРѕС‚СЂР°С‡РµРЅРѕ: {spent}/{budget}",
        ]
        text = "\n".join([l for l in lines if l is not None])
        # Р•СЃР»Рё РґРµРґР»Р°Р№РЅ РµС‰С‘ РЅРµ РёСЃС‚С‘Рє вЂ” РїРѕРєР°Р·Р°С‚СЊ РєРЅРѕРїРєСѓ "РџРµСЂРµСЃРѕР±СЂР°С‚СЊ СЃРѕСЃС‚Р°РІ"
        reply_markup = None
        try:
            import datetime
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            deadline_dt = datetime.datetime.strptime(str(row[3]), "%d.%m.%y %H:%M")
            now = datetime.datetime.now()
            if now < deadline_dt:
                reply_markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton('РџРµСЂРµСЃРѕР±СЂР°С‚СЊ СЃРѕСЃС‚Р°РІ', callback_data='restart_tour')]]
                )
        except Exception:
            reply_markup = None
        try:
            await query.edit_message_text(text, reply_markup=reply_markup)
        except Exception:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)
        return ConversationHandler.END if 'ConversationHandler' in globals() else None
    else:
        # РЎРѕСЃС‚Р°РІР° РЅРµС‚ вЂ” РїРѕРєР°Р·Р°С‚СЊ РёРЅС„Рѕ Рё РїСЂРµРґР»РѕР¶РёС‚СЊ РЅР°С‡Р°С‚СЊ СЃР±РѕСЂРєСѓ С‡РµСЂРµР· entry-point РєРЅРѕРїРєРѕР№
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        text = (
            f"РўСѓСЂ #{row[0]} вЂ” {row[1]}\n"
            f"РЎС‚Р°С‚СѓСЃ: {row[5]}\n"
            f"РЎС‚Р°СЂС‚: {row[2]}\nР”РµРґР»Р°Р№РЅ: {row[3]}\nРћРєРѕРЅС‡Р°РЅРёРµ: {row[4]}\n\n"
            f"РќР°Р¶РјРёС‚Рµ РєРЅРѕРїРєСѓ РЅРёР¶Рµ, С‡С‚РѕР±С‹ РЅР°С‡Р°С‚СЊ СЃР±РѕСЂРєСѓ СЃРѕСЃС‚Р°РІР°."
        )
        keyboard = [[InlineKeyboardButton("РЎРѕР±СЂР°С‚СЊ СЃРѕСЃС‚Р°РІ", callback_data=f"tour_build_{row[0]}")]]
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
        # РќРµ Р°РєС‚РёРІРёСЂСѓРµРј CH РЅР°РїСЂСЏРјСѓСЋ вЂ” РІС…РѕРґ С‡РµСЂРµР· РєРЅРѕРїРєСѓ 'tour_build_<id>'
        return


async def tour_build_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """РЎС‚Р°СЂС‚ СЃР±РѕСЂРєРё СЃРѕСЃС‚Р°РІР° РїРѕ РІС‹Р±СЂР°РЅРЅРѕРјСѓ С‚СѓСЂСѓ: РґРµР»РµРіРёСЂСѓРµРј РІ tour_start РєР°Рє entry-point."""
    query = update.callback_query
    await query.answer()
    # РњРѕР¶РЅРѕ СЃРѕС…СЂР°РЅРёС‚СЊ РІС‹Р±СЂР°РЅРЅС‹Р№ tour_id, РµСЃР»Рё РїРѕРЅР°РґРѕР±РёС‚СЃСЏ РІ Р±СѓРґСѓС‰РµРј
    try:
        tid = int(query.data.replace('tour_build_', ''))
        context.user_data['selected_tour_id'] = tid
    except Exception:
        tid = None
    # Р—Р°РїСѓСЃРєР°РµРј СЃС†РµРЅР°СЂРёР№ СЃР±РѕСЂРєРё СЃРѕСЃС‚Р°РІР°
    return await tour_start(update, context)


# --- CHALLENGE ---
async def challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    # РўРѕР»СЊРєРѕ РґР»СЏ РїРѕРґРїРёСЃС‡РёРєРѕРІ
    try:
        from db import is_subscription_active
        if not is_subscription_active(user.id):
            await update.message.reply_text("Р¤СѓРЅРєС†РёСЏ РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ РїРѕРґРїРёСЃС‡РёРєР°Рј. РћС„РѕСЂРјРёС‚Рµ РїРѕРґРїРёСЃРєСѓ: /subscribe")
            return
    except Exception:
        await update.message.reply_text("РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕРІРµСЂРёС‚СЊ РїРѕРґРїРёСЃРєСѓ. РџРѕРїСЂРѕР±СѓР№С‚Рµ РїРѕР·Р¶Рµ РёР»Рё РѕС„РѕСЂРјРёС‚Рµ /subscribe.")
        return

    # РЎРїРёСЃРѕРє РґРѕСЃС‚СѓРїРЅС‹С… С‡РµР»Р»РµРЅРґР¶РµР№: РІСЃРµ СЃРѕ СЃС‚Р°С‚СѓСЃРѕРј "Р°РєС‚РёРІРµРЅ" Рё "РІ РёРіСЂРµ". Р•СЃР»Рё С‚Р°РєРёС… РЅРµС‚ вЂ” РїРѕРєР°Р·Р°С‚СЊ РїРѕСЃР»РµРґРЅРёР№ "Р·Р°РІРµСЂС€РµРЅ".
    challenges = []
    try:
        challenges = db.get_all_challenges() or []
    except Exception:
        challenges = []

    active_or_play = [c for c in challenges if len(c) > 5 and c[5] in ("Р°РєС‚РёРІРµРЅ", "РІ РёРіСЂРµ")]
    last_finished = None
    if challenges:
        # РІС‹Р±СЂР°С‚СЊ РїРѕСЃР»РµРґРЅРёР№ Р·Р°РІРµСЂС€РµРЅРЅС‹Р№ РїРѕ end_date
        try:
            import datetime
            finished = [c for c in challenges if len(c) > 5 and c[5] == "Р·Р°РІРµСЂС€РµРЅ"]
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
        await update.message.reply_text("РЎРµР№С‡Р°СЃ РЅРµС‚ РґРѕСЃС‚СѓРїРЅС‹С… С‡РµР»Р»РµРЅРґР¶РµР№. Р—Р°РіР»СЏРЅРёС‚Рµ РїРѕР·Р¶Рµ.")
        return

    lines = ["*Р”РѕСЃС‚СѓРїРЅС‹Рµ С‡РµР»Р»РµРЅРґР¶Рё:*"]
    # Р’СЃРїРѕРјРѕРіР°С‚РµР»СЊРЅР°СЏ С„СѓРЅРєС†РёСЏ: ISO -> С‚РµРєСЃС‚ РІ РњРЎРљ (Europe/Moscow)
    def iso_to_msk_text(dt_str: str) -> str:
        import datetime as _dt
        months = [
            "СЏРЅРІР°СЂСЏ", "С„РµРІСЂР°Р»СЏ", "РјР°СЂС‚Р°", "Р°РїСЂРµР»СЏ", "РјР°СЏ", "РёСЋРЅСЏ",
            "РёСЋР»СЏ", "Р°РІРіСѓСЃС‚Р°", "СЃРµРЅС‚СЏР±СЂСЏ", "РѕРєС‚СЏР±СЂСЏ", "РЅРѕСЏР±СЂСЏ", "РґРµРєР°Р±СЂСЏ"
        ]
        if not dt_str:
            return ""
        try:
            dt = _dt.datetime.fromisoformat(str(dt_str))
        except Exception:
            return str(dt_str)
        # РЎС‡РёС‚Р°РµРј, С‡С‚Рѕ С…СЂР°РЅРёРјРѕРµ РІСЂРµРјСЏ вЂ” UTC (РЅР°РёРІРЅРѕРµ -> РїСЂРѕСЃС‚Р°РІРёРј UTC)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        else:
            dt = dt.astimezone(_dt.timezone.utc)
        # РџРµСЂРµРІРѕРґ РІ РњРЎРљ
        try:
            from zoneinfo import ZoneInfo  # Python 3.9+
            msk = dt.astimezone(ZoneInfo("Europe/Moscow"))
        except Exception:
            # Р¤РѕР»Р±СЌРє: С„РёРєСЃРёСЂРѕРІР°РЅРЅС‹Р№ UTC+3 (РњРѕСЃРєРІР° Р±РµР· РїРµСЂРµС…РѕРґР°)
            msk = dt.astimezone(_dt.timezone(_dt.timedelta(hours=3)))
        day = msk.day
        month_name = months[msk.month - 1]
        time_part = msk.strftime("%H:%M")
        return f"{day} {month_name} {time_part} (РјСЃРє)"
    buttons = []
    for c in list_to_show:
        # c: (id, start, deadline, end, image_filename, status, [image_file_id])
        cid = c[0]
        deadline = c[2]
        end = c[3]
        status = c[5] if len(c) > 5 else ''
        if status == 'Р·Р°РІРµСЂС€РµРЅ':
            line = f"рџ”є в„–{cid} [Р·Р°РІРµСЂС€РµРЅ] РїРѕСЃРјРѕС‚СЂРµС‚СЊ СЂРµР·СѓР»СЊС‚Р°С‚С‹"
        elif status == 'РІ РёРіСЂРµ':
            line = f"рџ”№ в„–{cid} [РЅР°С‡Р°Р»СЃСЏ] РїРѕРґРІРµРґРµРЅРёРµ РёС‚РѕРіРѕРІ: {iso_to_msk_text(end)}"
        elif status == 'Р°РєС‚РёРІРµРЅ':
            line = f"рџ”ё в„–{cid} [СЃР±РѕСЂ СЃРѕСЃС‚Р°РІРѕРІ] РґРµРґР»Р°Р№РЅ СЃР±РѕСЂРєРё СЃРѕСЃС‚Р°РІР°: {iso_to_msk_text(deadline)}"
        else:
            line = f"в„–{cid} [{status}]"
        lines.append(line)
        buttons.append([InlineKeyboardButton(f"РћС‚РєСЂС‹С‚СЊ #{cid}", callback_data=f"challenge_open_{cid}")])

    await update.message.reply_text("\n\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')


async def challenge_open_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    try:
        cid = int(data.replace("challenge_open_", ""))
    except Exception:
        await query.edit_message_text("РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РІС‹Р±РѕСЂ С‡РµР»Р»РµРЅРґР¶Р°.")
        return

    # РќР°Р№РґРµРј С‡РµР»Р»РµРЅРґР¶ РїРѕ id
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
        await query.edit_message_text("Р§РµР»Р»РµРЅРґР¶ РЅРµ РЅР°Р№РґРµРЅ.")
        return

    # РџРѕРїСЂРѕР±СѓРµРј РѕС‚РїСЂР°РІРёС‚СЊ РєР°СЂС‚РёРЅРєСѓ С‡РµР»Р»РµРЅРґР¶Р° РєР°Рє С„РѕС‚Рѕ
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

    # Р•СЃР»Рё Сѓ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ СѓР¶Рµ РµСЃС‚СЊ Р·Р°РїРёСЃСЊ РЅР° СЌС‚РѕС‚ С‡РµР»Р»РµРЅРґР¶ вЂ” РїРѕРєР°Р·Р°С‚СЊ С‚РµРєСѓС‰РёР№ СЃРѕСЃС‚Р°РІ Рё РєРЅРѕРїРєРё РћС‚РјРµРЅРёС‚СЊ/РџРµСЂРµСЃРѕР±СЂР°С‚СЊ
    uid = update.effective_user.id if update.effective_user else None
    entry = None
    try:
        if uid:
            entry = db.challenge_get_entry(ch[0], uid)
    except Exception:
        entry = None

    status = ch[5] if len(ch) > 5 else ''
    if entry:
        # Р•СЃР»Рё Р·Р°РїРёСЃСЊ РѕС‚РјРµРЅРµРЅР°/РІРѕР·РІСЂР°С‰РµРЅР° вЂ” СЃС‡РёС‚Р°РµРј, С‡С‚Рѕ Р·Р°РїРёСЃРё РЅРµС‚
        try:
            st = (entry[5] or '').lower()
            if st in ('canceled', 'refunded'):
                entry = None
        except Exception:
            pass

    if entry:
        # entry: (id, stake, forward_id, defender_id, goalie_id, status)
        # РЎРѕС…СЂР°РЅРёРј id С‡РµР»Р»РµРЅРґР¶Р° РІ РєРѕРЅС‚РµРєСЃС‚ РґР»СЏ РїРѕСЃР»РµРґСѓСЋС‰РёС… РґРµР№СЃС‚РІРёР№ (РћС‚РјРµРЅРёС‚СЊ/РџРµСЂРµСЃРѕР±СЂР°С‚СЊ)
        context.user_data['challenge_id'] = ch[0]
        fwd_id = entry[2]
        d_id = entry[3]
        g_id = entry[4]
        try:
            fwd = db.get_player_by_id(fwd_id) if fwd_id else None
            d = db.get_player_by_id(d_id) if d_id else None
            g = db.get_player_by_id(g_id) if g_id else None
            def fmt(p):
                return f"{p[1]} ({p[3]})" if p else "вЂ”"
            picked_line = f"{fmt(fwd)} - {fmt(d)} - {fmt(g)}"
        except Exception:
            picked_line = "вЂ”"
        stake = entry[1]
        # Р›РѕРєР°Р»СЊРЅС‹Р№ С„РѕСЂРјР°С‚С‚РµСЂ РњРЎРљ
        def iso_to_msk_text(dt_str: str) -> str:
            import datetime as _dt
            months = [
                "СЏРЅРІР°СЂСЏ", "С„РµРІСЂР°Р»СЏ", "РјР°СЂС‚Р°", "Р°РїСЂРµР»СЏ", "РјР°СЏ", "РёСЋРЅСЏ",
                "РёСЋР»СЏ", "Р°РІРіСѓСЃС‚Р°", "СЃРµРЅС‚СЏР±СЂСЏ", "РѕРєС‚СЏР±СЂСЏ", "РЅРѕСЏР±СЂСЏ", "РґРµРєР°Р±СЂСЏ"
            ]
            if not dt_str:
                return "вЂ”"
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
            return f"{day} {month_name} РІ {time_part} (РјСЃРє)"

        deadline_text = iso_to_msk_text(ch[2])
        end_text = iso_to_msk_text(ch[3])
        status_display = 'СЂРµРіРёСЃС‚СЂР°С†РёСЏ СЃРѕСЃС‚Р°РІРѕРІ' if (status == 'Р°РєС‚РёРІРµРЅ') else status
        txt = (
            f"Р§РµР»Р»РµРЅРґР¶ в„–{ch[0]}\n"
            f"РЎС‚Р°С‚СѓСЃ: {status_display}\n\n"
            f"Р”РµРґР»Р°Р№РЅ: {deadline_text}\n"
            f"РџРѕРґРІРµРґРµРЅРёРµ РёС‚РѕРіРѕРІ: {end_text}\n\n"
            f"Р’Р°С€ СЃРѕСЃС‚Р°РІ: {picked_line}\n"
            f"РЈСЂРѕРІРµРЅСЊ РІС‹Р·РѕРІР°: {stake} HC"
        )
        buttons = [
            [InlineKeyboardButton('РћС‚РјРµРЅРёС‚СЊ', callback_data='challenge_cancel')],
            [InlineKeyboardButton('РџРµСЂРµСЃРѕР±СЂР°С‚СЊ', callback_data='challenge_reshuffle')],
        ]
        await context.bot.send_message(chat_id=update.effective_chat.id, text=txt, reply_markup=InlineKeyboardMarkup(buttons))
        return

    # РњРµРЅСЋ РґРµР№СЃС‚РІРёР№ РїРѕ С‡РµР»Р»РµРЅРґР¶Сѓ (РµСЃР»Рё Р·Р°РїРёСЃРё РЅРµС‚)
    # РЎРѕС…СЂР°РЅРёРј id С‡РµР»Р»РµРЅРґР¶Р° РІ РєРѕРЅС‚РµРєСЃС‚ РґР»СЏ РІРѕР·РјРѕР¶РЅРѕРіРѕ РЅР°С‡Р°Р»Р° СЃР±РѕСЂРєРё
    context.user_data['challenge_id'] = ch[0]
    text = (
        f"Р§РµР»Р»РµРЅРґР¶ #{ch[0]}\n"
        f"РЎС‚Р°С‚СѓСЃ: {status}\n"
        f"РЎС‚Р°СЂС‚: {ch[1]}\nР”РµРґР»Р°Р№РЅ: {ch[2]}\nРћРєРѕРЅС‡Р°РЅРёРµ: {ch[3]}"
    )
    buttons = [[InlineKeyboardButton("РРЅС„Рѕ", callback_data=f"challenge_info_{ch[0]}")]]
    if status == "Р°РєС‚РёРІРµРЅ":
        buttons.append([InlineKeyboardButton("РЎРѕР±СЂР°С‚СЊ СЃРѕСЃС‚Р°РІ", callback_data=f"challenge_build_{ch[0]}")])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=InlineKeyboardMarkup(buttons))


async def challenge_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        cid = int(query.data.replace("challenge_info_", ""))
    except Exception:
        await query.edit_message_text("РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ Р·Р°РїСЂРѕСЃ.")
        return
    # РќР°Р№РґРµРј С‡РµР»Р»РµРЅРґР¶
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
        await query.edit_message_text("Р§РµР»Р»РµРЅРґР¶ РЅРµ РЅР°Р№РґРµРЅ.")
        return
    status = ch[5] if len(ch) > 5 else ''
    txt = (
        f"РРЅС„РѕСЂРјР°С†РёСЏ РїРѕ С‡РµР»Р»РµРЅРґР¶Сѓ #{ch[0]}\n"
        f"РЎС‚Р°С‚СѓСЃ: {status}\n"
        f"РЎС‚Р°СЂС‚: {ch[1]}\nР”РµРґР»Р°Р№РЅ: {ch[2]}\nРћРєРѕРЅС‡Р°РЅРёРµ: {ch[3]}\n\n"
        f"Р•СЃР»Рё СЃС‚Р°С‚СѓСЃ 'Р°РєС‚РёРІРµРЅ' вЂ” РјРѕР¶РµС‚Рµ СЃРѕР±СЂР°С‚СЊ СЃРѕСЃС‚Р°РІ."
    )
    await query.edit_message_text(txt)

def _parse_shop_items(text: str):
    items = []
    if not text:
        return items
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        if not (line.startswith('рџ”ё') or line.startswith('вЂў') or line.startswith('-')):
            continue
        # РЈР±РёСЂР°РµРј РјР°СЂРєРµСЂ
        raw = line.lstrip('рџ”ё').lstrip('вЂў').lstrip('-').strip()
        # Р Р°Р·РґРµР»РёС‚РµР»СЊ вЂ” РјРѕР¶РµС‚ Р±С‹С‚СЊ РґР»РёРЅРЅРѕРµ С‚РёСЂРµ РёР»Рё РґРµС„РёСЃ
        sep = 'вЂ”' if 'вЂ”' in raw else (' - ' if ' - ' in raw else '-')
        if sep not in raw:
            # РџСЂРѕРїСѓСЃРєР°РµРј РЅРµРєРѕСЂСЂРµРєС‚РЅС‹Рµ СЃС‚СЂРѕРєРё
            continue
        name, price = raw.split(sep, 1)
        name = name.strip()
        price = price.strip()
        if name:
            items.append((name, price))
    return items

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """РџРѕРєР°Р·Р°С‚СЊ СЃРѕРґРµСЂР¶РёРјРѕРµ РјР°РіР°Р·РёРЅР°: С‚РµРєСЃС‚ + РєР°СЂС‚РёРЅРєР° + РёРЅР»Р°Р№РЅ-РєРЅРѕРїРєРё С‚РѕРІР°СЂРѕРІ."""
    try:
        text, image_filename, image_file_id = db.get_shop_content()
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ РґР°РЅРЅС‹С… РјР°РіР°Р·РёРЅР°: {e}")
        return
    if not text and not image_filename and not image_file_id:
        await update.message.reply_text("РњР°РіР°Р·РёРЅ РїРѕРєР° РїСѓСЃС‚. Р—Р°РіР»СЏРЅРёС‚Рµ РїРѕР·Р¶Рµ.")
        return
    # РџРѕСЃС‚СЂРѕРёРј РёРЅР»Р°Р№РЅ-РєРЅРѕРїРєРё РёР· С‚РµРєСЃС‚Р°
    items = _parse_shop_items(text or '')
    buttons = []
    for idx, (name, price) in enumerate(items, start=1):
        label = f"{name} вЂ” {price}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"shop_item_{idx}")])
    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    caption = text if text else None
    # РџРѕРїС‹С‚Р°РµРјСЃСЏ РѕС‚РїСЂР°РІРёС‚СЊ С„РѕС‚Рѕ РїРѕ file_id
    if image_file_id:
        try:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_file_id, caption=caption, reply_markup=reply_markup)
            return
        except Exception:
            logger.warning("send_photo by file_id failed in /shop", exc_info=True)
    # РџРѕРїСЂРѕР±СѓРµРј РѕС‚РїСЂР°РІРёС‚СЊ Р»РѕРєР°Р»СЊРЅС‹Р№ С„Р°Р№Р»
    if image_filename:
        fpath = os.path.join(IMAGES_DIR, image_filename)
        if os.path.exists(fpath):
            try:
                with open(fpath, 'rb') as fp:
                    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=InputFile(fp, filename=image_filename), caption=caption, reply_markup=reply_markup)
                    return
            except Exception:
                logger.error("send_photo from local file failed in /shop", exc_info=True)
    # Р•СЃР»Рё С„РѕС‚Рѕ РЅРµ РїРѕР»СѓС‡РёР»РѕСЃСЊ вЂ” РѕС‚РїСЂР°РІРёРј РїСЂРѕСЃС‚Рѕ С‚РµРєСЃС‚
    if caption:
        await update.message.reply_text(caption, reply_markup=reply_markup)
    else:
        await update.message.reply_text("РњР°РіР°Р·РёРЅ РЅРµРґРѕСЃС‚СѓРїРµРЅ.")

async def shop_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # shop_item_<n>
    try:
        await query.edit_message_reply_markup(reply_markup=query.message.reply_markup)
    except BadRequest as e:
        # РРіРЅРѕСЂРёСЂСѓРµРј 'Message is not modified'
        if 'Message is not modified' not in str(e):
            raise
    try:
        idx = int(data.replace('shop_item_', ''))
    except Exception:
        idx = None
    # РџРѕР»СѓС‡РёРј СЃРїРёСЃРѕРє С‚РѕРІР°СЂРѕРІ Р·Р°РЅРѕРІРѕ РёР· Р‘Р”
    try:
        text, _, _ = db.get_shop_content()
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"РћС€РёР±РєР° С‡С‚РµРЅРёСЏ РјР°РіР°Р·РёРЅР°: {e}")
        return
    items = _parse_shop_items(text or '')
    if not idx or idx < 1 or idx > len(items):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РІС‹Р±РѕСЂ С‚РѕРІР°СЂР°.")
        return
    name, price_str = items[idx - 1]
    # РР·РІР»РµС‡С‘Рј С‡РёСЃР»Рѕ РёР· СЃС‚СЂРѕРєРё С†РµРЅС‹ (РЅР°РїСЂРёРјРµСЂ, '35 000 HC' -> 35000)
    digits = ''.join(ch for ch in price_str if ch.isdigit())
    try:
        price = int(digits) if digits else 0
    except Exception:
        price = 0
    # Р‘Р°Р»Р°РЅСЃ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
    user = update.effective_user
    balance = 0
    try:
        row = db.get_user_by_id(user.id)
        if row and len(row) > 3 and isinstance(row[3], (int, float)):
            balance = int(row[3])
        elif row and len(row) > 3:
            # РќР° СЃР»СѓС‡Р°Р№, РµСЃР»Рё С…СЂР°РЅРёС‚СЃСЏ СЃС‚СЂРѕРєРѕР№
            try:
                balance = int(str(row[3]))
            except Exception:
                balance = 0
    except Exception:
        balance = 0
    if price <= 0:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"РўРѕРІР°СЂ: {name}\nР¦РµРЅР°: {price_str}\n\nРќРµ СѓРґР°Р»РѕСЃСЊ СЂР°СЃРїРѕР·РЅР°С‚СЊ С†РµРЅСѓ. РЎРІСЏР¶РёС‚РµСЃСЊ СЃ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂРѕРј.")
        return
    if balance < price:
        need = price - balance
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"РўРѕРІР°СЂ: {name}\nР¦РµРЅР°: {price_str}\n\n"
                f"РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ СЃСЂРµРґСЃС‚РІ: РЅРµ С…РІР°С‚Р°РµС‚ {need} HC.\n"
                f"Р’С‹ РјРѕР¶РµС‚Рµ РїРѕРґРєР»СЋС‡РёС‚СЊ РїРѕРґРїРёСЃРєСѓ /subscribe Р·Р° 299 СЂСѓР±/РјРµСЃСЏС†, С‡С‚РѕР±С‹ Р±С‹СЃС‚СЂРµРµ РЅР°РєР°РїР»РёРІР°С‚СЊ HC."
            )
        )
        return
    # Р‘Р°Р»Р°РЅСЃР° РґРѕСЃС‚Р°С‚РѕС‡РЅРѕ вЂ” РїСЂРѕР±СѓРµРј СЃРїРёСЃР°С‚СЊ HC
    try:
        db.update_hc_balance(user.id, -price)
        new_balance = max(0, balance - price)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРїРёСЃР°С‚СЊ HC: {e}")
        return
    # РЎРѕРѕР±С‰РµРЅРёРµ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"РўРѕРІР°СЂ: {name}\nР¦РµРЅР°: {price_str}\n\n"
            f"РџРѕРєСѓРїРєР° РїСЂРёРЅСЏС‚Р°! РЎ РІР°С€РµРіРѕ Р±Р°Р»Р°РЅСЃР° СЃРїРёСЃР°РЅРѕ {price} HC.\n"
            f"РўРµРєСѓС‰РёР№ Р±Р°Р»Р°РЅСЃ: {new_balance} HC."
        )
    )
    # РЈРІРµРґРѕРјР»РµРЅРёРµ Р°РґРјРёРЅР°(РѕРІ)
    try:
        admin_text = (
            "рџ›’ Р—Р°РїСЂРѕСЃ РЅР° РїРѕРєСѓРїРєСѓ\n\n"
            f"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ: {user.full_name} (@{user.username or '-'}, id={user.id})\n"
            f"РўРѕРІР°СЂ: {name}\n"
            f"Р¦РµРЅР°: {price_str}\n"
            f"РЎРїРёСЃР°РЅРѕ: {price} HC\n"
            f"РќРѕРІС‹Р№ Р±Р°Р»Р°РЅСЃ: {new_balance} HC\n"
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
        await query.edit_message_text("РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ Р·Р°РїСЂРѕСЃ.")
        return
    # РџСЂРѕРІРµСЂРёРј, С‡С‚Рѕ РІС‹Р±СЂР°РЅРЅС‹Р№ С‡РµР»Р»РµРЅРґР¶ Р°РєС‚РёРІРµРЅ
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
        await query.edit_message_text("Р§РµР»Р»РµРЅРґР¶ РЅРµ РЅР°Р№РґРµРЅ.")
        return
    status = ch[5] if len(ch) > 5 else ''
    if status != "Р°РєС‚РёРІРµРЅ":
        await query.edit_message_text("РЎР±РѕСЂ СЃРѕСЃС‚Р°РІР° РЅРµРґРѕСЃС‚СѓРїРµРЅ: С‡РµР»Р»РµРЅРґР¶ РЅРµ Р°РєС‚РёРІРµРЅ.")
        return

    # РЎРѕС…СЂР°РЅРёРј id С‡РµР»Р»РµРЅРґР¶Р° РІ user_data РґР»СЏ РґР°Р»СЊРЅРµР№С€РёС… С€Р°РіРѕРІ
    context.user_data['challenge_id'] = cid
    # РџРµСЂРµРёСЃРїРѕР»СЊР·СѓРµРј С‚РµРєСѓС‰СѓСЋ РјРµС…Р°РЅРёРєСѓ: РІС‹Р±РѕСЂ СѓСЂРѕРІРЅСЏ РІС‹Р·РѕРІР°
    text = (
        "Р’С‹Р±РµСЂРёС‚Рµ СѓСЂРѕРІРµРЅСЊ РІС‹Р·РѕРІР° РґР»СЏ С‡РµР»Р»РµРЅРґР¶Р°:\n\n"
        "вљЎпёЏ 50 HC\nвљЎпёЏ 100 HC\nвљЎпёЏ 500 HC"
    )
    keyboard = [
        [
            InlineKeyboardButton('вљЎпёЏ 50 HC', callback_data='challenge_level_50'),
            InlineKeyboardButton('вљЎпёЏ 100 HC', callback_data='challenge_level_100'),
            InlineKeyboardButton('вљЎпёЏ 500 HC', callback_data='challenge_level_500'),
        ]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def challenge_level_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    level = data.replace('challenge_level_', '')
    try:
        level_int = int(level)
    except Exception:
        await query.edit_message_text("РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ СѓСЂРѕРІРµРЅСЊ РІС‹Р·РѕРІР°.")
        return
    user = update.effective_user
    user_row = db.get_user_by_id(user.id)
    balance = user_row[3] if user_row else 0
    if balance < level_int:
        text = (
            f"РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ HC РґР»СЏ СѓСЂРѕРІРЅСЏ {level_int} HC.\n"
            f"РўРµРєСѓС‰РёР№ Р±Р°Р»Р°РЅСЃ: {balance} HC.\n\n"
            "Р’С‹Р±РµСЂРёС‚Рµ РґРѕСЃС‚СѓРїРЅС‹Р№ СѓСЂРѕРІРµРЅСЊ РІС‹Р·РѕРІР°:"
        )
        keyboard = [
            [
                InlineKeyboardButton('вљЎпёЏ 50 HC', callback_data='challenge_level_50'),
                InlineKeyboardButton('вљЎпёЏ 100 HC', callback_data='challenge_level_100'),
                InlineKeyboardButton('вљЎпёЏ 500 HC', callback_data='challenge_level_500'),
            ]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    # Р‘Р°Р»Р°РЅСЃ РґРѕСЃС‚Р°С‚РѕС‡РµРЅ вЂ” СЃРїРёСЃС‹РІР°РµРј Рё СЃРѕР·РґР°С‘Рј Р·Р°СЏРІРєСѓ
    cid = context.user_data.get('challenge_id')
    if not cid:
        await query.edit_message_text("РћС€РёР±РєР°: РЅРµС‚ РІС‹Р±СЂР°РЅРЅРѕРіРѕ С‡РµР»Р»РµРЅРґР¶Р°. РћС‚РєСЂРѕР№С‚Рµ Р·Р°РЅРѕРІРѕ С‡РµСЂРµР· /challenge.")
        return
    ok = db.create_challenge_entry_and_charge(cid, user.id, level_int)
    if not ok:
        await query.edit_message_text("РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕР·РґР°С‚СЊ Р·Р°СЏРІРєСѓ: РІРѕР·РјРѕР¶РЅРѕ, Р·Р°РїРёСЃСЊ СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚ РёР»Рё РЅРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ HC.")
        return
    context.user_data['challenge_level'] = level_int
    context.user_data['challenge_remaining_positions'] = ['РЅР°РїР°РґР°СЋС‰РёР№', 'Р·Р°С‰РёС‚РЅРёРє', 'РІСЂР°С‚Р°СЂСЊ']
    # РџРѕРєР°Р·Р°С‚СЊ РІС‹Р±РѕСЂ РїРѕР·РёС†РёРё
    buttons = [
        [InlineKeyboardButton('РЅР°РїР°РґР°СЋС‰РёР№', callback_data='challenge_pick_pos_РЅР°РїР°РґР°СЋС‰РёР№')],
        [InlineKeyboardButton('Р·Р°С‰РёС‚РЅРёРє', callback_data='challenge_pick_pos_Р·Р°С‰РёС‚РЅРёРє')],
        [InlineKeyboardButton('РІСЂР°С‚Р°СЂСЊ', callback_data='challenge_pick_pos_РІСЂР°С‚Р°СЂСЊ')],
    ]
    await query.edit_message_text(
        f"РЈСЂРѕРІРµРЅСЊ РІС‹Р·РѕРІР° РІС‹Р±СЂР°РЅ: {level_int} HC. РЎ РІР°С€РµРіРѕ Р±Р°Р»Р°РЅСЃР° СЃРїРёСЃР°РЅРѕ {level_int} HC.\nР’С‹Р±РµСЂРёС‚Рµ РїРѕР·РёС†РёСЋ:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def challenge_pick_pos_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pos = query.data.replace('challenge_pick_pos_', '')
    remaining = context.user_data.get('challenge_remaining_positions', ['РЅР°РїР°РґР°СЋС‰РёР№', 'Р·Р°С‰РёС‚РЅРёРє', 'РІСЂР°С‚Р°СЂСЊ'])
    if pos not in remaining:
        await query.edit_message_text("Р­С‚Р° РїРѕР·РёС†РёСЏ СѓР¶Рµ РІС‹Р±СЂР°РЅР°. Р’С‹Р±РµСЂРёС‚Рµ РґСЂСѓРіСѓСЋ.")
        return
    context.user_data['challenge_current_pos'] = pos
    context.user_data['challenge_expect_team'] = True
    await query.edit_message_text(f"Р’С‹ РІС‹Р±СЂР°Р»Рё РїРѕР·РёС†РёСЋ: {pos}. РўРµРїРµСЂСЊ РІРІРµРґРёС‚Рµ РЅР°Р·РІР°РЅРёРµ РєРѕРјР°РЅРґС‹ СЃРѕРѕР±С‰РµРЅРёРµРј.")


async def challenge_team_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # РћР±СЂР°Р±Р°С‚С‹РІР°РµРј С‚РµРєСЃС‚ РЅР°Р·РІР°РЅРёСЏ РєРѕРјР°РЅРґС‹ С‚РѕР»СЊРєРѕ РµСЃР»Рё РѕР¶РёРґР°РµРј
    if not context.user_data.get('challenge_expect_team'):
        return
    team_text = (update.message.text or '').strip()
    context.user_data['challenge_expect_team'] = False
    context.user_data['challenge_team_query'] = team_text
    pos = context.user_data.get('challenge_current_pos')
    # РЎРїРёСЃРѕРє РёРіСЂРѕРєРѕРІ РїРѕ РїРѕР·РёС†РёРё Рё РЅР°Р·РІР°РЅРёСЋ РєРѕРјР°РЅРґС‹
    from db import get_all_players
    all_players = get_all_players()
    team_lower = team_text.lower()
    filtered = [p for p in all_players if (p[2] or '').lower() == pos and team_lower in str(p[3] or '').lower()]
    if not filtered:
        # Вывести список команд из БД, чтобы помочь пользователю
        try:
            clubs = sorted({str(p[3]).strip() for p in all_players if (p and len(p) > 3 and p[3])})
            if clubs:
                clubs_text = "\n".join(clubs)
                await update.message.reply_text("Мы не нашли вашу команду по вашему запросу. Может вы имели ввиду одну из этих:\n\n" + clubs_text)
            else:
                await update.message.reply_text("Мы не нашли вашу команду по вашему запросу.")
        except Exception:
            await update.message.reply_text("Мы не нашли вашу команду по вашему запросу.")
        await update.message.reply_text("РРіСЂРѕРєРё РЅРµ РЅР°Р№РґРµРЅС‹ РїРѕ СѓРєР°Р·Р°РЅРЅС‹Рј С„РёР»СЊС‚СЂР°Рј. РџРѕРІС‚РѕСЂРёС‚Рµ РІС‹Р±РѕСЂ РїРѕР·РёС†РёРё.")
        # Р’РµСЂРЅС‘Рј РјРµРЅСЋ РїРѕР·РёС†РёР№ (РѕСЃС‚Р°РІС€РёРµСЃСЏ)
        remaining = context.user_data.get('challenge_remaining_positions', ['РЅР°РїР°РґР°СЋС‰РёР№', 'Р·Р°С‰РёС‚РЅРёРє', 'РІСЂР°С‚Р°СЂСЊ'])
        btns = [[InlineKeyboardButton(x, callback_data=f"challenge_pick_pos_{x}")] for x in remaining]
        await update.message.reply_text("Р’С‹Р±РµСЂРёС‚Рµ РїРѕР·РёС†РёСЋ:", reply_markup=InlineKeyboardMarkup(btns))
        return
    # РџРѕСЃС‚СЂРѕРёС‚СЊ РєР»Р°РІРёР°С‚СѓСЂСѓ РёРіСЂРѕРєРѕРІ
    kb = []
    for p in filtered:
        kb.append([InlineKeyboardButton(f"{p[1]} ({p[3]})", callback_data=f"challenge_pick_player_{p[0]}")])
    await update.message.reply_text("Р’С‹Р±РµСЂРёС‚Рµ РёРіСЂРѕРєР°:", reply_markup=InlineKeyboardMarkup(kb))


async def challenge_pick_player_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        pid = int(query.data.replace('challenge_pick_player_', ''))
    except Exception:
        await query.edit_message_text("РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РІС‹Р±РѕСЂ РёРіСЂРѕРєР°.")
        return
    cid = context.user_data.get('challenge_id')
    pos = context.user_data.get('challenge_current_pos')
    if not cid or not pos:
        await query.edit_message_text("РљРѕРЅС‚РµРєСЃС‚ РІС‹Р±РѕСЂР° СѓС‚РµСЂСЏРЅ. РќР°С‡РЅРёС‚Рµ Р·Р°РЅРѕРІРѕ: /challenge")
        return
    # РЎРѕС…СЂР°РЅСЏРµРј РїРёРє
    try:
        db.challenge_set_pick(cid, update.effective_user.id, pos, pid)
        p = db.get_player_by_id(pid)
        picked_name = f"{p[1]} ({p[3]})" if p else f"id={pid}"
        await query.edit_message_text(f"Р’С‹ РІС‹Р±СЂР°Р»Рё: {picked_name}")
    except Exception as e:
        await query.edit_message_text(f"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕС…СЂР°РЅРёС‚СЊ РІС‹Р±РѕСЂ: {e}")
        return
    # РћР±РЅРѕРІР»СЏРµРј СЃРїРёСЃРѕРє РѕСЃС‚Р°РІС€РёС…СЃСЏ РїРѕР·РёС†РёР№
    remaining = context.user_data.get('challenge_remaining_positions', ['РЅР°РїР°РґР°СЋС‰РёР№', 'Р·Р°С‰РёС‚РЅРёРє', 'РІСЂР°С‚Р°СЂСЊ'])
    try:
        remaining.remove(pos)
    except ValueError:
        pass
    context.user_data['challenge_remaining_positions'] = remaining
    if remaining:
        # РџРѕРєР°Р·Р°С‚СЊ РѕСЃС‚Р°РІС€РёРµСЃСЏ РїРѕР·РёС†РёРё
        btns = [[InlineKeyboardButton(x, callback_data=f"challenge_pick_pos_{x}")] for x in remaining]
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Р’С‹Р±РµСЂРёС‚Рµ СЃР»РµРґСѓСЋС‰СѓСЋ РїРѕР·РёС†РёСЋ:", reply_markup=InlineKeyboardMarkup(btns))
        return
    # Р’СЃРµ С‚СЂРё РїРѕР·РёС†РёРё РІС‹Р±СЂР°РЅС‹ вЂ” С„РёРЅР°Р»РёР·Р°С†РёСЏ
    try:
        db.challenge_finalize(cid, update.effective_user.id)
    except Exception:
        pass
    # РЎРІРѕРґРєР°
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
    # РќР°Р№РґС‘Рј РґРµРґР»Р°Р№РЅ Рё СЃС‚Р°РІРєСѓ
    ch = None
    try:
        ch = db.get_challenge_by_id(cid)
    except Exception:
        ch = None
    # Р¤РѕСЂРјР°С‚РёСЂСѓРµРј РґР°С‚Сѓ РїРѕРґРІРµРґРµРЅРёСЏ РёС‚РѕРіРѕРІ (РёСЃРїРѕР»СЊР·СѓРµРј РєРѕРЅРµС† С‡РµР»Р»РµРЅРґР¶Р° ch[3])
    def iso_to_msk_text(dt_str: str) -> str:
        import datetime as _dt
        months = [
            "СЏРЅРІР°СЂСЏ", "С„РµРІСЂР°Р»СЏ", "РјР°СЂС‚Р°", "Р°РїСЂРµР»СЏ", "РјР°СЏ", "РёСЋРЅСЏ",
            "РёСЋР»СЏ", "Р°РІРіСѓСЃС‚Р°", "СЃРµРЅС‚СЏР±СЂСЏ", "РѕРєС‚СЏР±СЂСЏ", "РЅРѕСЏР±СЂСЏ", "РґРµРєР°Р±СЂСЏ"
        ]
        if not dt_str:
            return "вЂ”"
        try:
            dt = _dt.datetime.fromisoformat(str(dt_str))
        except Exception:
            return str(dt_str)
        # СЃС‡РёС‚Р°РµРј, С‡С‚Рѕ С…СЂР°РЅРёС‚СЃСЏ UTC
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
        return f"{day} {month_name} РІ {time_part} (РјСЃРє)"

    end_iso = ch[3] if ch else ""
    end_text = iso_to_msk_text(end_iso)
    stake = context.user_data.get('challenge_level')
    txt = (
        f"{picked_line}\n"
        f"РџРѕРґРІРµРґРµРЅРёРµ РёС‚РѕРіРѕРІ: {end_text}\n"
        f"Р’Р°С€ СѓСЂРѕРІРµРЅСЊ РІС‹Р·РѕРІР°: {stake} HC"
    )
    buttons = [
        [InlineKeyboardButton('РћС‚РјРµРЅРёС‚СЊ', callback_data='challenge_cancel')],
        [InlineKeyboardButton('РџРµСЂРµСЃРѕР±СЂР°С‚СЊ', callback_data='challenge_reshuffle')],
    ]
    await context.bot.send_message(chat_id=update.effective_chat.id, text=txt, reply_markup=InlineKeyboardMarkup(buttons))


async def challenge_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = context.user_data.get('challenge_id')
    if not cid:
        await query.edit_message_text("РћС‚РјРµРЅР° РЅРµРґРѕСЃС‚СѓРїРЅР°: РЅРµС‚ Р°РєС‚РёРІРЅРѕР№ Р·Р°РїРёСЃРё.")
        return
    refunded = db.challenge_cancel_and_refund(cid, update.effective_user.id)
    if refunded:
        # РќР° РІСЃСЏРєРёР№ СЃР»СѓС‡Р°Р№ РѕС‡РёСЃС‚РёРј РїРёРєРё
        try:
            db.challenge_reset_picks(cid, update.effective_user.id)
        except Exception:
            pass
        await query.edit_message_text("Р—Р°СЏРІРєР° РѕС‚РјРµРЅРµРЅР°, СЃРѕСЃС‚Р°РІ РѕС‡РёС‰РµРЅ, HC РІРѕР·РІСЂР°С‰РµРЅС‹ РЅР° Р±Р°Р»Р°РЅСЃ.")
    else:
        await query.edit_message_text("Р—Р°СЏРІРєР° СѓР¶Рµ Р·Р°РІРµСЂС€РµРЅР° РёР»Рё РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚. Р’РѕР·РІСЂР°С‚ РЅРµРІРѕР·РјРѕР¶РµРЅ.")


async def challenge_reshuffle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = context.user_data.get('challenge_id')
    if not cid:
        await query.edit_message_text("РџРµСЂРµСЃР±РѕСЂРєР° РЅРµРґРѕСЃС‚СѓРїРЅР°: РЅРµС‚ Р°РєС‚РёРІРЅРѕР№ Р·Р°РїРёСЃРё.")
        return
    try:
        db.challenge_reset_picks(cid, update.effective_user.id)
        context.user_data['challenge_remaining_positions'] = ['РЅР°РїР°РґР°СЋС‰РёР№', 'Р·Р°С‰РёС‚РЅРёРє', 'РІСЂР°С‚Р°СЂСЊ']
        btns = [[InlineKeyboardButton(x, callback_data=f"challenge_pick_pos_{x}")] for x in context.user_data['challenge_remaining_positions']]
        await query.edit_message_text("РЎР±СЂРѕСЃ РІС‹РїРѕР»РЅРµРЅ. Р’С‹Р±РµСЂРёС‚Рµ РїРѕР·РёС†РёСЋ:", reply_markup=InlineKeyboardMarkup(btns))
    except Exception as e:
        await query.edit_message_text(f"РќРµ СѓРґР°Р»РѕСЃСЊ РїРµСЂРµСЃРѕР±СЂР°С‚СЊ: {e}")


TOUR_START, TOUR_FORWARD_1, TOUR_FORWARD_2, TOUR_FORWARD_3, TOUR_DEFENDER_1, TOUR_DEFENDER_2, TOUR_GOALIE, TOUR_CAPTAIN, PREMIUM_TEAM, PREMIUM_POSITION = range(10)

async def tour_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # РџРѕР»СѓС‡Р°РµРј РѕР±СЉРµРєС‚ СЃРѕРѕР±С‰РµРЅРёСЏ РґР»СЏ РѕС‚РІРµС‚Р° (СѓРЅРёРІРµСЂСЃР°Р»СЊРЅРѕ РґР»СЏ Update Рё CallbackQuery)
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message

    # РџСЂРѕРІРµСЂСЏРµРј Р°РєС‚РёРІРЅСѓСЋ РїРѕРґРїРёСЃРєСѓ
    try:
        from db import is_subscription_active
        user = update.effective_user
        if not is_subscription_active(user.id):
            await message.reply_text(
                "РџРѕРґРїРёСЃРєР° РЅРµ Р°РєС‚РёРІРЅР°. РћС„РѕСЂРјРёС‚Рµ РёР»Рё РїСЂРѕРґР»РёС‚Рµ РїРѕРґРїРёСЃРєСѓ РєРѕРјР°РЅРґРѕР№ /subscribe, Р·Р°С‚РµРј РїРѕРІС‚РѕСЂРёС‚Рµ РїРѕРїС‹С‚РєСѓ."
            )
            return ConversationHandler.END
    except Exception:
        # РџСЂРё РѕС€РёР±РєРµ РїСЂРѕРІРµСЂРєРё РЅРµ Р±Р»РѕРєРёСЂСѓРµРј, РЅРѕ РґР°С‘Рј РїРѕРґСЃРєР°Р·РєСѓ
        try:
            await message.reply_text("РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕРІРµСЂРёС‚СЊ РїРѕРґРїРёСЃРєСѓ. Р•СЃР»Рё РґРѕСЃС‚СѓРї РѕРіСЂР°РЅРёС‡РµРЅ, РёСЃРїРѕР»СЊР·СѓР№С‚Рµ /subscribe.")
        except Exception:
            pass

    # --- РћРїСЂРµРґРµР»СЏРµРј Р°РєС‚РёРІРЅС‹Р№ С‚СѓСЂ ---
    from db import get_active_tour
    active_tour = get_active_tour()
    if not active_tour:
        await message.reply_text("РќРµС‚ Р°РєС‚РёРІРЅРѕРіРѕ С‚СѓСЂР° РґР»СЏ СЃР±РѕСЂР° СЃРѕСЃС‚Р°РІР°. РћР±СЂР°С‚РёС‚РµСЃСЊ Рє Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ.")
        return ConversationHandler.END
async def tour_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    # РџРѕР»СѓС‡Р°РµРј РѕР±СЉРµРєС‚ СЃРѕРѕР±С‰РµРЅРёСЏ РґР»СЏ РѕС‚РІРµС‚Р° (СѓРЅРёРІРµСЂСЃР°Р»СЊРЅРѕ РґР»СЏ Update Рё CallbackQuery)
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message

    # --- РћРїСЂРµРґРµР»СЏРµРј Р°РєС‚РёРІРЅС‹Р№ С‚СѓСЂ ---
    from db import get_active_tour, get_user_tour_roster, get_player_by_id
    active_tour = get_active_tour()
    if not active_tour:
        await message.reply_text("РќРµС‚ Р°РєС‚РёРІРЅРѕРіРѕ С‚СѓСЂР° РґР»СЏ СЃР±РѕСЂР° СЃРѕСЃС‚Р°РІР°. РћР±СЂР°С‚РёС‚РµСЃСЊ Рє Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ.")
        return ConversationHandler.END
    context.user_data['active_tour_id'] = active_tour['id']

    user_id = update.effective_user.id
    tour_id = active_tour['id']
    user_roster = get_user_tour_roster(user_id, tour_id)
    if user_roster and user_roster.get('roster'):
        # Р¤РѕСЂРјР°С‚РёСЂСѓРµРј СЃРѕСЃС‚Р°РІ РґР»СЏ РІС‹РІРѕРґР°
        def format_user_roster_md(roster_data):
            from utils import escape_md
            roster = roster_data['roster']
            captain_id = roster_data.get('captain_id')
            spent = roster_data.get('spent', 0)
            # РџРѕР»СѓС‡Р°РµРј РёРЅС„Сѓ РїРѕ РёРіСЂРѕРєР°Рј
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
            cap_str = f"РљР°РїРёС‚Р°РЅ: {escape_md(captain)}" if captain else "РљР°РїРёС‚Р°РЅ: -"
            lines = [
                '*Р’Р°С€ СЃРѕС…СЂР°РЅС‘РЅРЅС‹Р№ СЃРѕСЃС‚Р°РІ:*',
                '',
                g_str,
                d_str,
                f_str,
                '',
                cap_str,
                f'РџРѕС‚СЂР°С‡РµРЅРѕ: *{escape_md(str(spent))}* HC'
            ]
            return '\n'.join(lines)

        text = format_user_roster_md(user_roster)
        keyboard = [[InlineKeyboardButton('РџРµСЂРµСЃРѕР±СЂР°С‚СЊ СЃРѕСЃС‚Р°РІ', callback_data='restart_tour')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(text, reply_markup=reply_markup, parse_mode="MarkdownV2")
        return ConversationHandler.END

    # --- Р•СЃР»Рё СЃРѕСЃС‚Р°РІР° РЅРµС‚, Р·Р°РїСѓСЃРєР°РµРј РѕР±С‹С‡РЅС‹Р№ СЃС†РµРЅР°СЂРёР№ РІС‹Р±РѕСЂР° ---
    # 1. РћС‚РїСЂР°РІРёС‚СЊ РєР°СЂС‚РёРЅРєСѓ С‚СѓСЂР° Рё РІРІРѕРґРЅС‹Р№ С‚РµРєСЃС‚ СЃ Р±СЋРґР¶РµС‚РѕРј
    budget = db.get_budget() or 0
    roster = db.get_tour_roster_with_player_info()
    forwards = [p for p in roster if p[3].lower() == 'РЅР°РїР°РґР°СЋС‰РёР№']
    defenders = [p for p in roster if p[3].lower() == 'Р·Р°С‰РёС‚РЅРёРє']
    goalies = [p for p in roster if p[3].lower() == 'РІСЂР°С‚Р°СЂСЊ']
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
    # РћС‚РїСЂР°РІРёС‚СЊ РєР°СЂС‚РёРЅРєСѓ (РµСЃР»Рё РµСЃС‚СЊ)
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
        logger.error(f'РћС€РёР±РєР° РїСЂРё РѕС‚РїСЂР°РІРєРµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ С‚СѓСЂР°: {e}')
    # Р’РІРѕРґРЅС‹Р№ С‚РµРєСЃС‚
    # Р¤РѕСЂРјРёСЂСѓРµРј СЃС‚СЂРѕРєСѓ РґРµРґР»Р°Р№РЅР°
    deadline = active_tour.get('deadline', '')
    deadline_str = str(deadline).replace('.', '\\.')
    # Р¤РѕСЂРјРёСЂСѓРµРј РєСЂР°СЃРёРІС‹Р№ С‚РµРєСЃС‚ СЃ MarkdownV2
    intro = rf"""*РЎРїРёСЃРѕРє РёРіСЂРѕРєРѕРІ РЅР° С‚РµРєСѓС‰РёР№ С‚СѓСЂ\!* Р’С‹Р±РµСЂРё Рє СЃРµР±Рµ РІ СЃРѕСЃС‚Р°РІ:
рџ”ё3 РЅР°РїР°РґР°СЋС‰РёС…
рџ”ё2 Р·Р°С‰РёС‚РЅРёРєРѕРІ
рџ”ё1 РІСЂР°С‚Р°СЂСЏ

РќР°Р·РЅР°С‡СЊ РѕРґРЅРѕРіРѕ РїРѕР»РµРІРѕРіРѕ РёРіСЂРѕРєР° РёР· СЃРѕСЃС‚Р°РІР° РєР°РїРёС‚Р°РЅРѕРј \(РµРіРѕ РѕС‡РєРё СѓРјРЅРѕР¶РёРј РЅР° С…1\.5\)

*Р’Р°С€ Р±СЋРґР¶РµС‚: {budget}*

РџСЂРёРЅРёРјР°РµРј СЃРѕСЃС‚Р°РІС‹ РґРѕ: {deadline_str}"""

    # Р•СЃР»Рё Сѓ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Р°РєС‚РёРІРЅР°СЏ РїРѕРґРїРёСЃРєР° вЂ” РґРѕР±Р°РІРёРј Р±Р»РѕРє РїСЂРѕ РїСЂРµРјРёСѓРј
    try:
        from db import is_subscription_active
        if is_subscription_active(update.effective_user.id):
            premium_line = "\n\nрџ’Ћ  РџСЂРµРјРёСѓРј: Сѓ С‚РµР±СЏ РґРѕСЃС‚СѓРїРµРЅ РїРµСЂСЃРѕРЅР°Р»СЊРЅС‹Р№ Р±РѕРЅСѓСЃ вЂ” \\+1 РёРіСЂРѕРє РІ РїСѓР» \\(" \
                           "+ РґРѕСЃС‚СѓРїРЅРѕ: 1/1 \\) Р’С‹Р±РёСЂР°Р№ СЃ СѓРјРѕРј!"
            # РСЃРїСЂР°РІРёРј СЃС‚СЂРѕРєСѓ РЅР° РєРѕСЂСЂРµРєС‚РЅСѓСЋ Р±РµР· РєРѕРЅРєР°С‚РµРЅР°С†РёРё РґР»СЏ С‡РёС‚Р°РµРјРѕСЃС‚Рё
            premium_line = "\n\nрџ’Ћ  РџСЂРµРјРёСѓРј: Сѓ С‚РµР±СЏ РґРѕСЃС‚СѓРїРµРЅ РїРµСЂСЃРѕРЅР°Р»СЊРЅС‹Р№ Р±РѕРЅСѓСЃ вЂ” \\+1 РёРіСЂРѕРє РІ РїСѓР» \\(" \
                           "РґРѕСЃС‚СѓРїРЅРѕ: 1/1\\) Р’С‹Р±РёСЂР°Р№ СЃ СѓРјРѕРј\\!"
            intro = intro + premium_line
    except Exception:
        pass

    await message.reply_text(intro, parse_mode="MarkdownV2")
    # Р”Р»СЏ РїСЂРµРјРёСѓРј-РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ вЂ” РїРѕРєР°Р·Р°С‚СЊ РєРЅРѕРїРєСѓ Р°РєС‚РёРІР°С†РёРё Р±РѕРЅСѓСЃР°
    try:
        from db import is_subscription_active
        if is_subscription_active(update.effective_user.id):
            print("[DEBUG] tour_start: user has active subscription, showing premium button")
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton('Р”РѕР±Р°РІРёС‚СЊ РёРіСЂРѕРєР° РІ РїСѓР»', callback_data='premium_add_pool')]]
            )
            sent = await message.reply_text('рџ’Ћ РџСЂРµРјРёСѓРј-РѕРїС†РёСЏ', reply_markup=kb)
            try:
                # Р—Р°РїРѕРјРЅРёРј РґР»СЏ РґРёР°РіРЅРѕСЃС‚РёРєРё id СЃРѕРѕР±С‰РµРЅРёСЏ СЃ РїСЂРµРјРёСѓРј-РєРЅРѕРїРєРѕР№
                context.user_data['premium_button_chat_id'] = sent.chat_id
                context.user_data['premium_button_message_id'] = sent.message_id
                print(f"[DEBUG] tour_start: premium button message_id={sent.message_id}")
            except Exception as e:
                print(f"[WARN] tour_start: failed to store premium button ids: {e}")
    except Exception:
        pass
    # РЎСЂР°Р·Сѓ РїРѕРєР°Р·С‹РІР°РµРј РІС‹Р±РѕСЂ РїРµСЂРІРѕРіРѕ РЅР°РїР°РґР°СЋС‰РµРіРѕ!
    return await tour_forward_1(update, context)


async def premium_add_pool_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # РћР±СЂР°Р±РѕС‚РєР° РЅР°Р¶Р°С‚РёСЏ РїСЂРµРјРёСѓРј-РєРЅРѕРїРєРё: С„РёРєСЃРёСЂСѓРµРј С„Р»Р°Рі РІ user_data
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
            await query.message.reply_text("РџСЂРµРјРёСѓРј РЅРµРґРѕСЃС‚СѓРїРµРЅ. РћС„РѕСЂРјРёС‚Рµ /subscribe, С‡С‚РѕР±С‹ Р°РєС‚РёРІРёСЂРѕРІР°С‚СЊ Р±РѕРЅСѓСЃ.")
            return TOUR_FORWARD_1
    except Exception:
        print("[WARN] premium_add_pool_callback: failed to check subscription")
    # РЈСЃС‚Р°РЅРѕРІРёРј С„Р»Р°РіРё РїСЂРµРјРёСѓРј-СЂРµР¶РёРјР°: РґРѕР±Р°РІР»РµРЅРёРµ РІ РїСѓР» (Р±РµР· Р°РІС‚РѕРґРѕР±Р°РІР»РµРЅРёСЏ РІ СЃРѕСЃС‚Р°РІ)
    context.user_data['premium_extra_available'] = True
    context.user_data['premium_mode'] = 'add_to_pool'
    print("[DEBUG] premium_add_pool_callback: premium_extra_available=True set")
    # РЈРґР°Р»РёРј РїСЂРµРґС‹РґСѓС‰РµРµ СЃРѕРѕР±С‰РµРЅРёРµ СЃ РІС‹Р±РѕСЂРѕРј РёРіСЂРѕРєРѕРІ, РµСЃР»Рё СЃРѕС…СЂР°РЅРµРЅРѕ
    try:
        chat_id = context.user_data.get('last_choice_chat_id')
        msg_id = context.user_data.get('last_choice_message_id')
        if chat_id and msg_id:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            print(f"[DEBUG] premium_add_pool_callback: deleted last choice message id={msg_id}")
            # РћС‡РёСЃС‚РёРј СЃРѕС…СЂР°РЅС‘РЅРЅС‹Рµ Р·РЅР°С‡РµРЅРёСЏ
            context.user_data.pop('last_choice_chat_id', None)
            context.user_data.pop('last_choice_message_id', None)
    except Exception:
        print("[WARN] premium_add_pool_callback: failed to delete last choice message")
    # РўР°РєР¶Рµ СѓРґР°Р»РёРј СЃРѕРѕР±С‰РµРЅРёРµ СЃ СЃР°РјРѕР№ РїСЂРµРјРёСѓРј-РєРЅРѕРїРєРѕР№
    try:
        await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
        print(f"[DEBUG] premium_add_pool_callback: deleted premium button message id={query.message.message_id}")
    except Exception:
        print("[WARN] premium_add_pool_callback: failed to delete premium button message")
    await query.message.reply_text("рџ’Ћ РџРµСЂСЃРѕРЅР°Р»СЊРЅС‹Р№ Р±РѕРЅСѓСЃ Р°РєС‚РёРІРёСЂРѕРІР°РЅ: +1 РёРіСЂРѕРє РІ РїСѓР».\n\nРќР°РїРёС€РёС‚Рµ РєРѕРјР°РЅРґСѓ РёРіСЂРѕРєР°")
    return PREMIUM_TEAM


async def premium_team_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # РџРѕР»СѓС‡Р°РµРј С‚РµРєСЃС‚ РєРѕРјР°РЅРґС‹ Рё РїСЂРѕСЃРёРј РІС‹Р±СЂР°С‚СЊ РїРѕР·РёС†РёСЋ
    team_text = update.message.text.strip()
    context.user_data['premium_team_query'] = team_text
    try:
        print(f"[DEBUG] premium_team_input: received team text='{team_text}'")
    except Exception:
        pass
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton('РЅР°РїР°РґР°СЋС‰РёР№', callback_data='premium_pos_РЅР°РїР°РґР°СЋС‰РёР№')],
        [InlineKeyboardButton('Р·Р°С‰РёС‚РЅРёРє', callback_data='premium_pos_Р·Р°С‰РёС‚РЅРёРє')],
        [InlineKeyboardButton('РІСЂР°С‚Р°СЂСЊ', callback_data='premium_pos_РІСЂР°С‚Р°СЂСЊ')],
    ])
    await update.message.reply_text('Р’С‹Р±РµСЂРёС‚Рµ РїРѕР·РёС†РёСЋ РёРіСЂРѕРєР°', reply_markup=kb)
    return PREMIUM_POSITION


async def premium_position_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    pos = data.replace('premium_pos_', '')
    context.user_data['premium_position'] = pos
    print(f"[DEBUG] premium_position_selected: pos={pos}")
    # РџРѕРєР°Р¶РµРј СЃРїРёСЃРѕРє РёРіСЂРѕРєРѕРІ, РѕС‚С„РёР»СЊС‚СЂРѕРІР°РЅРЅС‹С… РїРѕ РєРѕРјР°РЅРґРµ Рё РїРѕР·РёС†РёРё (РР— Р’РЎР•Р™ Р‘РђР—Р« РР“Р РћРљРћР’)
    try:
        team_text = (context.user_data.get('premium_team_query') or '').strip().lower()
        from db import get_all_players
        all_players = get_all_players()  # (id, name, position, club, nation, age, price)
        budget = context.user_data.get('tour_budget', 0)
        spent = context.user_data.get('tour_selected', {}).get('spent', 0)
        left = max(0, budget - spent)
        # РСЃРєР»СЋС‡РµРЅРёСЏ РїРѕ СѓР¶Рµ РІС‹Р±СЂР°РЅРЅС‹Рј
        selected = context.user_data.get('tour_selected', {})
        exclude_ids = []
        next_state = TOUR_FORWARD_1
        if pos == 'РЅР°РїР°РґР°СЋС‰РёР№':
            exclude_ids = selected.get('forwards', [])
            next_state = TOUR_FORWARD_1
        elif pos == 'Р·Р°С‰РёС‚РЅРёРє':
            exclude_ids = selected.get('defenders', [])
            # Р’С‹Р±РµСЂРµРј РїРѕРґС…РѕРґСЏС‰РµРµ СЃРѕСЃС‚РѕСЏРЅРёРµ РІ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё РѕС‚ СѓР¶Рµ РІС‹Р±СЂР°РЅРЅС‹С…
            next_state = TOUR_DEFENDER_1 if len(exclude_ids) == 0 else TOUR_DEFENDER_2
        elif pos == 'РІСЂР°С‚Р°СЂСЊ':
            gid = selected.get('goalie')
            exclude_ids = [gid] if gid else []
            next_state = TOUR_GOALIE
        # Р¤РёР»СЊС‚СЂР°С†РёСЏ РїРѕ РїРѕР·РёС†РёРё, РєРѕРјР°РЅРґРµ, Р±СЋРґР¶РµС‚Сѓ Рё РёСЃРєР»СЋС‡РµРЅРёСЏРј
        def team_match(t):
            try:
                return team_text in str(t or '').lower()
            except Exception:
                return False
        # РСЃРєР»СЋС‡РёРј РёРіСЂРѕРєРѕРІ, СѓР¶Рµ РІРєР»СЋС‡С‘РЅРЅС‹С… РІ С‚СѓСЂРѕРІС‹Р№ СЂРѕСЃС‚РµСЂ
        tour_roster = context.user_data.get('tour_roster', [])
        tour_ids = set([tr[1] for tr in tour_roster])  # p.id РёР· С‚СѓСЂРѕРІРѕРіРѕ СЃРїРёСЃРєР°
        # РРЅРґРµРєСЃС‹ РІ players: 0-id,1-name,2-position,3-club,6-price
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
            await query.message.reply_text("РџРѕ Р·Р°РґР°РЅРЅС‹Рј С„РёР»СЊС‚СЂР°Рј РёРіСЂРѕРєРѕРІ РЅРµ РЅР°Р№РґРµРЅРѕ. РР·РјРµРЅРёС‚Рµ РєРѕРјР°РЅРґСѓ РёР»Рё РїРѕР·РёС†РёСЋ.")
            return next_state
        # РџРѕСЃС‚СЂРѕРёРј РєР»Р°РІРёР°С‚СѓСЂСѓ
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = []
        for p in filtered:
            btn_text = f"{p[1]} вЂ” {p[6]} HC"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pick_{p[0]}_{pos}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = f"РќР°Р№РґРµРЅРЅС‹Рµ РёРіСЂРѕРєРё ({pos}, РєРѕРјР°РЅРґР° СЃРѕРґРµСЂР¶РёС‚: '{team_text}') вЂ” РѕСЃС‚Р°Р»РѕСЃСЊ HC: {left}"
        sent = await query.message.reply_text(text, reply_markup=reply_markup)
        # РЎРѕС…СЂР°РЅРёРј, С‡С‚РѕР±С‹ РјРѕС‡СЊ СѓРґР°Р»РёС‚СЊ РґР°Р»РµРµ РїСЂРё РЅРµРѕР±С…РѕРґРёРјРѕСЃС‚Рё
        try:
            context.user_data['last_choice_chat_id'] = sent.chat_id
            context.user_data['last_choice_message_id'] = sent.message_id
        except Exception:
            pass
        return next_state
    except Exception as e:
        print(f"[ERROR] premium_position_selected building list: {e}")
        await query.message.reply_text(f"РћС€РёР±РєР° РїРѕСЃС‚СЂРѕРµРЅРёСЏ СЃРїРёСЃРєР°: {e}")
        return TOUR_FORWARD_1

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

async def send_player_choice(update, context, position, exclude_ids, next_state, budget):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    # РЈРЅРёРІРµСЂСЃР°Р»СЊРЅРѕ РїРѕР»СѓС‡Р°РµРј message РґР»СЏ reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message
    # РџРѕР»СѓС‡Р°РµРј Р°РєС‚СѓР°Р»СЊРЅС‹Р№ СЂРѕСЃС‚РµСЂ
    roster = context.user_data['tour_roster']
    # Р¤РёР»СЊС‚СЂСѓРµРј РїРѕ РїРѕР·РёС†РёРё Рё РёСЃРєР»СЋС‡РµРЅРёСЏРј
    players = [p for p in roster if p[3].lower() == position and p[1] not in exclude_ids and p[7] <= budget]
    if not players:
        # РџСЂРѕРІРµСЂРєР°: РµСЃР»Рё РЅРµ С…РІР°С‚Р°РµС‚ HC РґР»СЏ РѕР±СЏР·Р°С‚РµР»СЊРЅРѕРіРѕ РІС‹Р±РѕСЂР°
        text = (
            'рџљЁ Р’С‹ РїСЂРёРІС‹СЃРёР»Рё РїРѕС‚РѕР»РѕРє Р·Р°СЂРїР»Р°С‚. РџРµСЂРµСЃРѕР±РµСЂРёС‚Рµ СЃРѕСЃС‚Р°РІ, С‡С‚РѕР±С‹ РІРїРёСЃР°С‚СЊСЃСЏ РІ Р»РёРјРёС‚.'
        )
        keyboard = [
            [InlineKeyboardButton('РџРµСЂРµСЃРѕР±СЂР°С‚СЊ СЃРѕСЃС‚Р°РІ', callback_data='restart_tour')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(text, reply_markup=reply_markup)
        return ConversationHandler.END
    keyboard = []
    for p in players:
        btn_text = f"{p[2]} вЂ” {p[7]} HC"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pick_{p[1]}_{position}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Р’С‹Р±РµСЂРёС‚Рµ {position} (РѕСЃС‚Р°Р»РѕСЃСЊ HC: {budget})"
    sent_msg = await message.reply_text(text, reply_markup=reply_markup)
    # Р—Р°РїРѕРјРЅРёРј РїРѕСЃР»РµРґРЅРµРµ СЃРѕРѕР±С‰РµРЅРёРµ СЃ РІС‹Р±РѕСЂРѕРј, С‡С‚РѕР±С‹ РјРѕС‡СЊ СѓРґР°Р»РёС‚СЊ РїСЂРё Р°РєС‚РёРІР°С†РёРё РїСЂРµРјРёСѓРј-СЂРµР¶РёРјР°
    try:
        context.user_data['last_choice_chat_id'] = sent_msg.chat_id
        context.user_data['last_choice_message_id'] = sent_msg.message_id
    except Exception:
        pass
    return next_state
    keyboard = []
    for p in players:
        btn_text = f"{p[2]} вЂ” {p[7]} HC"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pick_{p[1]}_{position}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Р’С‹Р±РµСЂРёС‚Рµ {position} (РѕСЃС‚Р°Р»РѕСЃСЊ HC: {budget})"
    await message.reply_text(text, reply_markup=reply_markup)
    return next_state

async def tour_forward_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    picked = context.user_data['tour_selected']['forwards']
    return await send_player_choice(update, context, 'РЅР°РїР°РґР°СЋС‰РёР№', picked, TOUR_FORWARD_2, budget)


async def tour_forward_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data
        print(f"Callback data: {data}", flush=True)
        # РћР¶РёРґР°РµС‚СЃСЏ С„РѕСЂРјР°С‚ pick_<player_id>_РЅР°РїР°РґР°СЋС‰РёР№
        if not data.startswith('pick_') or '_РЅР°РїР°РґР°СЋС‰РёР№' not in data:
            await query.edit_message_text('РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РІС‹Р±РѕСЂ.')
            return TOUR_FORWARD_1
        pid = int(data.split('_')[1])
        # РџРѕР»СѓС‡Р°РµРј РёРіСЂРѕРєР° РїРѕ id
        roster = context.user_data['tour_roster']
        player = next((p for p in roster if p[1] == pid), None)
        added_personal = False
        if not player:
            # Fallback: РёС‰РµРј РІ РѕР±С‰РµР№ Р‘Р” РёРіСЂРѕРєРѕРІ
            try:
                pdb = db.get_player_by_id(pid)
                if pdb:
                    # РџСЂРµРѕР±СЂР°Р·СѓРµРј Рє С„РѕСЂРјР°С‚Сѓ: (tr.cost, p.id, p.name, p.position, p.club, p.nation, p.age, p.price)
                    player = (pdb[6], pdb[0], pdb[1], pdb[2], pdb[3], pdb[4], pdb[5], pdb[6])
                    # Р”РѕР±Р°РІРёРј СЌС‚РѕРіРѕ РёРіСЂРѕРєР° РІ РїРµСЂСЃРѕРЅР°Р»СЊРЅС‹Р№ С‚СѓСЂРѕРІС‹Р№ СЃРїРёСЃРѕРє РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ, РµСЃР»Рё РµС‰С‘ РЅРµС‚
                    try:
                        if not any(p_[1] == pdb[0] for p_ in roster):
                            context.user_data['tour_roster'].append(player)
                        added_personal = True
                        # РџРѕРјРµС‚РёРј РёСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ РїСЂРµРјРёСѓРј-Р±РѕРЅСѓСЃР°
                        context.user_data['premium_extra_available'] = False
                    except Exception:
                        pass
                else:
                    await query.edit_message_text('РРіСЂРѕРє РЅРµ РЅР°Р№РґРµРЅ.')
                    return TOUR_FORWARD_1
            except Exception:
                await query.edit_message_text('РРіСЂРѕРє РЅРµ РЅР°Р№РґРµРЅ.')
                return TOUR_FORWARD_1
        # Р•СЃР»Рё Р°РєС‚РёРІРµРЅ СЂРµР¶РёРј РґРѕР±Р°РІР»РµРЅРёСЏ РІ РїСѓР» вЂ” РЅРµ РґРѕР±Р°РІР»СЏРµРј РІ СЃРѕСЃС‚Р°РІ, Р° С‚РѕР»СЊРєРѕ СЂР°СЃС€РёСЂСЏРµРј РїСѓР»
        if context.user_data.get('premium_mode') == 'add_to_pool':
            try:
                # РЈР±РµРґРёРјСЃСЏ, С‡С‚Рѕ РёРіСЂРѕРє РµСЃС‚СЊ РІ РїРµСЂСЃРѕРЅР°Р»СЊРЅРѕРј РїСѓР»Рµ
                roster = context.user_data['tour_roster']
                if not any(p_[1] == player[1] for p_ in roster):
                    context.user_data['tour_roster'].append(player)
                # Р’С‹РєР»СЋС‡Р°РµРј СЂРµР¶РёРј Рё СЃР¶РёРіР°РµРј Р±РѕРЅСѓСЃ
                context.user_data['premium_mode'] = None
                context.user_data['premium_extra_available'] = False
                # РџРѕРєР°Р¶РµРј РѕР±С‹С‡РЅС‹Р№ РІС‹Р±РѕСЂ РЅР°РїР°РґР°СЋС‰РёС… СЃ СѓС‡С‘С‚РѕРј СЂР°СЃС€РёСЂРµРЅРЅРѕРіРѕ РїСѓР»Р°
                budget = context.user_data['tour_budget']
                spent = context.user_data['tour_selected']['spent']
                left = budget - spent
                picked = context.user_data['tour_selected']['forwards']
                await query.edit_message_text(f"Р”РѕР±Р°РІР»РµРЅ РІ РІР°С€ РїСѓР»: {player[2]} ({player[4]}). РўРµРїРµСЂСЊ РІС‹Р±РµСЂРёС‚Рµ РЅР°РїР°РґР°СЋС‰РµРіРѕ.")
                next_state = TOUR_FORWARD_2 if len(picked) == 0 else TOUR_FORWARD_3
                return await send_player_choice(update, context, 'РЅР°РїР°РґР°СЋС‰РёР№', picked, next_state, left)
            except Exception as e:
                await query.edit_message_text(f"РћС€РёР±РєР° РґРѕР±Р°РІР»РµРЅРёСЏ РІ РїСѓР»: {e}")
                return TOUR_FORWARD_1
        # РџСЂРѕРІРµСЂСЏРµРј Р±СЋРґР¶РµС‚
        budget = context.user_data['tour_budget']
        spent = context.user_data['tour_selected']['spent']
        if spent + player[7] > budget:
            await query.edit_message_text(f'РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ HC РґР»СЏ РІС‹Р±РѕСЂР° {player[1]}!')
            return TOUR_FORWARD_1
        # РЎРѕС…СЂР°РЅСЏРµРј РІС‹Р±РѕСЂ
        context.user_data['tour_selected']['forwards'].append(pid)
        context.user_data['tour_selected']['spent'] += player[7]
        left = budget - context.user_data['tour_selected']['spent']
        player_name = escape_md(str(player[2]))
        cost = escape_md(str(player[7]))
        left_str = escape_md(str(left))
        msg = f'Р’С‹ РІС‹Р±СЂР°Р»Рё {player_name} \\({cost}\\)\n\n*РћСЃС‚Р°РІС€РёР№СЃСЏ Р±СЋРґР¶РµС‚: {left_str}*'
        await query.edit_message_text(msg, parse_mode="MarkdownV2")
        if len(context.user_data['tour_selected']['forwards']) == 1:
            print("tour_forward_callback SUCCESS: РїРµСЂРµС…РѕРґ Рє tour_forward_2", flush=True)
            return await tour_forward_2(update, context)
        elif len(context.user_data['tour_selected']['forwards']) == 2:
            print("tour_forward_callback SUCCESS: РїРµСЂРµС…РѕРґ Рє tour_forward_3", flush=True)
            return await tour_forward_3(update, context)
        elif len(context.user_data['tour_selected']['forwards']) == 3:
            print("tour_forward_callback SUCCESS: РїРµСЂРµС…РѕРґ Рє tour_defender_1", flush=True)
            await tour_defender_1(update, context)
            return TOUR_DEFENDER_1
    except Exception as e:
        print(f"tour_forward_callback ERROR: {e}", flush=True)
        logger.exception("Exception in tour_forward_callback")
        await query.edit_message_text(f"РћС€РёР±РєР°: {e}")
        return TOUR_FORWARD_1
    finally:
        print("tour_forward_callback FINISHED", flush=True)


async def tour_forward_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = context.user_data['tour_selected']['forwards']
    return await send_player_choice(update, context, 'РЅР°РїР°РґР°СЋС‰РёР№', picked, TOUR_FORWARD_3, left)


async def tour_forward_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = context.user_data['tour_selected']['forwards']
    # РџРѕРєР°Р·С‹РІР°РµРј РєР»Р°РІРёР°С‚СѓСЂСѓ РґР»СЏ С‚СЂРµС‚СЊРµРіРѕ РЅР°РїР°РґР°СЋС‰РµРіРѕ, next_state вЂ” TOUR_FORWARD_3
    return await send_player_choice(update, context, 'РЅР°РїР°РґР°СЋС‰РёР№', picked, TOUR_FORWARD_3, left)

async def tour_defender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data
        print(f"Callback data: {data}", flush=True)
        # РћР¶РёРґР°РµС‚СЃСЏ С„РѕСЂРјР°С‚ pick_<player_id>_Р·Р°С‰РёС‚РЅРёРє
        if not data.startswith('pick_') or '_Р·Р°С‰РёС‚РЅРёРє' not in data:
            await query.edit_message_text('РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РІС‹Р±РѕСЂ.')
            return TOUR_DEFENDER_1
        pid = int(data.split('_')[1])
        roster = context.user_data['tour_roster']
        player = next((p for p in roster if p[1] == pid), None)
        added_personal = False
        if not player:
            # Fallback: РёС‰РµРј РІ РѕР±С‰РµР№ Р‘Р” РёРіСЂРѕРєРѕРІ
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
                    await query.edit_message_text('РРіСЂРѕРє РЅРµ РЅР°Р№РґРµРЅ.')
                    return TOUR_DEFENDER_1
            except Exception:
                await query.edit_message_text('РРіСЂРѕРє РЅРµ РЅР°Р№РґРµРЅ.')
                return TOUR_DEFENDER_1
        # Р РµР¶РёРј РґРѕР±Р°РІР»РµРЅРёСЏ РІ РїСѓР» вЂ” Р±РµР· Р°РІС‚РѕРґРѕР±Р°РІР»РµРЅРёСЏ РІ СЃРѕСЃС‚Р°РІ
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
                # РџРѕСЃР»Рµ РґРѕР±Р°РІР»РµРЅРёСЏ РІ РїСѓР» РІСЃРµРіРґР° РІРѕР·РІСЂР°С‰Р°РµРјСЃСЏ Рє РІС‹Р±РѕСЂСѓ РЅР°РїР°РґР°СЋС‰РёС…
                forwards_picked = context.user_data['tour_selected']['forwards']
                await query.edit_message_text(f"Р”РѕР±Р°РІР»РµРЅ РІ РІР°С€ РїСѓР»: {player[2]} ({player[4]}). РўРµРїРµСЂСЊ РІС‹Р±РµСЂРёС‚Рµ РЅР°РїР°РґР°СЋС‰РµРіРѕ.")
                next_state = TOUR_FORWARD_2 if len(forwards_picked) == 0 else TOUR_FORWARD_3
                return await send_player_choice(update, context, 'РЅР°РїР°РґР°СЋС‰РёР№', forwards_picked, next_state, left)
            except Exception as e:
                await query.edit_message_text(f"РћС€РёР±РєР° РґРѕР±Р°РІР»РµРЅРёСЏ РІ РїСѓР»: {e}")
                return TOUR_FORWARD_1
        budget = context.user_data['tour_budget']
        spent = context.user_data['tour_selected']['spent']
        if spent + player[7] > budget:
            await query.edit_message_text(f'РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ HC РґР»СЏ РІС‹Р±РѕСЂР° {player[1]}!')
            return TOUR_DEFENDER_1
        context.user_data['tour_selected']['defenders'].append(pid)
        context.user_data['tour_selected']['spent'] += player[7]
        left = budget - context.user_data['tour_selected']['spent']
        player_name = escape_md(str(player[2]))
        cost = escape_md(str(player[7]))
        left_str = escape_md(str(left))
        msg = f'Р’С‹ РІС‹Р±СЂР°Р»Рё {player_name} \\({cost}\\)\n\n*РћСЃС‚Р°РІС€РёР№СЃСЏ Р±СЋРґР¶РµС‚: {left_str}*'
        await query.edit_message_text(msg, parse_mode="MarkdownV2")
        if len(context.user_data['tour_selected']['defenders']) == 1:
            print("tour_defender_callback SUCCESS: РїРµСЂРµС…РѕРґ Рє tour_defender_2", flush=True)
            return await tour_defender_2(update, context)
        elif len(context.user_data['tour_selected']['defenders']) == 2:
            print("tour_defender_callback SUCCESS: РїРµСЂРµС…РѕРґ Рє tour_goalie", flush=True)
            await tour_goalie(update, context)
            return TOUR_GOALIE
    except Exception as e:
        print(f"tour_defender_callback ERROR: {e}", flush=True)
        logger.exception("Exception in tour_defender_callback")
        await query.edit_message_text(f"РћС€РёР±РєР°: {e}")
        return TOUR_DEFENDER_1
    finally:
        print("tour_defender_callback FINISHED", flush=True)


async def tour_defender_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = context.user_data['tour_selected']['defenders']
    return await send_player_choice(update, context, 'Р·Р°С‰РёС‚РЅРёРє', picked, TOUR_DEFENDER_2, left)

async def tour_defender_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = context.user_data['tour_selected']['defenders']
    # РџРѕРєР°Р·С‹РІР°РµРј РєР»Р°РІРёР°С‚СѓСЂСѓ РґР»СЏ РІС‚РѕСЂРѕРіРѕ Р·Р°С‰РёС‚РЅРёРєР°, next_state вЂ” TOUR_DEFENDER_2
    return await send_player_choice(update, context, 'Р·Р°С‰РёС‚РЅРёРє', picked, TOUR_DEFENDER_2, left)

async def tour_goalie_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data
        print(f"Callback data: {data}", flush=True)
        # РћР¶РёРґР°РµС‚СЃСЏ С„РѕСЂРјР°С‚ pick_<player_id>_РІСЂР°С‚Р°СЂСЊ
        if not data.startswith('pick_') or '_РІСЂР°С‚Р°СЂСЊ' not in data:
            await query.edit_message_text('РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РІС‹Р±РѕСЂ.')
            return TOUR_GOALIE
        pid = int(data.split('_')[1])
        roster = context.user_data['tour_roster']
        player = next((p for p in roster if p[1] == pid), None)
        added_personal = False
        if not player:
            # Fallback: РёС‰РµРј РІ РѕР±С‰РµР№ Р‘Р” РёРіСЂРѕРєРѕРІ
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
                    await query.edit_message_text('РРіСЂРѕРє РЅРµ РЅР°Р№РґРµРЅ.')
                    return TOUR_GOALIE
            except Exception:
                await query.edit_message_text('РРіСЂРѕРє РЅРµ РЅР°Р№РґРµРЅ.')
                return TOUR_GOALIE
        # Р РµР¶РёРј РґРѕР±Р°РІР»РµРЅРёСЏ РІ РїСѓР» вЂ” Р±РµР· Р°РІС‚РѕРґРѕР±Р°РІР»РµРЅРёСЏ РІ СЃРѕСЃС‚Р°РІ
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
                # РџРѕСЃР»Рµ РґРѕР±Р°РІР»РµРЅРёСЏ РІ РїСѓР» РІСЃРµРіРґР° РІРѕР·РІСЂР°С‰Р°РµРјСЃСЏ Рє РІС‹Р±РѕСЂСѓ РЅР°РїР°РґР°СЋС‰РёС…
                forwards_picked = context.user_data['tour_selected']['forwards']
                await query.edit_message_text(f"Р”РѕР±Р°РІР»РµРЅ РІ РІР°С€ РїСѓР»: {player[2]} ({player[4]}). РўРµРїРµСЂСЊ РІС‹Р±РµСЂРёС‚Рµ РЅР°РїР°РґР°СЋС‰РµРіРѕ.")
                next_state = TOUR_FORWARD_2 if len(forwards_picked) == 0 else TOUR_FORWARD_3
                return await send_player_choice(update, context, 'РЅР°РїР°РґР°СЋС‰РёР№', forwards_picked, next_state, left)
            except Exception as e:
                await query.edit_message_text(f"РћС€РёР±РєР° РґРѕР±Р°РІР»РµРЅРёСЏ РІ РїСѓР»: {e}")
                return TOUR_FORWARD_1
        budget = context.user_data['tour_budget']
        spent = context.user_data['tour_selected']['spent']
        if spent + player[7] > budget:
            await query.edit_message_text(f'РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ HC РґР»СЏ РІС‹Р±РѕСЂР° {player[1]}!')
            return TOUR_GOALIE
        context.user_data['tour_selected']['goalie'] = pid
        context.user_data['tour_selected']['spent'] += player[7]
        left = budget - context.user_data['tour_selected']['spent']
        player_name = escape_md(str(player[2]))
        cost = escape_md(str(player[7]))
        left_str = escape_md(str(left))
        msg = f'Р’С‹ РІС‹Р±СЂР°Р»Рё {player_name} \\({cost}\\)\n\n*РћСЃС‚Р°РІС€РёР№СЃСЏ Р±СЋРґР¶РµС‚: {left_str}*'
        await query.edit_message_text(msg, parse_mode="MarkdownV2")
        # РџРѕРєР°Р·С‹РІР°РµРј СЌС‚Р°Рї РІС‹Р±РѕСЂР° РєР°РїРёС‚Р°РЅР°
        return await tour_captain(update, context)
    except Exception as e:
        print(f"tour_goalie_callback ERROR: {e}", flush=True)
        logger.exception("Exception in tour_goalie_callback")
        await query.edit_message_text(f"РћС€РёР±РєР°: {e}")
        return TOUR_GOALIE
    finally:
        print("tour_goalie_callback FINISHED", flush=True)


async def tour_goalie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = []
    # Р’СЂР°С‚Р°СЂСЊ С‚РѕР»СЊРєРѕ РѕРґРёРЅ, РЅРµ РЅСѓР¶РµРЅ exclude РєСЂРѕРјРµ СѓР¶Рµ РІС‹Р±СЂР°РЅРЅРѕРіРѕ
    if context.user_data['tour_selected']['goalie']:
        picked = [context.user_data['tour_selected']['goalie']]
    return await send_player_choice(update, context, 'РІСЂР°С‚Р°СЂСЊ', picked, TOUR_CAPTAIN, left)


async def tour_captain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    # РЈРЅРёРІРµСЂСЃР°Р»СЊРЅРѕ РїРѕР»СѓС‡Р°РµРј message РґР»СЏ reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message

    selected = context.user_data['tour_selected']
    roster = context.user_data['tour_roster']
    # РЎРѕР±РёСЂР°РµРј id РїРѕР»РµРІС‹С… РёРіСЂРѕРєРѕРІ
    field_ids = selected['forwards'] + selected['defenders']
    # РџРѕР»СѓС‡Р°РµРј РёРЅС„Сѓ РїРѕ РёРіСЂРѕРєР°Рј
    candidates = [p for p in roster if p[1] in field_ids]
    keyboard = [
        [InlineKeyboardButton(f"{p[2]} ({p[3]})", callback_data=f"pick_captain_{p[1]}")]
        for p in candidates
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "РќР°Р·РЅР°С‡СЊ РѕРґРЅРѕРіРѕ РїРѕР»РµРІРѕРіРѕ РёРіСЂРѕРєР° РёР· СЃРѕСЃС‚Р°РІР° РєР°РїРёС‚Р°РЅРѕРј. Р•РіРѕ РёС‚РѕРіРѕРІС‹Рµ РѕС‡РєРё СѓРјРЅРѕР¶РёРј РЅР° 1.5"
    await message.reply_text(text, reply_markup=reply_markup)
    return TOUR_CAPTAIN

# --- РћР±СЂР°Р±РѕС‚С‡РёРє РІС‹Р±РѕСЂР° РєР°РїРёС‚Р°РЅР° ---
async def tour_captain_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith('pick_captain_'):
        await query.edit_message_text('РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РІС‹Р±РѕСЂ РєР°РїРёС‚Р°РЅР°.')
        return TOUR_CAPTAIN
    captain_id = int(data.replace('pick_captain_', ''))
    selected = context.user_data['tour_selected']
    roster = context.user_data['tour_roster']
    field_ids = selected['forwards'] + selected['defenders']
    if captain_id not in field_ids:
        await query.edit_message_text('РљР°РїРёС‚Р°РЅ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РїРѕР»РµРІС‹Рј РёРіСЂРѕРєРѕРј РёР· РІР°С€РµРіРѕ СЃРѕСЃС‚Р°РІР°!')
        return TOUR_CAPTAIN
    context.user_data['tour_selected']['captain'] = captain_id
    # Р¤РѕСЂРјРёСЂСѓРµРј РєСЂР°СЃРёРІРѕРµ РёС‚РѕРіРѕРІРѕРµ СЃРѕРѕР±С‰РµРЅРёРµ СЃ РєР°СЃС‚РѕРјРЅС‹Рј СЌРјРѕРґР·Рё
    # def custom_emoji_entity(emoji_id, offset):
    #     return MessageEntity(
    #         type=MessageEntityType.CUSTOM_EMOJI,
    #         offset=offset,
    #         length=1,  # ASCII-СЃРёРјРІРѕР»
    #         custom_emoji_id=str(emoji_id)
    #     )

    def get_name(pid, captain=False):
        p = next((x for x in roster if x[1]==pid), None)
        if not p:
            return str(pid)
        base = f"{p[2]} ({p[4]})"
        if captain:
            return f"рџЏ… {base}"
        return base

    def format_final_roster_md(goalie, defenders, forwards, captain, spent, budget):
        lines = [
            '*Р’Р°С€ РёС‚РѕРіРѕРІС‹Р№ СЃРѕСЃС‚Р°РІ:*',
            '',
            escape_md(goalie),
            escape_md(defenders),
            escape_md(forwards),
            '',
            f'РљР°РїРёС‚Р°РЅ: {escape_md(captain)}',
            f'РџРѕС‚СЂР°С‡РµРЅРѕ: *{escape_md(str(spent))}*/*{escape_md(str(budget))}*'
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
    save_user_tour_roster(user_id, tour_id, roster_dict, captain_id, spent)

    text = format_final_roster_md(goalie_str, defenders_str, forwards_str, captain_str, spent, budget)
    keyboard = [[InlineKeyboardButton('РџРµСЂРµСЃРѕР±СЂР°С‚СЊ СЃРѕСЃС‚Р°РІ', callback_data='restart_tour')]]
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
    user_id = query.from_user.id
    active_tour = get_active_tour()
    if active_tour:
        tour_id = active_tour['id']
        clear_user_tour_roster(user_id, tour_id)
    # Р—Р°РїСѓСЃРєР°РµРј РїСЂРѕС†РµСЃСЃ РІС‹Р±РѕСЂР° СЃРѕСЃС‚Р°РІР° Р·Р°РЅРѕРІРѕ С‡РµСЂРµР· /tour (ConversationHandler entry_point)
    await context.bot.send_message(chat_id=query.message.chat_id, text="/tour")
    return ConversationHandler.END

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from db import get_budget
    # РЈРЅРёРІРµСЂСЃР°Р»СЊРЅРѕ РїРѕР»СѓС‡Р°РµРј message РґР»СЏ reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message
    budget = get_budget()
    budget_str = str(budget).replace("-", r"\-") if budget is not None else 'N/A'
    text = rf"""*РџСЂР°РІРёР»Р° РёРіСЂС‹:*

РЎРѕР±РµСЂРёС‚Рµ СЃРІРѕСЋ РєРѕРјР°РЅРґСѓ РёР· 6 РёРіСЂРѕРєРѕРІ \(3 РЅР°РїР°РґР°СЋС‰РёС…, 2 Р·Р°С‰РёС‚РЅРёРєР°, 1 РІСЂР°С‚Р°СЂСЊ\) СЃ РѕРіСЂР°РЅРёС‡РµРЅРЅС‹Рј Р±СЋРґР¶РµС‚РѕРј\. РЈ РєР°Р¶РґРѕРіРѕ РёРіСЂРѕРєР° СЃРІРѕСЏ СЃС‚РѕРёРјРѕСЃС‚СЊ \- 10, 30, 40 РёР»Рё 50 РµРґРёРЅРёС†\.

вљЎпёЏ РќР°Р·РЅР°С‡СЊ РѕРґРЅРѕРіРѕ РїРѕР»РµРІРѕРіРѕ РёРіСЂРѕРєР° РёР· СЃРѕСЃС‚Р°РІР° РєР°РїРёС‚Р°РЅРѕРј

*Р’Р°С€ Р±СЋРґР¶РµС‚: {budget_str}*

РЎРѕР±СЂР°С‚СЊ СЃРѕСЃС‚Р°РІ \- /tour"""
    await message.reply_text(text, parse_mode="MarkdownV2")

async def hc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # РЈРЅРёРІРµСЂСЃР°Р»СЊРЅРѕ РїРѕР»СѓС‡Р°РµРј message РґР»СЏ reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message

    user = update.effective_user
    data = db.get_user_by_id(user.id)
    if data:
        await message.reply_text(f'рџ’° РўРІРѕР№ Р±Р°Р»Р°РЅСЃ: {data[3]} HC')
    else:
        await message.reply_text(
            'рџљ« РўРµР±СЏ РµС‰Рµ РЅРµС‚ РІ СЃРїРёСЃРєРµ РіРµРЅРјРµРЅРµРґР¶РµСЂРѕРІ Р¤РµРЅС‚РµР·Рё Р”СЂР°С„С‚ РљРҐР›\n\n'
            'Р—Р°СЂРµРіРёСЃС‚СЂРёСЂСѓР№СЃСЏ С‡РµСЂРµР· /start вЂ” Рё РІРїРµСЂС‘Рґ Рє СЃР±РѕСЂРєРµ СЃРѕСЃС‚Р°РІР°!'
        )
