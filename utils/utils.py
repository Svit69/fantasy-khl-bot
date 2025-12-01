import logging
from telegram import Update, InputFile
from telegram.ext import ContextTypes
import datetime
import asyncio
import db
from config import ADMIN_ID
import os
import logging

SUBSCRIPTION_STARS = int(os.getenv('SUBSCRIPTION_STARS', '199'))

IMAGES_DIR = 'images'
TOUR_IMAGE_PATH_FILE = 'latest_tour.txt'
CHALLENGE_IMAGE_PATH_FILE = 'latest_challenge.txt'
SUBSCRIBE_QR_IMAGE_PATH_FILE = 'subscribe_qr.txt'
logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id == ADMIN_ID

async def poll_subscription_reminders(bot, interval: int = 3600):
    """Periodically checks subscriptions and sends reminders:
    - 7 days before expiration
    - 3 days before expiration
    - On expiration day
    Uses db.subscription_notifications for deduplication.
    """
    logger.debug("poll_subscription_reminders started (package utils)")
    while True:
        try:
            subs = db.get_all_subscriptions()  # [(user_id, paid_until)]
            today = datetime.datetime.utcnow().date()
            for user_id, paid_until in subs:
                if not paid_until:
                    continue
                try:
                    dt = datetime.datetime.fromisoformat(str(paid_until))
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
                            logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
                elif remain == 0:
                    kind = "expired"
                    notify_date = dt.date().isoformat()
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
            logger.error(f"poll_subscription_reminders loop error: {e}")
        await asyncio.sleep(interval)

async def send_message_to_users(bot, users, text: str = None, photo_path: str = None, caption: str = None, parse_mode: str = None, disable_web_page_preview: bool = False):
    """Send text or photo to a list of users."""
    success, failed = 0, 0
    for user in users:
        try:
            if photo_path:
                await bot.send_photo(
                    chat_id=user[0],
                    photo=InputFile(photo_path),
                    caption=caption,
                    parse_mode=parse_mode,
                )
            else:
                remaining = str(text) if text is not None else ''
                while remaining:
                    chunk = remaining[:4096]
                    remaining = remaining[4096:]
                    await bot.send_message(
                        chat_id=user[0],
                        text=chunk,
                        parse_mode=parse_mode,
                        disable_web_page_preview=disable_web_page_preview,
                    )
            success += 1
        except Exception as e:
            logger.warning(f"Ошибка при отправке пользователю {user[0]}: {e}")
            failed += 1
    return success, failed
