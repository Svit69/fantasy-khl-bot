import json
import db
from telegram import Update
from telegram.ext import ContextTypes


async def list_tours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.admin_handlers import admin_only  # reuse existing admin check
    if not await admin_only(update, context):
        return
    tours = db.get_all_tours()
    if not tours:
        await update.message.reply_text("Нет туров.")
        return
    msg = "Список туров:\n"
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
            f"Старт: {t[2]} | Дедлайн: {t[3]} | Окончание: {t[4]}\n"
            f"Статус: {t[5]} | Победители: {winners}\n"
        )
    await update.message.reply_text(msg)

