import logging
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from config import ADMIN_ID
import os

IMAGES_DIR = 'images'
TOUR_IMAGE_PATH_FILE = 'latest_tour.txt'
CHALLENGE_IMAGE_PATH_FILE = 'latest_challenge.txt'
logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id == ADMIN_ID

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
