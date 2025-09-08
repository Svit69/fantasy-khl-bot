import datetime
from telegram.ext import ContextTypes, ConversationHandler
from handlers.admin_handlers import broadcast_subscribers_job


async def broadcast_subscribers_confirm(update, context: ContextTypes.DEFAULT_TYPE):
    ans = (update.message.text or '').strip().lower()
    ok_values = {"да", "д", "ага", "угу", "ок", "okay", "ok", "yes", "y"}
    if ans not in ok_values:
        await update.message.reply_text("Рассылка отменена.")
        return ConversationHandler.END

    text = context.user_data.get('broadcast_text') or ''
    if not text:
        await update.message.reply_text("Текст рассылки не найден. Запустите заново: /broadcast_subscribers")
        return ConversationHandler.END

    dt_utc = None
    dt_utc_str = context.user_data.get('broadcast_dt_utc')
    if dt_utc_str:
        try:
            dt_utc = datetime.datetime.fromisoformat(dt_utc_str)
        except Exception:
            dt_utc = None

    now = datetime.datetime.utcnow()
    delay = 0
    if dt_utc and dt_utc > now:
        delay = max(0, int((dt_utc - now).total_seconds()))

    try:
        context.application.job_queue.run_once(
            broadcast_subscribers_job,
            when=delay,
            data={'text': text}
        )
        when_desc = context.user_data.get('broadcast_dt_input') or 'как можно скорее'
        await update.message.reply_text(f"Рассылка запланирована на {when_desc} (МСК).")
    except Exception as e:
        await update.message.reply_text(f"Не удалось запланировать рассылку: {e}")
    return ConversationHandler.END

