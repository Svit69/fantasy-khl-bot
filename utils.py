import logging
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from config import ADMIN_ID
import os

YOOKASSA_SHOP_ID = "1141033"
YOOKASSA_SECRET_KEY = "test_NnIZ_gFbddTpDQQNphx0KuZFqBWHd6PVoB1KxVtWOHw"
SUBSCRIPTION_AMOUNT = 299


def create_yookassa_payment(user_id: int):
    import sys
    print("[DEBUG] Модуль configuration:", sys.modules.get('yookassa.configuration'))
    print("[DEBUG] Модуль Payment:", sys.modules.get('yookassa.payment'))
    print("[DEBUG] Модуль client:", sys.modules.get('yookassa.client'))
    print("[DEBUG] Модуль yookassa:", sys.modules.get('yookassa'))
    from yookassa import Configuration
    print("[DEBUG] Ключи внутри функции:", Configuration.account_id, Configuration.secret_key)
    print("[DEBUG] Импорт Payment внутри функции create_yookassa_payment")
    from yookassa import Payment
    print("[DEBUG] Перед Payment.create")
    payment = Payment.create({
        "amount": {
            "value": f"{SUBSCRIPTION_AMOUNT}.00",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/khl_draft_bot"
        },
        "capture": True,
        "description": f"Подписка на Fantasy KHL для user_{user_id}",
        "metadata": {"user_id": str(user_id)}
    })
    from db import save_payment_id
    save_payment_id(user_id, payment.id, status='pending')
    return payment.confirmation.confirmation_url, payment.id

import db
import datetime
import asyncio

async def poll_yookassa_payments(bot, interval=60):
    print("[DEBUG] poll_yookassa_payments started")
    from yookassa import Payment
    import db
    while True:
        try:
            pending = db.get_pending_payments()
            print("[DEBUG] pending payments:", pending)
            for payment_id, user_id in pending:
                payment = Payment.find_one(payment_id)
                print(f"[DEBUG] payment_id={payment_id}, status={payment.status}")
                if payment.status == "succeeded":
                    # Продлить подписку
                    paid_until = datetime.datetime.utcnow() + datetime.timedelta(days=31)
                    db.add_or_update_subscription(user_id, paid_until.isoformat(), payment_id)
                    db.update_payment_status(payment_id, "succeeded")
                    try:
                        await bot.send_message(chat_id=user_id, text=f"✅ Ваша подписка успешно продлена до {paid_until.strftime('%d.%m.%Y')}!")
                    except Exception as e:
                        print(f"Не удалось уведомить пользователя {user_id}: {e}")
        except Exception as e:
            print(f"Ошибка при polling ЮKassa: {e}")
        await asyncio.sleep(interval)


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
