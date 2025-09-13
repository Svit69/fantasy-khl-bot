from telegram import Update
from telegram.ext import ContextTypes
import db


async def addhc2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from handlers.admin_handlers import admin_only  # reuse existing check
    if not await admin_only(update, context):
        return
    if len(context.args) != 2 or not context.args[1].isdigit():
        await update.message.reply_text('Использование: /addhc @username 100 или /addhc user_id 100')
        return
    identifier = (context.args[0] or '').strip()
    amount = int(context.args[1])

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
        await update.message.reply_text('Пользователь не найден.')
        return

    db.update_hc_balance(user[0], amount)
    new_balance = db.get_user_by_id(user[0])[3]

    try:
        await context.bot.send_message(
            chat_id=user[0],
            text=f'Начислено {amount} HC!\nТекущий баланс: {new_balance} HC'
        )
    except Exception:
        pass

    target_label = f"@{resolved_username}" if resolved_username else f"id {user[0]}"
    await update.message.reply_text(f'Начислено {target_label} {amount} HC.')

