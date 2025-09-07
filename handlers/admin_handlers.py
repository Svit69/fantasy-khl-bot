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
import datetime

# --- Р”РѕР±Р°РІР»РµРЅРёРµ РёРіСЂРѕРєР° ---
ADD_NAME, ADD_POSITION, ADD_CLUB, ADD_NATION, ADD_AGE, ADD_PRICE = range(6)

# --- Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ РёРіСЂРѕРєР° ---
EDIT_NAME, EDIT_POSITION, EDIT_CLUB, EDIT_NATION, EDIT_AGE, EDIT_PRICE = range(6, 12)

# (Р·Р°СЂРµР·РµСЂРІРёСЂРѕРІР°РЅРѕ РґР»СЏ Р±СѓРґСѓС‰РёС… РєРѕРЅСЃС‚Р°РЅС‚ СЃРѕСЃС‚РѕСЏРЅРёР№ 12-13)

# --- РњР°РіР°Р·РёРЅ: СЃРѕСЃС‚РѕСЏРЅРёСЏ РґРёР°Р»РѕРіР° ---
SHOP_TEXT_WAIT = 30
SHOP_IMAGE_WAIT = 31

async def add_image_shop_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text("РћС‚РїСЂР°РІСЊС‚Рµ С‚РµРєСЃС‚ РѕРїРёСЃР°РЅРёСЏ РјР°РіР°Р·РёРЅР°:")
    return SHOP_TEXT_WAIT

async def add_image_shop_text(update, context):
    text = (update.message.text or '').strip()
    try:
        db.update_shop_text(text)
        context.user_data['shop_text'] = text
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СЃРѕС…СЂР°РЅРµРЅРёСЏ С‚РµРєСЃС‚Р°: {e}")
        return ConversationHandler.END
    await update.message.reply_text("РўРµРїРµСЂСЊ РѕС‚РїСЂР°РІСЊС‚Рµ РѕРґРЅРѕ С„РѕС‚Рѕ РјР°РіР°Р·РёРЅР° РІ СЃР»РµРґСѓСЋС‰РµРј СЃРѕРѕР±С‰РµРЅРёРё.")
    return SHOP_IMAGE_WAIT

async def add_image_shop_photo(update, context):
    if not update.message or not update.message.photo:
        await update.message.reply_text("РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РѕС‚РїСЂР°РІСЊС‚Рµ РёРјРµРЅРЅРѕ С„РѕС‚Рѕ.")
        return SHOP_IMAGE_WAIT
    try:
        photo = update.message.photo[-1]
        file_id = photo.file_id
        tg_file = await photo.get_file()
        os.makedirs(IMAGES_DIR, exist_ok=True)
        filename = 'shop.jpg'
        file_path = os.path.join(IMAGES_DIR, filename)
        # РїРѕРїС‹С‚РєР° СѓРЅРёРІРµСЂСЃР°Р»СЊРЅРѕР№ Р·Р°РіСЂСѓР·РєРё РґР»СЏ PTB v20
        try:
            await tg_file.download_to_drive(file_path)
        except Exception:
            await tg_file.download(custom_path=file_path)
        db.update_shop_image(filename, file_id)
        await update.message.reply_text("Р“РѕС‚РѕРІРѕ. РњР°РіР°Р·РёРЅ РѕР±РЅРѕРІР»С‘РЅ.")
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СЃРѕС…СЂР°РЅРµРЅРёСЏ С„РѕС‚Рѕ: {e}")
    return ConversationHandler.END

async def add_image_shop_cancel(update, context):
    await update.message.reply_text("РћР±РЅРѕРІР»РµРЅРёРµ РјР°РіР°Р·РёРЅР° РѕС‚РјРµРЅРµРЅРѕ.")
    return ConversationHandler.END

# --- РЈРґР°Р»РµРЅРёРµ РїРѕРґРїРёСЃРѕРє (Р·Р°РїР°СЂРѕР»РµРЅРЅС‹Рµ РєРѕРјР°РЅРґС‹) ---
DEL_SUB_WAIT_PASSWORD = 10010
DEL_SUB_WAIT_USERNAME = 10011

async def delete_sub_by_username_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ.")
        return ConversationHandler.END
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РїР°СЂРѕР»СЊ РґР»СЏ СѓРґР°Р»РµРЅРёСЏ РїРѕРґРїРёСЃРєРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ:")
    return DEL_SUB_WAIT_PASSWORD

async def delete_sub_by_username_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pw = (update.message.text or '').strip()
    checker = _get_purge_password_checker()
    if not checker(pw):
        await update.message.reply_text("РќРµРІРµСЂРЅС‹Р№ РїР°СЂРѕР»СЊ. РћС‚РјРµРЅР°.")
        return ConversationHandler.END
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ @username РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ (Р±РµР· РїСЂРѕР±РµР»РѕРІ):")
    return DEL_SUB_WAIT_USERNAME

async def delete_sub_by_username_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = (update.message.text or '').strip()
    if username.startswith('@'):
        username = username[1:]
    try:
        row = db.get_user_by_username(username)
        if not row:
            await update.message.reply_text("РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ.")
            return ConversationHandler.END
        user_id = row[0] if isinstance(row, tuple) else row['telegram_id'] if isinstance(row, dict) else row[0]
        deleted = db.delete_subscription_by_user_id(user_id)
        await update.message.reply_text(f"РЈРґР°Р»РµРЅРѕ РїРѕРґРїРёСЃРѕРє: {deleted} Сѓ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ @{username}.")
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР°: {e}")
    return ConversationHandler.END

async def delete_sub_by_username_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("РћС‚РјРµРЅРµРЅРѕ.")
    return ConversationHandler.END

PURGE_SUBS_WAIT_PASSWORD = 10020

async def purge_subscriptions_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ.")
        return ConversationHandler.END
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РїР°СЂРѕР»СЊ РґР»СЏ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ СѓРґР°Р»РµРЅРёСЏ Р’РЎР•РҐ РїРѕРґРїРёСЃРѕРє:")
    return PURGE_SUBS_WAIT_PASSWORD

async def purge_subscriptions_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pw = (update.message.text or '').strip()
    checker = _get_purge_password_checker()
    if not checker(pw):
        await update.message.reply_text("РќРµРІРµСЂРЅС‹Р№ РїР°СЂРѕР»СЊ. РћС‚РјРµРЅР°.")
        return ConversationHandler.END
    try:
        deleted = db.purge_all_subscriptions()
        await update.message.reply_text(f"РЈРґР°Р»РµРЅРѕ РїРѕРґРїРёСЃРѕРє: {deleted}.")
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СѓРґР°Р»РµРЅРёСЏ: {e}")
    return ConversationHandler.END

# --- РЈРґР°Р»РµРЅРёРµ РћР”РќРћР“Рћ С‚СѓСЂР° РїРѕ id (Р·Р°РїР°СЂРѕР»РµРЅРЅР°СЏ РєРѕРјР°РЅРґР°) ---
DEL_TOUR_WAIT_PASSWORD = 10030
DEL_TOUR_WAIT_ID = 10031

async def delete_tour_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ.")
        return ConversationHandler.END
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РїР°СЂРѕР»СЊ РґР»СЏ СѓРґР°Р»РµРЅРёСЏ РўРЈР Рђ РїРѕ id:")
    return DEL_TOUR_WAIT_PASSWORD

async def delete_tour_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pw = (update.message.text or '').strip()
    checker = _get_purge_password_checker()
    if not checker(pw):
        await update.message.reply_text("РќРµРІРµСЂРЅС‹Р№ РїР°СЂРѕР»СЊ. РћС‚РјРµРЅР°.")
        return ConversationHandler.END
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ id С‚СѓСЂР° (С†РµР»РѕРµ С‡РёСЃР»Рѕ):")
    return DEL_TOUR_WAIT_ID

async def delete_tour_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (update.message.text or '').strip()
    if not txt.isdigit():
        await update.message.reply_text("РќСѓР¶РЅРѕ С‡РёСЃР»Рѕ. РћС‚РјРµРЅРµРЅРѕ.")
        return ConversationHandler.END
    tour_id = int(txt)
    try:
        deleted = db.delete_tour_by_id(tour_id)
        if deleted:
            await update.message.reply_text(f"РўСѓСЂ #{tour_id} СѓРґР°Р»С‘РЅ. РЎРІСЏР·Р°РЅРЅС‹Рµ РґР°РЅРЅС‹Рµ РѕС‡РёС‰РµРЅС‹.")
        else:
            await update.message.reply_text(f"РўСѓСЂ #{tour_id} РЅРµ РЅР°Р№РґРµРЅ.")
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СѓРґР°Р»РµРЅРёСЏ: {e}")
    return ConversationHandler.END

async def delete_tour_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("РћС‚РјРµРЅРµРЅРѕ.")
    return ConversationHandler.END
# --- PURGE TOURS (Р·Р°РїР°СЂРѕР»РµРЅРЅР°СЏ РєРѕРјР°РЅРґР°) ---
PURGE_WAIT_PASSWORD = 9991

def _get_purge_password_checker():
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ С„СѓРЅРєС†РёСЋ checker(pw:str)->bool, РЅРµ СЂР°СЃРєСЂС‹РІР°СЏ РїР°СЂРѕР»СЊ РІ РєРѕРґРµ.
    РџСЂРѕРІРµСЂСЏРµС‚СЃСЏ СЃРЅР°С‡Р°Р»Р° РїРµСЂРµРјРµРЅРЅР°СЏ РѕРєСЂСѓР¶РµРЅРёСЏ PURGE_TOURS_PASSWORD_HASH (sha256),
    РёРЅР°С‡Рµ PURGE_TOURS_PASSWORD (plain)."""
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
        await update.message.reply_text("РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ.")
        return ConversationHandler.END
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РїР°СЂРѕР»СЊ РґР»СЏ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ СѓРґР°Р»РµРЅРёСЏ Р’РЎР•РҐ С‚СѓСЂРѕРІ:")
    return PURGE_WAIT_PASSWORD

async def purge_tours_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pw = (update.message.text or '').strip()
    checker = _get_purge_password_checker()
    if not checker(pw):
        await update.message.reply_text("РќРµРІРµСЂРЅС‹Р№ РїР°СЂРѕР»СЊ. РћС‚РјРµРЅР°.")
        return ConversationHandler.END
    try:
        deleted = db.purge_all_tours()
        await update.message.reply_text(f"РЈРґР°Р»РµРЅРѕ С‚СѓСЂРѕРІ: {deleted}. РЎРѕСЃС‚Р°РІС‹ Рё СЃРІСЏР·Р°РЅРЅС‹Рµ РґР°РЅРЅС‹Рµ С‚Р°РєР¶Рµ РѕС‡РёС‰РµРЅС‹.")
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СѓРґР°Р»РµРЅРёСЏ: {e}")
    return ConversationHandler.END

async def purge_tours_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("РћС‚РјРµРЅРµРЅРѕ.")
    return ConversationHandler.END

async def add_image_shop_cancel(update, context):
    await update.message.reply_text("РћР±РЅРѕРІР»РµРЅРёРµ РјР°РіР°Р·РёРЅР° РѕС‚РјРµРЅРµРЅРѕ.")
    return ConversationHandler.END

# --- Р”РѕР±Р°РІР»РµРЅРёРµ РёРіСЂРѕРєР° ---
async def add_player_start(update, context):
    logger.info("add_player_start called")
    if not await admin_only(update, context):
        logger.warning("Admin check failed in add_player_start")
        return ConversationHandler.END
    logger.info("Sending name prompt")
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РёРјСЏ Рё С„Р°РјРёР»РёСЋ РёРіСЂРѕРєР°:")
    logger.info(f"Returning ADD_NAME state: {ADD_NAME}")
    return ADD_NAME

async def add_player_name(update, context):
    try:
        logger.info(f"add_player_name called with text: {update.message.text}")
        if not update.message or not update.message.text or not update.message.text.strip():
            await update.message.reply_text("РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РІРІРµРґРёС‚Рµ РєРѕСЂСЂРµРєС‚РЅРѕРµ РёРјСЏ РёРіСЂРѕРєР°.")
            return ADD_NAME
            
        context.user_data['name'] = update.message.text.strip()
        logger.info(f"Set name to: {context.user_data['name']}")
        logger.info(f"Sending position prompt, will return ADD_POSITION: {ADD_POSITION}")
        
        await update.message.reply_text("Р’РІРµРґРёС‚Рµ РїРѕР·РёС†РёСЋ (РЅР°РїР°РґР°СЋС‰РёР№/Р·Р°С‰РёС‚РЅРёРє/РІСЂР°С‚Р°СЂСЊ):")
        return ADD_POSITION
        
    except Exception as e:
        logger.error(f"Error in add_player_name: {str(e)}", exc_info=True)
        if update and update.message:
            await update.message.reply_text("РџСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ РёРјРµРЅРё РёРіСЂРѕРєР°. РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РїРѕРїСЂРѕР±СѓР№С‚Рµ РµС‰Рµ СЂР°Р·.")
        return ADD_NAME  # Р’РѕР·РІСЂР°С‰Р°РµРјСЃСЏ Рє РІРІРѕРґСѓ РёРјРµРЅРё

async def add_player_position(update, context):
    context.user_data['position'] = (update.message.text or '').strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РєР»СѓР±:")
    return ADD_CLUB

async def add_player_club(update, context):
    context.user_data['club'] = (update.message.text or '').strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РЅР°С†РёСЋ:")
    return ADD_NATION

async def add_player_nation(update, context):
    context.user_data['nation'] = (update.message.text or '').strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РІРѕР·СЂР°СЃС‚ (С‡РёСЃР»Рѕ):")
    return ADD_AGE

async def add_player_age(update, context):
    context.user_data['age'] = (update.message.text or '').strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ СЃС‚РѕРёРјРѕСЃС‚СЊ (HC, С‡РёСЃР»Рѕ):")
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
        await update.message.reply_text("РРіСЂРѕРє РґРѕР±Р°РІР»РµРЅ!")
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° РїСЂРё РґРѕР±Р°РІР»РµРЅРёРё: {e}")
    return ConversationHandler.END

async def add_player_cancel(update, context):
    await update.message.reply_text("Р”РѕР±Р°РІР»РµРЅРёРµ РѕС‚РјРµРЅРµРЅРѕ.")
    return ConversationHandler.END

# --- РЎРїРёСЃРѕРє / РїРѕРёСЃРє / СѓРґР°Р»РµРЅРёРµ РёРіСЂРѕРєРѕРІ ---
async def list_players(update, context):
    if not await admin_only(update, context):
        return
    try:
        players = db.get_all_players()
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ СЃРїРёСЃРєР° РёРіСЂРѕРєРѕРІ: {e}")
        return
    if not players:
        await update.message.reply_text("РЎРїРёСЃРѕРє РёРіСЂРѕРєРѕРІ РїСѓСЃС‚.")
        return
    msg = "\n".join([
        f"{p[0]}. {p[1]} | {p[2]} | {p[3]} | {p[4]} | {p[5]} Р»РµС‚ | {p[6]} HC" for p in players
    ])
    for i in range(0, len(msg), 3500):
        await update.message.reply_text(msg[i:i+3500])

async def find_player(update, context):
    if not await admin_only(update, context):
        return
    if not context.args or not str(context.args[0]).isdigit():
        await update.message.reply_text("РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ: /find_player <id>")
        return
    player_id = int(context.args[0])
    player = db.get_player_by_id(player_id)
    if not player:
        await update.message.reply_text("РРіСЂРѕРє РЅРµ РЅР°Р№РґРµРЅ.")
        return
    msg = f"{player[0]}. {player[1]} | {player[2]} | {player[3]} | {player[4]} | {player[5]} Р»РµС‚ | {player[6]} HC"
    await update.message.reply_text(msg)

async def remove_player(update, context):
    if not await admin_only(update, context):
        return
    if not context.args or not str(context.args[0]).isdigit():
        await update.message.reply_text("РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ: /remove_player <id>")
        return
    player_id = int(context.args[0])
    player = db.get_player_by_id(player_id)
    if not player:
        await update.message.reply_text("РРіСЂРѕРє РЅРµ РЅР°Р№РґРµРЅ.")
        return
    try:
        if db.remove_player(player_id):
            await update.message.reply_text(f"РРіСЂРѕРє {player[1]} (ID: {player_id}) СѓРґР°Р»РµРЅ.")
        else:
            await update.message.reply_text("РћС€РёР±РєР° РїСЂРё СѓРґР°Р»РµРЅРёРё РёРіСЂРѕРєР°.")
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° РїСЂРё СѓРґР°Р»РµРЅРёРё РёРіСЂРѕРєР°: {e}")

# --- Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ РёРіСЂРѕРєР° ---
async def edit_player_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    if not context.args or not str(context.args[0]).isdigit():
        await update.message.reply_text("РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ: /edit_player <id>")
        return ConversationHandler.END
    player_id = int(context.args[0])
    player = db.get_player_by_id(player_id)
    if not player:
        await update.message.reply_text("РРіСЂРѕРє РЅРµ РЅР°Р№РґРµРЅ.")
        return ConversationHandler.END
    context.user_data['edit_player_id'] = player_id
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РЅРѕРІРѕРµ РёРјСЏ Рё С„Р°РјРёР»РёСЋ РёРіСЂРѕРєР°:")
    return EDIT_NAME

async def edit_player_name(update, context):
    context.user_data['edit_name'] = (update.message.text or '').strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РЅРѕРІСѓСЋ РїРѕР·РёС†РёСЋ (РЅР°РїР°РґР°СЋС‰РёР№/Р·Р°С‰РёС‚РЅРёРє/РІСЂР°С‚Р°СЂСЊ):")
    return EDIT_POSITION

async def edit_player_position(update, context):
    context.user_data['edit_position'] = (update.message.text or '').strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РЅРѕРІС‹Р№ РєР»СѓР±:")
    return EDIT_CLUB

async def edit_player_club(update, context):
    context.user_data['edit_club'] = (update.message.text or '').strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РЅРѕРІСѓСЋ РЅР°С†РёСЋ:")
    return EDIT_NATION

async def edit_player_nation(update, context):
    context.user_data['edit_nation'] = (update.message.text or '').strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РЅРѕРІС‹Р№ РІРѕР·СЂР°СЃС‚ (С‡РёСЃР»Рѕ):")
    return EDIT_AGE

async def edit_player_age(update, context):
    context.user_data['edit_age'] = (update.message.text or '').strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РЅРѕРІСѓСЋ СЃС‚РѕРёРјРѕСЃС‚СЊ (HC, С‡РёСЃР»Рѕ):")
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
            await update.message.reply_text("РРіСЂРѕРє СѓСЃРїРµС€РЅРѕ РѕР±РЅРѕРІР»С‘РЅ!")
        else:
            await update.message.reply_text("РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ РёРіСЂРѕРєР°.")
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё: {e}")
    finally:
        for k in ('edit_player_id','edit_name','edit_position','edit_club','edit_nation','edit_age'):
            context.user_data.pop(k, None)
    return ConversationHandler.END

async def edit_player_cancel(update, context):
    await update.message.reply_text("Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ РѕС‚РјРµРЅРµРЅРѕ.")
    return ConversationHandler.END

# --- РўСѓСЂ: РґРѕР±Р°РІРёС‚СЊ Рё РІС‹РІРµСЃС‚Рё СЃРѕСЃС‚Р°РІ ---
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
        "РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РѕС‚РїСЂР°РІСЊС‚Рµ СЃРїРёСЃРѕРє РёРіСЂРѕРєРѕРІ РЅР° С‚СѓСЂ РІ С„РѕСЂРјР°С‚Рµ:\n50: 28, 1, ...\n40: ... Рё С‚.Рґ. (СЂРѕРІРЅРѕ 20 РёРіСЂРѕРєРѕРІ)"
    )
    return SET_TOUR_ROSTER_WAIT

async def set_tour_roster_process(update, context):
    text = update.message.text
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    ids = []
    try:
        for line in lines:
            if ':' not in line:
                await update.message.reply_text(f"РќРµРІРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚ СЃС‚СЂРѕРєРё: {line}")
                return ConversationHandler.END
            cost_str, ids_str = line.split(':', 1)
            cost = int(cost_str.strip())
            id_list = [int(x.strip()) for x in ids_str.split(',') if x.strip()]
            for player_id in id_list:
                ids.append((cost, player_id))
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СЂР°Р·Р±РѕСЂР°: {e}")
        return ConversationHandler.END
    if len(ids) != 20:
        await update.message.reply_text(f"РћС€РёР±РєР°: РґРѕР»Р¶РЅРѕ Р±С‹С‚СЊ СЂРѕРІРЅРѕ 20 РёРіСЂРѕРєРѕРІ, Р° РЅРµ {len(ids)}")
        return ConversationHandler.END
    # РџСЂРѕРІРµСЂРєР°, С‡С‚Рѕ РІСЃРµ РёРіСЂРѕРєРё СЃСѓС‰РµСЃС‚РІСѓСЋС‚
    for cost, player_id in ids:
        player = db.get_player_by_id(player_id)
        if not player:
            await update.message.reply_text(f"РРіСЂРѕРє СЃ id {player_id} РЅРµ РЅР°Р№РґРµРЅ!")
            return ConversationHandler.END
    db.clear_tour_roster()
    for cost, player_id in ids:
        db.add_tour_roster_entry(player_id, cost)
    await update.message.reply_text("РЎРѕСЃС‚Р°РІ РЅР° С‚СѓСЂ СѓСЃРїРµС€РЅРѕ СЃРѕС…СЂР°РЅС‘РЅ!")
    return ConversationHandler.END

async def get_tour_roster(update, context):
    if not await admin_only(update, context):
        return
    roster = db.get_tour_roster_with_player_info()
    if not roster:
        await update.message.reply_text("РЎРѕСЃС‚Р°РІ РЅР° С‚СѓСЂ РЅРµ Р·Р°РґР°РЅ.")
        return
    msg = "РЎРѕСЃС‚Р°РІ РЅР° С‚СѓСЂ:\n"
    for cost, pid, name, pos, club, nation, age, price in roster:
        msg += f"{cost}: {pid}. {name} | {pos} | {club} | {nation} | {age} Р»РµС‚ | {price} HC\n"
    await update.message.reply_text(msg)

# --- РЎРїРёСЃРѕРє РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ Рё РїРѕРґРїРёСЃРѕРє ---
async def show_users(update, context):
    if not await admin_only(update, context):
        return
    import datetime
    # РџРѕР»СѓС‡Р°РµРј РІСЃРµС… РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ Рё РёС… РїРѕРґРїРёСЃРєРё
    with db.closing(db.sqlite3.connect(db.DB_NAME)) as conn:
        users = conn.execute('SELECT telegram_id, username, name, hc_balance FROM users').fetchall()
        subs = {row[0]: row[1] for row in conn.execute('SELECT user_id, paid_until FROM subscriptions').fetchall()}
    now = datetime.datetime.utcnow()
    lines = []
    for user_id, username, name, hc_balance in users:
        paid_until = subs.get(user_id)
        active = False
        if paid_until:
            try:
                dt = datetime.datetime.fromisoformat(str(paid_until))
                active = dt > now
            except Exception:
                active = False
        status = 'вњ… РїРѕРґРїРёСЃРєР° Р°РєС‚РёРІРЅР°' if active else 'вќЊ РЅРµС‚ РїРѕРґРїРёСЃРєРё'
        lines.append(f"{user_id} | {username or '-'} | {name or '-'} | {status} | HC: {hc_balance if hc_balance is not None else 0}")
    if not lines:
        await update.message.reply_text("РќРµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№.")
    else:
        msg = 'РџРѕР»СЊР·РѕРІР°С‚РµР»Рё Рё РїРѕРґРїРёСЃРєРё:\n\n' + '\n'.join(lines)
        for i in range(0, len(msg), 4000):
            await update.message.reply_text(msg[i:i+4000])

# --- Р§РµР»Р»РµРЅРґР¶: РІС‹РІРѕРґ СЃРѕСЃС‚Р°РІРѕРІ РїРѕ id ---
async def challenge_rosters_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """РђРґРјРёРЅ-РєРѕРјР°РЅРґР°: /challenge_rosters <challenge_id>
    РџРѕРєР°Р·С‹РІР°РµС‚ СЃРїРёСЃРѕРє РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№, РёС… СЃС‚Р°С‚СѓСЃ Р·Р°СЏРІРєРё, СЃС‚Р°РІРєСѓ Рё РІС‹Р±СЂР°РЅРЅС‹С… РёРіСЂРѕРєРѕРІ (РЅР°РїР°РґР°СЋС‰РёР№/Р·Р°С‰РёС‚РЅРёРє/РІСЂР°С‚Р°СЂСЊ).
    """
    if not await admin_only(update, context):
        return
    # Р Р°Р·Р±РѕСЂ Р°СЂРіСѓРјРµРЅС‚Р°
    challenge_id = None
    try:
        if context.args and len(context.args) >= 1:
            challenge_id = int(context.args[0])
    except Exception:
        challenge_id = None
    if not challenge_id:
        await update.message.reply_text("РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ: /challenge_rosters <challenge_id>")
        return

    # РџРѕР»СѓС‡Р°РµРј Р·Р°РїРёСЃРё Р·Р°СЏРІРѕРє СЃ СЋР·РµСЂР°РјРё
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
        await update.message.reply_text(f"РћС€РёР±РєР° Р‘Р”: {e}")
        return

    if not rows:
        await update.message.reply_text(f"Р”Р»СЏ С‡РµР»Р»РµРЅРґР¶Р° #{challenge_id} Р·Р°СЏРІРєРё РЅРµ РЅР°Р№РґРµРЅС‹.")
        return

    def name_club(pid):
        if not pid:
            return "вЂ”"
        try:
            p = db.get_player_by_id(int(pid))
            if p:
                return f"{p[1]} ({p[3]})"
        except Exception:
            pass
        return str(pid)

    # Р¤РѕСЂРјРёСЂСѓРµРј СЃРѕРѕР±С‰РµРЅРёРµ СЃ СЂР°Р·Р±РёРµРЅРёРµРј РЅР° С‡Р°СЃС‚Рё
    parts = []
    cur_lines = [f"РЎРѕСЃС‚Р°РІС‹ СѓС‡Р°СЃС‚РЅРёРєРѕРІ С‡РµР»Р»РµРЅРґР¶Р° #{challenge_id}:", ""]
    for r in rows:
        uname = ("@" + (r["username"] or "").strip()) if r["username"] else "вЂ”"
        name = r["name"] or "вЂ”"
        status = (r["status"] or "").lower()
        stake = r["stake"] or 0
        fwd = name_club(r["forward_id"]) if r["forward_id"] else "вЂ”"
        dfd = name_club(r["defender_id"]) if r["defender_id"] else "вЂ”"
        gk = name_club(r["goalie_id"]) if r["goalie_id"] else "вЂ”"

        # РЎС‚Р°С‚СѓСЃ Р·РЅР°С‡РєРѕРј
        status_icon = {
            'in_progress': 'рџџЎ in_progress',
            'completed': 'рџџў completed',
            'canceled': 'вљЄ canceled',
            'refunded': 'вљЄ refunded',
        }.get(status, status or 'вЂ”')

        cur_lines.append(f"вЂў {uname} | {name} | {status_icon} | РЎС‚Р°РІРєР°: {stake} HC")
        cur_lines.append(f"РќР°РїР°РґР°СЋС‰РёР№: {fwd}")
        cur_lines.append(f"Р—Р°С‰РёС‚РЅРёРє: {dfd}")
        cur_lines.append(f"Р’СЂР°С‚Р°СЂСЊ: {gk}")
        cur_lines.append("")

        joined = "\n".join(cur_lines)
        if len(joined) > 3500:  # Р·Р°РїР°СЃ РґРѕ Р»РёРјРёС‚Р° Telegram РІ 4096
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
        await update.message.reply_text('РќРµС‚ РґРѕСЃС‚СѓРїР°')
        return False
    return True

async def send_tour_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    РЎС†РµРЅР°СЂРёР№:
    1. РђРґРјРёРЅ РѕС‚РїСЂР°РІР»СЏРµС‚ /send_tour_image вЂ” Р±РѕС‚ РїСЂРѕСЃРёС‚ РїСЂРёРєСЂРµРїРёС‚СЊ РєР°СЂС‚РёРЅРєСѓ.
    2. РђРґРјРёРЅ РѕС‚РїСЂР°РІР»СЏРµС‚ С„РѕС‚Рѕ вЂ” Р±РѕС‚ СЃРѕС…СЂР°РЅСЏРµС‚, СЃРѕРѕР±С‰Р°РµС‚ РѕР± СѓСЃРїРµС…Рµ.
    """
    if not await admin_only(update, context):
        logger.info(f"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ {update.effective_user.id} РЅРµ Р°РґРјРёРЅ, РґРѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ.")
        return

    # Р•СЃР»Рё РєРѕРјР°РЅРґР° РІС‹Р·РІР°РЅР° Р±РµР· С„РѕС‚Рѕ, Р·Р°РїСЂР°С€РёРІР°РµРј С„РѕС‚Рѕ


    if not update.message.photo:
        context.user_data['awaiting_tour_image'] = True
        chat_id = update.effective_chat.id
        debug_info = f"[DEBUG] /send_tour_image chat_id: {chat_id}, user_data: {context.user_data}"
        await update.message.reply_text('РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РїСЂРёРєСЂРµРїРёС‚Рµ РєР°СЂС‚РёРЅРєСѓ СЃР»РµРґСѓСЋС‰РёРј СЃРѕРѕР±С‰РµРЅРёРµРј.')
        await update.message.reply_text(debug_info)
        logger.info(f"[DEBUG] РћР¶РёРґР°РЅРёРµ РєР°СЂС‚РёРЅРєРё РѕС‚ Р°РґРјРёРЅР° {update.effective_user.id}, user_data: {context.user_data}")
        return

    # Р•СЃР»Рё С„РѕС‚Рѕ РїСЂРёС€Р»Рѕ РїРѕСЃР»Рµ Р·Р°РїСЂРѕСЃР°


    if context.user_data.get('awaiting_tour_image'):
        logger.info(f"[DEBUG] РџРѕР»СѓС‡РµРЅРѕ С„РѕС‚Рѕ, user_data: {context.user_data}")
        try:
            photo = update.message.photo[-1]
            file = await photo.get_file()
            filename = f"tour_{photo.file_unique_id}.jpg"
            path = os.path.join(IMAGES_DIR, filename)
            await file.download_to_drive(path)
            with open(TOUR_IMAGE_PATH_FILE, 'w') as f:
                f.write(filename)
            context.user_data['awaiting_tour_image'] = False
            await update.message.reply_text(f'вњ… РљР°СЂС‚РёРЅРєР° РїСЂРёРЅСЏС‚Р° Рё СЃРѕС…СЂР°РЅРµРЅР° РєР°Рє `{filename}`. РћРЅР° Р±СѓРґРµС‚ СЂР°Р·РѕСЃР»Р°РЅР° РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј РїСЂРё РєРѕРјР°РЅРґРµ /tour.')
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f'[DEBUG] Р¤РѕС‚Рѕ РѕР±СЂР°Р±РѕС‚Р°РЅРѕ, СЃРѕС…СЂР°РЅРµРЅРѕ РєР°Рє {filename}')
            logger.info(f"РљР°СЂС‚РёРЅРєР° С‚СѓСЂР° СЃРѕС…СЂР°РЅРµРЅР°: {path} (РѕС‚ {update.effective_user.id})")
        except Exception as e:
            logger.error(f'РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РєР°СЂС‚РёРЅРєРё С‚СѓСЂР°: {e}')
            await update.message.reply_text(f'РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РєР°СЂС‚РёРЅРєРё: {e}')
        return

    # Р•СЃР»Рё С„РѕС‚Рѕ РїСЂРёС€Р»Рѕ Р±РµР· Р·Р°РїСЂРѕСЃР°
    await update.message.reply_text('РЎРЅР°С‡Р°Р»Р° РѕС‚РїСЂР°РІСЊС‚Рµ РєРѕРјР°РЅРґСѓ /send_tour_image, Р·Р°С‚РµРј С„РѕС‚Рѕ.')
    logger.info(f"Р¤РѕС‚Рѕ РїРѕР»СѓС‡РµРЅРѕ Р±РµР· Р·Р°РїСЂРѕСЃР° РѕС‚ {update.effective_user.id}")

async def process_tour_image_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        filename = f"tour_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        await file.download_to_drive(path)
        with open(TOUR_IMAGE_PATH_FILE, 'w') as f:
            f.write(filename)
        await update.message.reply_text(f'вњ… РљР°СЂС‚РёРЅРєР° РїСЂРёРЅСЏС‚Р° Рё СЃРѕС…СЂР°РЅРµРЅР° РєР°Рє `{filename}`. РћРЅР° Р±СѓРґРµС‚ СЂР°Р·РѕСЃР»Р°РЅР° РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј РїСЂРё РєРѕРјР°РЅРґРµ /tour.')
        logger.info(f"РљР°СЂС‚РёРЅРєР° С‚СѓСЂР° СЃРѕС…СЂР°РЅРµРЅР°: {path} (РѕС‚ {update.effective_user.id})")
    except Exception as e:
        logger.error(f'РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РєР°СЂС‚РёРЅРєРё С‚СѓСЂР°: {e}')
        await update.message.reply_text(f'РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РєР°СЂС‚РёРЅРєРё: {e}')

async def addhc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_only(update, context):
        return
    if len(context.args) != 2 or not context.args[1].isdigit():
        await update.message.reply_text('РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ: /addhc @username 100')
        return
    username = context.args[0].lstrip('@')
    amount = int(context.args[1])
    user = db.get_user_by_username(username)
    if not user:
        await update.message.reply_text('РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ.')
        return
    db.update_hc_balance(user[0], amount)
    new_balance = db.get_user_by_id(user[0])[3]
    await context.bot.send_message(chat_id=user[0], text=f'рџЋ‰ РўРµР±Рµ РЅР°С‡РёСЃР»РµРЅРѕ {amount} HC!\nрџ’° РќРѕРІС‹Р№ Р±Р°Р»Р°РЅСЃ: {new_balance} HC')
    await update.message.reply_text(f'РџРѕР»СЊР·РѕРІР°С‚РµР»СЋ @{username} РЅР°С‡РёСЃР»РµРЅРѕ {amount} HC.')

# --- Р РµРіРёСЃС‚СЂР°С†РёСЏ С‡РµР»Р»РµРЅРґР¶Р° (+ Р·Р°РіСЂСѓР·РєР° РєР°СЂС‚РёРЅРєРё) ---
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
        'РЎРѕР·РґР°РЅРёРµ С‡РµР»Р»РµРЅРґР¶Р°. Р’РІРµРґРёС‚Рµ РґР°С‚Сѓ РЎРўРђР РўРђ РІ С„РѕСЂРјР°С‚Рµ ISO, РЅР°РїСЂРёРјРµСЂ: 2025-08-08T12:00:00'
    )
    return CHALLENGE_START

async def challenge_input_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    dt = _parse_iso(text)
    if not dt:
        await update.message.reply_text('РќРµРєРѕСЂСЂРµРєС‚РЅР°СЏ РґР°С‚Р°. РџРѕРІС‚РѕСЂРёС‚Рµ РІ С„РѕСЂРјР°С‚Рµ ISO: 2025-08-08T12:00:00')
        return CHALLENGE_START
    context.user_data['challenge_start'] = text
    await update.message.reply_text('Р’РІРµРґРёС‚Рµ Р”Р•Р”Р›РђР™Рќ (РєСЂР°Р№РЅРёР№ СЃСЂРѕРє РІС‹Р±РѕСЂР° СЃРѕСЃС‚Р°РІР°) РІ С„РѕСЂРјР°С‚Рµ ISO: 2025-08-09T18:00:00')
    return CHALLENGE_DEADLINE

async def challenge_input_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    dt = _parse_iso(text)
    if not dt:
        await update.message.reply_text('РќРµРєРѕСЂСЂРµРєС‚РЅР°СЏ РґР°С‚Р°. РџРѕРІС‚РѕСЂРёС‚Рµ РґРµРґР»Р°Р№РЅ РІ С„РѕСЂРјР°С‚Рµ ISO.')
        return CHALLENGE_DEADLINE
    # РџСЂРѕРІРµСЂРёРј РїРѕСЂСЏРґРѕРє
    sd = _parse_iso(context.user_data.get('challenge_start', ''))
    if not sd or not (sd < dt):
        await update.message.reply_text('Р”РµРґР»Р°Р№РЅ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РџРћРЎР›Р• РґР°С‚С‹ СЃС‚Р°СЂС‚Р°. РџРѕРІС‚РѕСЂРёС‚Рµ РІРІРѕРґ РґРµРґР»Р°Р№РЅР°.')
        return CHALLENGE_DEADLINE
    context.user_data['challenge_deadline'] = text
    await update.message.reply_text('Р’РІРµРґРёС‚Рµ Р”РђРўРЈ РћРљРћРќР§РђРќРРЇ РёРіСЂС‹ РІ С„РѕСЂРјР°С‚Рµ ISO: 2025-08-12T23:59:59')
    return CHALLENGE_END

async def challenge_input_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    dt = _parse_iso(text)
    if not dt:
        await update.message.reply_text('РќРµРєРѕСЂСЂРµРєС‚РЅР°СЏ РґР°С‚Р°. РџРѕРІС‚РѕСЂРёС‚Рµ РґР°С‚Сѓ РѕРєРѕРЅС‡Р°РЅРёСЏ РІ С„РѕСЂРјР°С‚Рµ ISO.')
        return CHALLENGE_END
    sd = _parse_iso(context.user_data.get('challenge_start', ''))
    dl = _parse_iso(context.user_data.get('challenge_deadline', ''))
    if not sd or not dl or not (dl < dt):
        await update.message.reply_text('Р”Р°С‚Р° РѕРєРѕРЅС‡Р°РЅРёСЏ РґРѕР»Р¶РЅР° Р±С‹С‚СЊ РџРћРЎР›Р• РґРµРґР»Р°Р№РЅР°. РџРѕРІС‚РѕСЂРёС‚Рµ РґР°С‚Сѓ РѕРєРѕРЅС‡Р°РЅРёСЏ.')
        return CHALLENGE_END
    context.user_data['challenge_end'] = text
    await update.message.reply_text('РўРµРїРµСЂСЊ РїСЂРёС€Р»РёС‚Рµ РљРђР РўРРќРљРЈ С‡РµР»Р»РµРЅРґР¶Р° СЃРѕРѕР±С‰РµРЅРёРµРј РІ С‡Р°С‚.')
    return CHALLENGE_WAIT_IMAGE

async def send_challenge_image_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # РЎРѕС…СЂР°РЅСЏРµРј С„РѕС‚Рѕ
        photo = update.message.photo[-1]
        file = await photo.get_file()
        filename = f"challenge_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        await file.download_to_drive(path)
        with open(CHALLENGE_IMAGE_PATH_FILE, 'w') as f:
            f.write(filename)

        # Р РµРіРёСЃС‚СЂРёСЂСѓРµРј С‡РµР»Р»РµРЅРґР¶ РІ Р‘Р”
        start_date = context.user_data.get('challenge_start')
        deadline = context.user_data.get('challenge_deadline')
        end_date = context.user_data.get('challenge_end')
        image_file_id = getattr(photo, 'file_id', '') or ''
        ch_id = db.create_challenge(start_date, deadline, end_date, filename, image_file_id)

        await update.message.reply_text(
            f'вњ… Р§РµР»Р»РµРЅРґР¶ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅ (id={ch_id}). РљР°СЂС‚РёРЅРєР° СЃРѕС…СЂР°РЅРµРЅР° РєР°Рє `{filename}`.'
        )
        logger.info(f"Р§РµР»Р»РµРЅРґР¶ {ch_id} СЃРѕР·РґР°РЅ: {start_date} / {deadline} / {end_date}, image={path}")
    except Exception as e:
        logger.error(f'РћС€РёР±РєР° РїСЂРё СЂРµРіРёСЃС‚СЂР°С†РёРё С‡РµР»Р»РµРЅРґР¶Р°: {e}')
        await update.message.reply_text(f'РћС€РёР±РєР° РїСЂРё СЂРµРіРёСЃС‚СЂР°С†РёРё С‡РµР»Р»РµРЅРґР¶Р°: {e}')
    finally:
        # РћС‡РёСЃС‚РёРј РІСЂРµРјРµРЅРЅС‹Рµ РґР°РЅРЅС‹Рµ
        for k in ('challenge_start','challenge_deadline','challenge_end'):
            context.user_data.pop(k, None)
    return ConversationHandler.END

# --- РњР°РіР°Р·РёРЅ: РѕРїРёСЃР°РЅРёРµ + РєР°СЂС‚РёРЅРєР° ---
SHOP_TEXT_WAIT = 41
SHOP_IMAGE_WAIT = 42

async def add_image_shop_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text(
        "РќР°РїРёС€РёС‚Рµ С‚РµРєСЃС‚ РѕРїРёСЃР°РЅРёСЏ РјР°РіР°Р·РёРЅР°. РњРѕР¶РµС‚Рµ РѕС„РѕСЂРјРёС‚СЊ Р°РєРєСѓСЂР°С‚РЅРѕ (РѕР±С‹С‡РЅС‹Р№ С‚РµРєСЃС‚)."
    )
    return SHOP_TEXT_WAIT

async def add_image_shop_text(update, context):
    text = (update.message.text or '').strip()
    try:
        db.update_shop_text(text)
    except Exception:
        pass
    await update.message.reply_text("РўРµРїРµСЂСЊ РѕС‚РїСЂР°РІСЊС‚Рµ РєР°СЂС‚РёРЅРєСѓ РјР°РіР°Р·РёРЅР° РѕРґРЅРёРј С„РѕС‚Рѕ СЃРѕРѕР±С‰РµРЅРёРµРј.")
    return SHOP_IMAGE_WAIT

async def add_image_shop_photo(update, context):
    if not update.message.photo:
        await update.message.reply_text("РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РѕС‚РїСЂР°РІСЊС‚Рµ РѕРґРЅРѕ С„РѕС‚Рѕ.")
        return SHOP_IMAGE_WAIT
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        filename = f"shop_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        await file.download_to_drive(path)
        # РЎРѕС…СЂР°РЅРёРј file_id РґР»СЏ Р±С‹СЃС‚СЂРѕРіРѕ РїРѕРІС‚РѕСЂРЅРѕРіРѕ РѕС‚РїСЂР°РІР»РµРЅРёСЏ
        db.update_shop_image(filename, photo.file_id)
        await update.message.reply_text("Р“РѕС‚РѕРІРѕ. РњР°РіР°Р·РёРЅ РѕР±РЅРѕРІР»С‘РЅ.")
        logger.info(f"РњР°РіР°Р·РёРЅ РѕР±РЅРѕРІР»С‘РЅ: text set, image {filename}")
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РєР°СЂС‚РёРЅРєРё РјР°РіР°Р·РёРЅР°: {e}")
        await update.message.reply_text(f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РєР°СЂС‚РёРЅРєРё: {e}")
    return ConversationHandler.END

async def send_challenge_image_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text('РћС‚РјРµРЅРµРЅРѕ.')
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
        success, failed = await send_message_to_users(context.bot, users, photo_path=path, caption='рџ“Љ Р РµР·СѓР»СЊС‚Р°С‚С‹ С‚СѓСЂР°:')
        await update.message.reply_text(f'Р РµР·СѓР»СЊС‚Р°С‚С‹ (С„РѕС‚Рѕ) СЂР°Р·РѕСЃР»Р°РЅС‹. РЈСЃРїРµС€РЅРѕ: {success}, РѕС€РёР±РєРё: {failed}')
    elif context.args:
        text = ' '.join(context.args)
        success, failed = await send_message_to_users(context.bot, users, text=f'рџ“Љ Р РµР·СѓР»СЊС‚Р°С‚С‹ С‚СѓСЂР°:\n{text}')
        await update.message.reply_text(f'Р РµР·СѓР»СЊС‚Р°С‚С‹ (С‚РµРєСЃС‚) СЂР°Р·РѕСЃР»Р°РЅС‹. РЈСЃРїРµС€РЅРѕ: {success}, РѕС€РёР±РєРё: {failed}')
    else:
        await update.message.reply_text('РџСЂРёС€Р»РёС‚Рµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ РёР»Рё С‚РµРєСЃС‚ РїРѕСЃР»Рµ РєРѕРјР°РЅРґС‹.')

# --- РЈРїСЂР°РІР»РµРЅРёРµ С‡РµР»Р»РµРЅРґР¶Р°РјРё (СЃРїРёСЃРѕРє/СѓРґР°Р»РµРЅРёРµ) ---
async def list_challenges(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_only(update, context):
        return
    try:
        rows = db.get_all_challenges()
        if not rows:
            await update.message.reply_text('Р’ Р±Р°Р·Рµ РЅРµС‚ С‡РµР»Р»РµРЅРґР¶РµР№.')
            return
        lines = []
        for r in rows:
            # РѕР¶РёРґР°РµРјС‹Рµ РїРѕР»СЏ: id, start_date, deadline, end_date, image_filename, status[, image_file_id]
            ch_id = r[0]
            start_date = r[1]
            deadline = r[2]
            end_date = r[3]
            image_filename = r[4] if len(r) > 4 else ''
            status = r[5] if len(r) > 5 else ''
            lines.append(
                f"id={ch_id} | {status}\nstart: {start_date}\ndeadline: {deadline}\nend: {end_date}\nimage: {image_filename}\nвЂ”"
            )
        msg = "\n".join(lines)
        # Telegram РѕРіСЂР°РЅРёС‡РµРЅРёРµ РЅР° РґР»РёРЅСѓ СЃРѕРѕР±С‰РµРЅРёСЏ ~4096
        for i in range(0, len(msg), 3500):
            await update.message.reply_text(msg[i:i+3500])
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ СЃРїРёСЃРєР° С‡РµР»Р»РµРЅРґР¶РµР№: {e}")

async def delete_challenge_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_only(update, context):
        return
    args = getattr(context, 'args', []) or []
    if not args or not args[0].isdigit():
        await update.message.reply_text('РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ: /delete_challenge <id>')
        return
    ch_id = int(args[0])
    try:
        deleted = db.delete_challenge(ch_id)
        if deleted:
            await update.message.reply_text(f'Р§РµР»Р»РµРЅРґР¶ id={ch_id} СѓРґР°Р»С‘РЅ.')
        else:
            await update.message.reply_text(f'Р§РµР»Р»РµРЅРґР¶ id={ch_id} РЅРµ РЅР°Р№РґРµРЅ.')
    except Exception as e:
        await update.message.reply_text(f'РћС€РёР±РєР° СѓРґР°Р»РµРЅРёСЏ С‡РµР»Р»РµРЅРґР¶Р°: {e}')

# --- РЈРїСЂР°РІР»РµРЅРёРµ С‚СѓСЂР°РјРё (admin) ---
from telegram.ext import CommandHandler, MessageHandler, filters, ConversationHandler
import json

TOUR_NAME, TOUR_START, TOUR_DEADLINE, TOUR_END, TOUR_CONFIRM = range(100, 105)

# --- Р•Р”РРќР«Р™ РџРђРљР•РўРќР«Р™ Р”РРђР›РћР“ РЎРћР—Р”РђРќРРЇ РўРЈР Рђ ---
# Р­С‚Р°РїС‹: РёРјСЏ -> РґР°С‚Р° СЃС‚Р°СЂС‚Р° -> РґРµРґР»Р°Р№РЅ -> РѕРєРѕРЅС‡Р°РЅРёРµ -> С„РѕС‚Рѕ -> СЂРѕСЃС‚РµСЂ -> С„РёРЅР°Р»
CT_NAME, CT_START, CT_DEADLINE, CT_END, CT_IMAGE, CT_ROSTER = range(200, 206)

async def create_tour_full_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    # РћС‡РёСЃС‚РёРј РІСЂРµРјРµРЅРЅС‹Рµ РґР°РЅРЅС‹Рµ РґРёР°Р»РѕРіР°
    for k in ['ct_name', 'ct_start', 'ct_deadline', 'ct_end', 'ct_image_filename', 'ct_tour_id']:
        context.user_data.pop(k, None)
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РЅР°Р·РІР°РЅРёРµ С‚СѓСЂР°:")
    return CT_NAME

async def create_tour_full_name(update, context):
    context.user_data['ct_name'] = (update.message.text or '').strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РґР°С‚Сѓ СЃС‚Р°СЂС‚Р° С‚СѓСЂР° (РґРґ.РјРј.РіРі):")
    return CT_START

async def create_tour_full_start_date(update, context):
    context.user_data['ct_start'] = (update.message.text or '').strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РґРµРґР»Р°Р№РЅ (РґРґ.РјРј.РіРі С‡С‡:РјРј):")
    return CT_DEADLINE

async def create_tour_full_deadline(update, context):
    context.user_data['ct_deadline'] = (update.message.text or '').strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РґР°С‚Сѓ РѕРєРѕРЅС‡Р°РЅРёСЏ С‚СѓСЂР° (РґРґ.РјРј.РіРі):")
    return CT_END

async def create_tour_full_end_date(update, context):
    context.user_data['ct_end'] = (update.message.text or '').strip()
    # РЎРѕР·РґР°С‘Рј С‚СѓСЂ СЃСЂР°Р·Сѓ, С‡С‚РѕР±С‹ РїРѕР»СѓС‡РёС‚СЊ id (Р°РІС‚РѕРёРЅРєСЂРµРјРµРЅС‚)
    try:
        tour_id = db.create_tour(
            context.user_data['ct_name'],
            context.user_data['ct_start'],
            context.user_data['ct_deadline'],
            context.user_data['ct_end']
        )
        context.user_data['ct_tour_id'] = tour_id
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ С‚СѓСЂР°: {e}")
        return ConversationHandler.END
    await update.message.reply_text("РўРµРїРµСЂСЊ РѕС‚РїСЂР°РІСЊС‚Рµ РѕРґРЅРѕ С„РѕС‚Рѕ РґР»СЏ С‚СѓСЂР° СЃРѕРѕР±С‰РµРЅРёРµРј СЃ С„РѕС‚РѕРіСЂР°С„РёРµР№.")
    return CT_IMAGE

async def create_tour_full_photo(update, context):
    if not update.message or not update.message.photo:
        await update.message.reply_text("РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РѕС‚РїСЂР°РІСЊС‚Рµ РёРјРµРЅРЅРѕ С„РѕС‚Рѕ.")
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
        # РЎРѕС…СЂР°РЅРёРј "РїРѕСЃР»РµРґРЅСЋСЋ" РєР°СЂС‚РёРЅРєСѓ РґР»СЏ РїРѕРєР°Р·Р° РІ /tour
        try:
            with open(TOUR_IMAGE_PATH_FILE, 'w') as f:
                f.write(filename)
        except Exception:
            logger.warning("Failed to write TOUR_IMAGE_PATH_FILE", exc_info=True)
        context.user_data['ct_image_filename'] = filename
        # РџСЂРёРІСЏР¶РµРј РёР·РѕР±СЂР°Р¶РµРЅРёРµ Рє СЃРѕР·РґР°РЅРЅРѕРјСѓ С‚СѓСЂСѓ
        try:
            tour_id = context.user_data.get('ct_tour_id')
            if tour_id:
                db.update_tour_image(tour_id, filename, photo.file_id)
        except Exception:
            logger.warning("Failed to update tour image in DB", exc_info=True)
        await update.message.reply_text(
            "Р¤РѕС‚Рѕ СЃРѕС…СЂР°РЅРµРЅРѕ. РўРµРїРµСЂСЊ РѕС‚РїСЂР°РІСЊС‚Рµ СЂРѕСЃС‚РµСЂ РІ С„РѕСЂРјР°С‚Рµ:\n"
            "50: 28, 1, ...\n40: ... Рё С‚.Рґ. (СЂРѕРІРЅРѕ 20 РёРіСЂРѕРєРѕРІ)"
        )
        return CT_ROSTER
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СЃРѕС…СЂР°РЅРµРЅРёСЏ С„РѕС‚Рѕ: {e}")
        return ConversationHandler.END

async def create_tour_full_roster(update, context):
    text = (update.message.text or '').strip()
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    pairs = []
    try:
        for line in lines:
            if ':' not in line:
                await update.message.reply_text(f"РќРµРІРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚ СЃС‚СЂРѕРєРё: {line}")
                return CT_ROSTER
            cost_str, ids_str = line.split(':', 1)
            cost = int(cost_str.strip())
            id_list = [int(x.strip()) for x in ids_str.split(',') if x.strip()]
            for pid in id_list:
                pairs.append((cost, pid))
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СЂР°Р·Р±РѕСЂР°: {e}")
        return CT_ROSTER
    if len(pairs) != 20:
        await update.message.reply_text(f"РћС€РёР±РєР°: РґРѕР»Р¶РЅРѕ Р±С‹С‚СЊ СЂРѕРІРЅРѕ 20 РёРіСЂРѕРєРѕРІ, Р° РЅРµ {len(pairs)}. РџРѕРІС‚РѕСЂРёС‚Рµ РІРІРѕРґ.")
        return CT_ROSTER
    # РџСЂРѕРІРµСЂРёРј, С‡С‚Рѕ РёРіСЂРѕРєРё СЃСѓС‰РµСЃС‚РІСѓСЋС‚
    for cost, pid in pairs:
        player = db.get_player_by_id(pid)
        if not player:
            await update.message.reply_text(f"РРіСЂРѕРє СЃ id {pid} РЅРµ РЅР°Р№РґРµРЅ! РџРѕРІС‚РѕСЂРёС‚Рµ РІРІРѕРґ.")
            return CT_ROSTER
    # РЎРѕС…СЂР°РЅСЏРµРј СЂРѕСЃС‚РµСЂ РЅР° РєРѕРЅРєСЂРµС‚РЅС‹Р№ С‚СѓСЂ РІ С‚Р°Р±Р»РёС†Сѓ tour_players
    try:
        tour_id = context.user_data.get('ct_tour_id')
        if tour_id:
            db.clear_tour_players(tour_id)
            for cost, pid in pairs:
                db.add_tour_player(tour_id, pid, cost)
            # РћР±СЂР°С‚РЅР°СЏ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚СЊ: С‚Р°РєР¶Рµ Р·Р°РїРѕР»РЅРёРј СЃС‚Р°СЂСѓСЋ С‚Р°Р±Р»РёС†Сѓ tour_roster,
            # С‚.Рє. С‚РµРєСѓС‰Р°СЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЊСЃРєР°СЏ Р»РѕРіРёРєР° С‡РёС‚Р°РµС‚ РµС‘.
            try:
                db.clear_tour_roster()
                for cost, pid in pairs:
                    db.add_tour_roster_entry(pid, cost)
            except Exception:
                logger.warning("Failed to mirror roster into legacy tour_roster", exc_info=True)
        else:
            await update.message.reply_text("Р’РЅСѓС‚СЂРµРЅРЅСЏСЏ РѕС€РёР±РєР°: tour_id РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚.")
            return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СЃРѕС…СЂР°РЅРµРЅРёСЏ СЂРѕСЃС‚РµСЂР°: {e}")
        return ConversationHandler.END
    tour_id = context.user_data.get('ct_tour_id')
    name = context.user_data.get('ct_name')
    start = context.user_data.get('ct_start')
    deadline = context.user_data.get('ct_deadline')
    end = context.user_data.get('ct_end')
    await update.message.reply_text(
        "РўСѓСЂ СЃРѕР·РґР°РЅ СѓСЃРїРµС€РЅРѕ!\n"
        f"ID: {tour_id}\nРќР°Р·РІР°РЅРёРµ: {name}\nРЎС‚Р°СЂС‚: {start}\nР”РµРґР»Р°Р№РЅ: {deadline}\nРћРєРѕРЅС‡Р°РЅРёРµ: {end}\n"
        f"РљР°СЂС‚РёРЅРєР°: {context.user_data.get('ct_image_filename', '-')}. Р РѕСЃС‚РµСЂ РїСЂРёРЅСЏС‚."
    )
    # РћС‡РёСЃС‚РёРј РІСЂРµРјРµРЅРЅС‹Рµ РґР°РЅРЅС‹Рµ
    for k in ['ct_name', 'ct_start', 'ct_deadline', 'ct_end', 'ct_image_filename', 'ct_tour_id']:
        context.user_data.pop(k, None)
    return ConversationHandler.END

async def create_tour_full_cancel(update, context):
    await update.message.reply_text("РЎРѕР·РґР°РЅРёРµ С‚СѓСЂР° РѕС‚РјРµРЅРµРЅРѕ.")
    # РћС‡РёСЃС‚РёРј РІСЂРµРјРµРЅРЅС‹Рµ РґР°РЅРЅС‹Рµ
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
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РЅР°Р·РІР°РЅРёРµ С‚СѓСЂР°:")
    return TOUR_NAME

async def create_tour_name(update, context):
    context.user_data['tour_name'] = update.message.text.strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РґР°С‚Сѓ СЃС‚Р°СЂС‚Р° С‚СѓСЂР° (РґРґ.РјРј.РіРі):")
    return TOUR_START

async def create_tour_start_date(update, context):
    context.user_data['tour_start'] = update.message.text.strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РґРµРґР»Р°Р№РЅ (РґРґ.РјРј.РіРі С‡С‡:РјРј):")
    return TOUR_DEADLINE

async def create_tour_deadline(update, context):
    context.user_data['tour_deadline'] = update.message.text.strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РґР°С‚Сѓ РѕРєРѕРЅС‡Р°РЅРёСЏ С‚СѓСЂР° (РґРґ.РјРј.РіРі):")
    return TOUR_END

async def create_tour_end_date(update, context):
    context.user_data['tour_end'] = update.message.text.strip()
    summary = (
        f"РќР°Р·РІР°РЅРёРµ: {context.user_data['tour_name']}\n"
        f"РЎС‚Р°СЂС‚: {context.user_data['tour_start']}\n"
        f"Р”РµРґР»Р°Р№РЅ: {context.user_data['tour_deadline']}\n"
        f"РћРєРѕРЅС‡Р°РЅРёРµ: {context.user_data['tour_end']}\n"
        "\nРџРѕРґС‚РІРµСЂРґРёС‚СЊ СЃРѕР·РґР°РЅРёРµ С‚СѓСЂР°? (РґР°/РЅРµС‚)"
    )
    await update.message.reply_text(summary)
    return TOUR_CONFIRM

async def create_tour_confirm(update, context):
    text = update.message.text.strip().lower()
    if text not in ("РґР°", "РЅРµС‚"):
        await update.message.reply_text("РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РЅР°РїРёС€РёС‚Рµ 'РґР°' РёР»Рё 'РЅРµС‚'.")
        return TOUR_CONFIRM
    if text == "РЅРµС‚":
        await update.message.reply_text("РЎРѕР·РґР°РЅРёРµ С‚СѓСЂР° РѕС‚РјРµРЅРµРЅРѕ.")
        return ConversationHandler.END
    db.create_tour(
        context.user_data['tour_name'],
        context.user_data['tour_start'],
        context.user_data['tour_deadline'],
        context.user_data['tour_end']
    )
    await update.message.reply_text("РўСѓСЂ СѓСЃРїРµС€РЅРѕ СЃРѕР·РґР°РЅ!")
    return ConversationHandler.END

async def create_tour_cancel(update, context):
    await update.message.reply_text("РЎРѕР·РґР°РЅРёРµ С‚СѓСЂР° РѕС‚РјРµРЅРµРЅРѕ.")
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
        await update.message.reply_text("РўСѓСЂРѕРІ РїРѕРєР° РЅРµС‚.")
        return
    msg = "РЎРїРёСЃРѕРє С‚СѓСЂРѕРІ:\n"
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
            f"РЎС‚Р°СЂС‚: {t[2]} | Р”РµРґР»Р°Р№РЅ: {t[3]} | РћРєРѕРЅС‡Р°РЅРёРµ: {t[4]}\n"
            f"РЎС‚Р°С‚СѓСЃ: {t[5]} | РџРѕР±РµРґРёС‚РµР»Рё: {winners}\n"
        )
    await update.message.reply_text(msg)

# --- Push Notifications ---
SEND_PUSH = 100

async def send_push_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """РќР°С‡Р°Р»Рѕ РїСЂРѕС†РµСЃСЃР° РѕС‚РїСЂР°РІРєРё push-СѓРІРµРґРѕРјР»РµРЅРёСЏ"""
    if not await admin_only(update, context):
        return ConversationHandler.END
        
    await update.message.reply_text(
        "вњ‰пёЏ Р’РІРµРґРёС‚Рµ С‚РµРєСЃС‚ push-СѓРІРµРґРѕРјР»РµРЅРёСЏ, РєРѕС‚РѕСЂРѕРµ Р±СѓРґРµС‚ РѕС‚РїСЂР°РІР»РµРЅРѕ РІСЃРµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј Р±РѕС‚Р°:\n"
        "(Р’С‹ РјРѕР¶РµС‚Рµ РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ HTML-СЂР°Р·РјРµС‚РєСѓ: <b>Р¶РёСЂРЅС‹Р№</b>, <i>РєСѓСЂСЃРёРІ</i>, <a href=\"URL\">СЃСЃС‹Р»РєР°</a>)\n\n"
        "Р”Р»СЏ РѕС‚РјРµРЅС‹ РІРІРµРґРёС‚Рµ /cancel"
    )
    return SEND_PUSH

async def send_push_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """РћС‚РїСЂР°РІРєР° push-СѓРІРµРґРѕРјР»РµРЅРёСЏ РІСЃРµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј"""
    message_text = update.message.text
    users = db.get_all_users()
    
    if not users:
        await update.message.reply_text("вќЊ Р’ Р±Р°Р·Рµ РґР°РЅРЅС‹С… РЅРµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№.")
        return ConversationHandler.END
    
    sent_count = 0
    failed_count = 0
    
    progress_msg = await update.message.reply_text(f"рџ”„ РћС‚РїСЂР°РІРєР° СѓРІРµРґРѕРјР»РµРЅРёСЏ {len(users)} РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј...")
    
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
            
            # РќРµ СЃРїР°РјРёРј СЃР»РёС€РєРѕРј Р±С‹СЃС‚СЂРѕ, С‡С‚РѕР±С‹ РЅРµ РїРѕР»СѓС‡РёС‚СЊ РѕРіСЂР°РЅРёС‡РµРЅРёРµ РѕС‚ Telegram
            if sent_count % 20 == 0:
                await asyncio.sleep(1)
                await progress_msg.edit_text(f"рџ”„ РћС‚РїСЂР°РІР»РµРЅРѕ {sent_count} РёР· {len(users)} СѓРІРµРґРѕРјР»РµРЅРёР№...")
                
        except Exception as e:
            logger.error(f"РћС€РёР±РєР° РїСЂРё РѕС‚РїСЂР°РІРєРµ СѓРІРµРґРѕРјР»РµРЅРёСЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ {user_id}: {e}")
            failed_count += 1
    
    await progress_msg.edit_text(
        f"вњ… Р Р°СЃСЃС‹Р»РєР° Р·Р°РІРµСЂС€РµРЅР°!\n"
        f"вЂў РћС‚РїСЂР°РІР»РµРЅРѕ: {sent_count}\n"
        f"вЂў РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РїСЂР°РІРёС‚СЊ: {failed_count}\n\n"
        f"РўРµРєСЃС‚ СѓРІРµРґРѕРјР»РµРЅРёСЏ:\n{message_text}"
    )
    return ConversationHandler.END

async def send_push_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """РћС‚РјРµРЅР° РѕС‚РїСЂР°РІРєРё push-СѓРІРµРґРѕРјР»РµРЅРёСЏ"""
    await update.message.reply_text("вќЊ РћС‚РїСЂР°РІРєР° СѓРІРµРґРѕРјР»РµРЅРёР№ РѕС‚РјРµРЅРµРЅР°.")
    return ConversationHandler.END

# Р РµРіРёСЃС‚СЂР°С†РёСЏ РѕР±СЂР°Р±РѕС‚С‡РёРєР° РґР»СЏ РєРѕРјР°РЅРґС‹ /push
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

# --- Р Р°СЃСЃС‹Р»РєР° С‚РѕР»СЊРєРѕ РїРѕРґРїРёСЃС‡РёРєР°Рј ---
BROADCAST_SUBS_WAIT_TEXT = 12001
BROADCAST_SUBS_WAIT_DATETIME = 12003
BROADCAST_SUBS_CONFIRM = 12002

async def broadcast_subscribers_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text("Введите текст рассылки для подписчиков (или /cancel). Можно использовать HTML-разметку (<b>жирный</b>, <i>курсив</i>, ссылки):", parse_mode='HTML')
    return BROADCAST_SUBS_WAIT_TEXT

async def broadcast_subscribers_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    if not text:
        await update.message.reply_text("РџСѓСЃС‚РѕРµ СЃРѕРѕР±С‰РµРЅРёРµ. Р’РІРµРґРёС‚Рµ С‚РµРєСЃС‚ РёР»Рё /cancel:")
        return BROADCAST_SUBS_WAIT_TEXT
    context.user_data['broadcast_text'] = text
    await update.message.reply_text(
        "РЈРєР°Р¶РёС‚Рµ РґР°С‚Сѓ Рё РІСЂРµРјСЏ РѕС‚РїСЂР°РІРєРё РІ С„РѕСЂРјР°С‚Рµ: РґРґ.РјРј.РіРі С‡С‡:РјРј (РњРЎРљ).\n"
        "РќР°РїСЂРёРјРµСЂ: 05.09.25 10:30"
    )
    return BROADCAST_SUBS_WAIT_DATETIME

async def broadcast_subscribers_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """РџР°СЂСЃРёС‚ РІСЂРµРјСЏ РІ РњРЎРљ (UTC+3), СЃРѕС…СЂР°РЅСЏРµС‚ РІСЂРµРјСЏ РІ UTC Рё РїСЂРµРґР»Р°РіР°РµС‚ РїРѕРґС‚РІРµСЂРґРёС‚СЊ."""
    s = (update.message.text or '').strip()
    dt_msk = None
    for fmt in ("%d.%m.%y %H:%M", "%d.%m.%Y %H:%M"):
        try:
            dt_msk = datetime.datetime.strptime(s, fmt)
            break
        except Exception:
            pass
    if not dt_msk:
        await update.message.reply_text(
            "РќРµ СѓРґР°Р»РѕСЃСЊ СЂР°СЃРїРѕР·РЅР°С‚СЊ РґР°С‚Сѓ. Р’РІРµРґРёС‚Рµ РІ С„РѕСЂРјР°С‚Рµ РґРґ.РјРј.РіРі С‡С‡:РјРј (РњРЎРљ), РЅР°РїСЂРёРјРµСЂ 05.09.25 10:30"
        )
        return BROADCAST_SUBS_WAIT_DATETIME
    # РџРµСЂРµРІРѕРґ РњРЎРљ (UTC+3) РІ UTC
    dt_utc = dt_msk - datetime.timedelta(hours=3)
    now_utc = datetime.datetime.utcnow()
    if dt_utc < now_utc:
        await update.message.reply_text("РЈРєР°Р·Р°РЅРЅРѕРµ РІСЂРµРјСЏ РІ РїСЂРѕС€Р»РѕРј. Р’РІРµРґРёС‚Рµ Р±СѓРґСѓС‰СѓСЋ РґР°С‚Сѓ/РІСЂРµРјСЏ (РњРЎРљ):")
        return BROADCAST_SUBS_WAIT_DATETIME
    context.user_data['broadcast_dt_utc'] = dt_utc.isoformat()
    context.user_data['broadcast_dt_input'] = s

    # РџРѕРґСЃС‡РёС‚Р°С‚СЊ С‡РёСЃР»Рѕ Р°РєС‚РёРІРЅС‹С… РїРѕРґРїРёСЃС‡РёРєРѕРІ РЅР° С‚РµРєСѓС‰РёР№ РјРѕРјРµРЅС‚ (РґР»СЏ РёРЅС„РѕСЂРјР°С†РёРё)
    subs = db.get_all_subscriptions()  # [(user_id, paid_until)]
    targets = []
    for user_id, paid_until in subs:
        if not paid_until:
            continue
        try:
            dtp = datetime.datetime.fromisoformat(str(paid_until))
        except Exception:
            continue
        if dtp > now_utc:
            targets.append(user_id)
    cnt = len(targets)
    # РџРѕРєР°Р¶РµРј РїРѕР»РЅС‹Р№ С‚РµРєСЃС‚ РїРµСЂРµРґ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµРј, СЃ РїРѕРґРґРµСЂР¶РєРѕР№ HTML
    try:
        await update.message.reply_text("РџСЂРµРґРїСЂРѕСЃРјРѕС‚СЂ СЂР°СЃСЃС‹Р»РєРё:", parse_mode='HTML')
    except Exception:
        await update.message.reply_text("РџСЂРµРґРїСЂРѕСЃРјРѕС‚СЂ СЂР°СЃСЃС‹Р»РєРё:")
    try:
        await update.message.reply_text(context.user_data.get('broadcast_text',''), parse_mode='HTML', disable_web_page_preview=False)
    except Exception:
        await update.message.reply_text(context.user_data.get('broadcast_text',''))
    preview = (context.user_data.get('broadcast_text','')[:120] + ('вЂ¦' if len(context.user_data.get('broadcast_text','')) > 120 else ''))
    await update.message.reply_text(
        f"РЎРѕРѕР±С‰РµРЅРёРµ: \nвЂ” {preview}\n\nРћС‚РїСЂР°РІРёС‚СЊ {cnt} РїРѕРґРїРёСЃС‡РёРєР°Рј РІ {s} (РњРЎРљ)?\n"
        "РћС‚РІРµС‚СЊС‚Рµ 'РґР°' РґР»СЏ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ РёР»Рё 'РЅРµС‚' РґР»СЏ РѕС‚РјРµРЅС‹."
    )
    return BROADCAST_SUBS_CONFIRM

async def broadcast_subscribers_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ans = (update.message.text or '').strip().lower()
    if ans not in ("РґР°", "Рґ", "yes", "y", "СѓРіСѓ", "ok", "РѕРє"):
        await update.message.reply_text("Р Р°СЃСЃС‹Р»РєР° РѕС‚РјРµРЅРµРЅР°.")
        return ConversationHandler.END
    text = context.user_data.get('broadcast_text') or ''
    if not text:
        await update.message.reply_text("РўРµРєСЃС‚ СЂР°СЃСЃС‹Р»РєРё РЅРµ РЅР°Р№РґРµРЅ. Р—Р°РїСѓСЃС‚РёС‚Рµ Р·Р°РЅРѕРІРѕ: /broadcast_subscribers")
        return ConversationHandler.END
    # РћРїСЂРµРґРµР»СЏРµРј, РєРѕРіРґР° РѕС‚РїСЂР°РІР»СЏС‚СЊ
    dt_utc_str = context.user_data.get('broadcast_dt_utc')
    dt_utc = None
    if dt_utc_str:
        try:
            dt_utc = datetime.datetime.fromisoformat(dt_utc_str)
        except Exception:
            dt_utc = None
    now = datetime.datetime.utcnow()
    delay = 0
    if dt_utc and dt_utc > now:
        delay = (dt_utc - now).total_seconds()
    # РџР»Р°РЅРёСЂСѓРµРј РѕС‚РїСЂР°РІРєСѓ С‡РµСЂРµР· JobQueue
    try:
        context.application.job_queue.run_once(
            broadcast_subscribers_job,
            when=max(0, int(delay)),
            data={'text': text}
        )
        when_desc = context.user_data.get('broadcast_dt_input') or 'СЃРµР№С‡Р°СЃ'
        await update.message.reply_text(f"Р Р°СЃСЃС‹Р»РєР° Р·Р°РїР»Р°РЅРёСЂРѕРІР°РЅР° РЅР° {when_desc} (РњРЎРљ).")
    except Exception as e:
        await update.message.reply_text(f"РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РїР»Р°РЅРёСЂРѕРІР°С‚СЊ СЂР°СЃСЃС‹Р»РєСѓ: {e}")
    return ConversationHandler.END

async def broadcast_subscribers_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Р Р°СЃСЃС‹Р»РєР° РѕС‚РјРµРЅРµРЅР°.")
    return ConversationHandler.END

async def broadcast_subscribers_job(context: ContextTypes.DEFAULT_TYPE):
    """JobQueue callback: РѕС‚РїСЂР°РІР»СЏРµС‚ С‚РµРєСЃС‚ РІСЃРµРј Р°РєС‚РёРІРЅС‹Рј РїРѕРґРїРёСЃС‡РёРєР°Рј."""
    text = ''
    try:
        job = getattr(context, 'job', None)
        if job and job.data:
            text = job.data.get('text') or ''
    except Exception:
        text = ''
    now = datetime.datetime.utcnow()
    subs = db.get_all_subscriptions()
    users = []
    for user_id, paid_until in subs:
        if not paid_until:
            continue
        try:
            dt = datetime.datetime.fromisoformat(str(paid_until))
        except Exception:
            continue
        if dt > now:
            users.append((user_id,))
    if not users:
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text="Р Р°СЃСЃС‹Р»РєР°: РЅРµС‚ Р°РєС‚РёРІРЅС‹С… РїРѕРґРїРёСЃС‡РёРєРѕРІ РЅР° РјРѕРјРµРЅС‚ РѕС‚РїСЂР°РІРєРё.")
        except Exception:
            pass
        return
    try:
        # РћС‚РїСЂР°РІР»СЏРµРј РїРѕР»РЅС‹Р№ С‚РµРєСЃС‚; РІРєР»СЋС‡Р°РµРј РїСЂРµРґРїСЂРѕСЃРјРѕС‚СЂ СЃСЃС‹Р»РѕРє Рё РїРѕРґРґРµСЂР¶РёРІР°РµРј СЌРјРѕРґР·Рё
        success, failed = await send_message_to_users(
            context.bot,
            users,
            text=text,
            parse_mode='HTML',
            disable_web_page_preview=False,
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"Р Р°СЃСЃС‹Р»РєР° Р·Р°РІРµСЂС€РµРЅР°. РЈСЃРїРµС€РЅРѕ: {success}, РѕС€РёР±РѕРє: {failed}.")
        except Exception:
            pass
    except Exception as e:
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"РћС€РёР±РєР° РїСЂРё СЂР°СЃСЃС‹Р»РєРµ: {e}")
        except Exception:
            pass

# --- РђРєС‚РёРІР°С†РёСЏ С‚СѓСЂР° Р°РґРјРёРЅРѕРј ---
async def activate_tour(update, context):
    if not await admin_only(update, context):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ: /activate_tour <id>")
        return
    tour_id = int(context.args[0])
    tours = db.get_all_tours()
    found = False
    for t in tours:
        if t[0] == tour_id:
            db.update_tour_status(tour_id, "Р°РєС‚РёРІРµРЅ")
            found = True
        elif t[5] == "Р°РєС‚РёРІРµРЅ":
            db.update_tour_status(t[0], "СЃРѕР·РґР°РЅ")
    if found:
        await update.message.reply_text(f"РўСѓСЂ {tour_id} Р°РєС‚РёРІРёСЂРѕРІР°РЅ.")
    else:
        await update.message.reply_text(f"РўСѓСЂ СЃ id {tour_id} РЅРµ РЅР°Р№РґРµРЅ.")

# --- Utility: enhanced /addhc supporting @username or user_id ---
async def addhc2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_only(update, context):
        return
    # Expect two arguments: identifier (@username or user_id) and amount
    if len(context.args) != 2 or not context.args[1].isdigit():
        await update.message.reply_text('РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ: /addhc @username 100 РёР»Рё /addhc user_id 100')
        return
    identifier = (context.args[0] or '').strip()
    amount = int(context.args[1])

    # Resolve user either by @username or by numeric id
    user = None
    resolved_username = None
    if identifier.startswith('@') or not identifier.isdigit():
        username = identifier.lstrip('@')
        user = db.get_user_by_username(username)
        resolved_username = username
    else:
        try:
            user_id = int(identifier)
        except ValueError:
            user_id = None
        if user_id is not None:
            user = db.get_user_by_id(user_id)
            if user:
                resolved_username = user[1] or ''

    if not user:
        await update.message.reply_text('РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ.')
        return

    db.update_hc_balance(user[0], amount)
    new_balance = db.get_user_by_id(user[0])[3]

    # Notify the user
    try:
        await context.bot.send_message(
            chat_id=user[0],
            text=f'Р’Р°Рј РЅР°С‡РёСЃР»РµРЅРѕ {amount} HC!\nРўРµРєСѓС‰РёР№ Р±Р°Р»Р°РЅСЃ: {new_balance} HC'
        )
    except Exception:
        pass

    # Reply to admin with more details
    target_label = f"@{resolved_username}" if resolved_username else f"id {user[0]}"
    await update.message.reply_text(f'РќР°С‡РёСЃР»РµРЅРѕ {target_label} {amount} HC.')
