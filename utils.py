import logging
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from config import ADMIN_ID
import os
import requests
import db
import datetime
import asyncio

IMAGES_DIR = 'images'
__all__ = ['IMAGES_DIR']

YOOMONEY_API_URL = "https://yoomoney.ru/api/operation-history"
SHOP_ID = "1141033"
API_KEY = "test_NnIZ_gFbddTpDQQNphx0KuZFqBWHd6PVoB1KxVtWOHw"
SUBSCRIPTION_AMOUNT = 299

async def poll_yoomoney_payments(bot, interval=60):
    """
    Периодически опрашивает ЮMoney на предмет новых успешных платежей.
    Если найден новый платеж с label user_{user_id} — продлевает подписку.
    """
    last_checked = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    while True:
        try:
            print("[DEBUG] API_KEY:", API_KEY[:8], "...")
            headers = {"Authorization": f"Bearer {API_KEY}"}
            data = {"type": "deposition", "records": 50}
            resp = requests.post(YOOMONEY_API_URL, headers=headers, data=data)
            if resp.status_code == 200:
                result = resp.json()
                operations = result.get("operations", [])
                for op in operations:
                    if op.get("status") == "success" and op.get("direction") == "in":
                        label = op.get("label", "")
                        amount = float(op.get("amount", 0))
                        op_id = op.get("operation_id")
                        if label.startswith("user_") and amount == SUBSCRIPTION_AMOUNT:
                            user_id = int(label.replace("user_", ""))
                            sub = db.get_subscription(user_id)
                            if not sub or (sub and sub[2] != op_id):
                                # Продлить подписку на месяц
                                paid_until = datetime.datetime.utcnow() + datetime.timedelta(days=31)
                                db.add_or_update_subscription(user_id, paid_until.isoformat(), op_id)
                                # Оповестить пользователя
                                try:
                                    await bot.send_message(chat_id=user_id, text="✅ Ваша подписка успешно продлена до {}!".format(paid_until.strftime('%d.%m.%Y')))
                                except Exception as e:
                                    logger.warning(f"Не удалось уведомить пользователя {user_id} о подписке: {e}")
            else:
                logger.warning(f"Ошибка запроса к ЮMoney: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.exception(f"Ошибка при polling ЮMoney: {e}")
        await asyncio.sleep(interval)

TOUR_IMAGE_PATH_FILE = 'latest_tour.txt'
logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id == ADMIN_ID

async def send_message_to_users(bot, users, text: str = None, photo_path: str = None, caption: str = None):
    """Send text or photo to a list of users."""
    success, failed = 0, 0
    for user in users:
        try:
            if photo_path:
                await bot.send_photo(chat_id=user[0], photo=InputFile(photo_path), caption=caption)
            else:
                await bot.send_message(chat_id=user[0], text=text)
            success += 1
        except Exception as e:
            logger.warning(f"Ошибка при отправке пользователю {user[0]}: {e}")
            failed += 1
    return success, failed

import re

def escape_md(text: str) -> str:
    """
    Экранирует спецсимволы для Telegram MarkdownV2.
    """
    if not isinstance(text, str):
        text = str(text)
    # Экранируем все специальные символы MarkdownV2
    return re.sub(r'([_\*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)
