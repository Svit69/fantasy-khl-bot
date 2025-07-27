import logging
from telegram.ext import Application, CommandHandler
from config import TELEGRAM_TOKEN, ADMIN_ID
import db
from handlers import start, tour, hc
import os
from telegram import Update, InputFile
from telegram.ext import ContextTypes

logging.basicConfig(level=logging.INFO)

IMAGES_DIR = 'images'

async def admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text('Нет доступа')
        return False
    return True

async def send_tour_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return
    if not update.message.photo:
        await update.message.reply_text('Пожалуйста, отправьте изображение для тура в виде фото вместе с этой командой.')
        return
    photo = update.message.photo[-1]
    file = await photo.get_file()
    filename = f"tour_{photo.file_unique_id}.jpg"
    path = os.path.join(IMAGES_DIR, filename)
    await file.download_to_drive(path)
    # Рассылка всем пользователям
    users = db.get_all_users()
    for user in users:
        try:
            await context.bot.send_photo(chat_id=user[0], photo=InputFile(path), caption='🏒 Новый тур! Состав игроков на сегодня:')
        except Exception:
            pass
    await update.message.reply_text('Изображение тура разослано всем пользователям.')

async def addhc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return
    if len(context.args) != 2 or not context.args[1].isdigit():
        await update.message.reply_text('Использование: /addhc @username 100')
        return
    username = context.args[0].lstrip('@')
    amount = int(context.args[1])
    user = db.get_user_by_username(username)
    if not user:
        await update.message.reply_text('Пользователь не найден.')
        return
    db.update_hc_balance(user[0], amount)
    new_balance = db.get_user_by_id(user[0])[3]
    await context.bot.send_message(chat_id=user[0], text=f'🎉 Тебе начислено {amount} HC!\n💰 Новый баланс: {new_balance} HC')
    await update.message.reply_text(f'Пользователю @{username} начислено {amount} HC.')

async def send_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        filename = f"results_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        await file.download_to_drive(path)
        users = db.get_all_users()
        for user in users:
            try:
                await context.bot.send_photo(chat_id=user[0], photo=InputFile(path), caption='📊 Результаты тура:')
            except Exception:
                pass
        await update.message.reply_text('Результаты (изображение) разосланы всем пользователям.')
    elif context.args:
        text = ' '.join(context.args)
        users = db.get_all_users()
        for user in users:
            try:
                await context.bot.send_message(chat_id=user[0], text=f'📊 Результаты тура:\n{text}')
            except Exception:
                pass
        await update.message.reply_text('Результаты (текст) разосланы всем пользователям.')
    else:
        await update.message.reply_text('Пришлите изображение или текст после команды.')

def main():
    db.init_db()
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('tour', tour))
    app.add_handler(CommandHandler('hc', hc))
    app.add_handler(CommandHandler('send_tour_image', send_tour_image))
    app.add_handler(CommandHandler('addhc', addhc))
    app.add_handler(CommandHandler('send_results', send_results))

    # TODO: добавить админские команды

    app.run_polling()

if __name__ == '__main__':
    if not os.path.exists('images'):
        os.makedirs('images')
    main() 