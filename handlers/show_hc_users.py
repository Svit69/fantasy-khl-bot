from telegram import Update
from telegram.ext import ContextTypes

import db
from handlers.admin_handlers import admin_only


async def show_hc_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет администратору список пользователей с положительным балансом HC."""
    if not await admin_only(update, context):
        return

    with db.closing(db.sqlite3.connect(db.DB_NAME)) as conn:
        rows = conn.execute(
            """
            SELECT telegram_id, username, name, hc_balance
            FROM users
            WHERE hc_balance IS NOT NULL AND hc_balance > 0
            ORDER BY hc_balance DESC, telegram_id ASC
            """
        ).fetchall()

    if not rows:
        await update.message.reply_text("Нет пользователей с положительным балансом HC.")
        return

    lines = []
    for user_id, username, name, hc_balance in rows:
        lines.append(f"{user_id} | {username or '-'} | {name or '-'} | HC: {hc_balance}")

    msg = 'Пользователи с балансом HC > 0:\n\n' + '\n'.join(lines)
    for i in range(0, len(msg), 4000):
        await update.message.reply_text(msg[i:i + 4000])
