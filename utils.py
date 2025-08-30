import logging
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from config import ADMIN_ID
import os

SUBSCRIPTION_PRICE_STARS = 299

import db
import datetime
import asyncio

async def poll_subscription_reminders(bot, interval=3600):
    """Периодически проверяет подписки и отправляет напоминания:
    - за 7 дней
    - за 3 дня
    - в день окончания (0 дней)
    Отправки дедуплицируются таблицей subscription_notifications.
    """
    print("[DEBUG] poll_subscription_reminders started")
    while True:
        try:
            subs = db.get_all_subscriptions()  # [(user_id, paid_until)]
            today = datetime.datetime.utcnow().date()
            for user_id, paid_until in subs:
                if not paid_until:
                    continue
                try:
                    dt = datetime.datetime.fromisoformat(paid_until)
                except Exception:
                    continue
                remain = (dt.date() - today).days
                if remain in (7, 3):
                    kind = f"{remain}d"
                    notify_date = today.isoformat()
                    if not db.has_subscription_notification(user_id, notify_date, kind):
                        try:
                            await bot.send_message(
                                chat_id=user_id,
                                text=(
                                    f"⏰ Напоминание: подписка истекает через {remain} дн.\n"
                                    f"Продлите подписку командой /subscribe."
                                )
                            )
                            db.record_subscription_notification(user_id, notify_date, kind)
                        except Exception as e:
                            logger.warning(f"Не удалось отправить напоминание ({kind}) пользователю {user_id}: {e}")
                elif remain == 0:
                    kind = "expired"
                    notify_date = dt.date().isoformat()  # фиксируем на дате окончания, чтобы не дублировать на след. дни
                    if not db.has_subscription_notification(user_id, notify_date, kind):
                        try:
                            await bot.send_message(
                                chat_id=user_id,
                                text=(
                                    "⚠️ Срок вашей подписки истёк сегодня. \n"
                                    "Оформите продление с помощью /subscribe."
                                )
                            )
                            db.record_subscription_notification(user_id, notify_date, kind)
                        except Exception as e:
                            logger.warning(f"Не удалось отправить уведомление об окончании подписки пользователю {user_id}: {e}")
        except Exception as e:
            print(f"Ошибка в poll_subscription_reminders: {e}")
        await asyncio.sleep(interval)

IMAGES_DIR = 'images'
__all__ = ['IMAGES_DIR']

TOUR_IMAGE_PATH_FILE = 'latest_tour.txt'
CHALLENGE_IMAGE_PATH_FILE = 'latest_challenge.txt'
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
