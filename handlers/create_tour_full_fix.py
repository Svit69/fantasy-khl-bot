import os
from telegram import InputFile
from telegram.ext import ContextTypes, ConversationHandler
from utils import IMAGES_DIR, TOUR_IMAGE_PATH_FILE
import db

# States for fixed conversation
FCT_NAME, FCT_START, FCT_DEADLINE, FCT_END, FCT_IMAGE, FCT_ROSTER = range(2300, 2306)


async def start(update, context: ContextTypes.DEFAULT_TYPE):
    # clear temp fields
    for k in ['ct_name', 'ct_start', 'ct_deadline', 'ct_end', 'ct_image_filename', 'ct_tour_id']:
        context.user_data.pop(k, None)
    await update.message.reply_text("Введите название тура:")
    return FCT_NAME


async def name(update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ct_name'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите дату начала тура (дд.мм.гг):")
    return FCT_START


async def start_date(update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ct_start'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите дедлайн (дд.мм.гг чч:мм):")
    return FCT_DEADLINE


async def deadline(update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ct_deadline'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите дату окончания тура (дд.мм.гг):")
    return FCT_END


async def end_date(update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ct_end'] = (update.message.text or '').strip()
    try:
        tour_id = db.create_tour(
            context.user_data.get('ct_name', ''),
            context.user_data.get('ct_start', ''),
            context.user_data.get('ct_deadline', ''),
            context.user_data.get('ct_end', ''),
        )
        context.user_data['ct_tour_id'] = tour_id
    except Exception as e:
        await update.message.reply_text(f"Не удалось создать тур: {e}")
        return ConversationHandler.END
    await update.message.reply_text("Отлично! Теперь отправьте изображение тура одним фото в ответ на это сообщение.")
    return FCT_IMAGE


async def photo(update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        await update.message.reply_text("Пожалуйста, отправьте фото.")
        return FCT_IMAGE
    try:
        photo = update.message.photo[-1]
        tg_file = await photo.get_file()
        os.makedirs(IMAGES_DIR, exist_ok=True)
        filename = f"tour_{photo.file_unique_id}.jpg"
        file_path = os.path.join(IMAGES_DIR, filename)
        try:
            await tg_file.download_to_drive(file_path)
        except Exception:
            await tg_file.download(custom_path=file_path)
        try:
            with open(TOUR_IMAGE_PATH_FILE, 'w', encoding='utf-8') as f:
                f.write(filename)
        except Exception:
            pass
        context.user_data['ct_image_filename'] = filename
        try:
            tour_id = int(context.user_data.get('ct_tour_id') or 0)
            if tour_id:
                db.update_tour_image(tour_id, filename, photo.file_id)
        except Exception:
            pass
        await update.message.reply_text(
            "Фото получено. Теперь отправьте состав и цены в формате:\n"
            "50: 28, 1, ...\n40: ...\nВсего должно быть 20 записей."
        )
        return FCT_ROSTER
    except Exception as e:
        await update.message.reply_text(f"Не удалось обработать изображение: {e}")
        return ConversationHandler.END


async def roster(update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    pairs = []
    try:
        for line in lines:
            if ':' not in line:
                await update.message.reply_text(f"Неверный формат строки: {line}")
                return FCT_ROSTER
            cost_str, ids_str = line.split(':', 1)
            cost = int(cost_str.strip())
            id_list = [int(x.strip()) for x in ids_str.split(',') if x.strip()]
            for pid in id_list:
                pairs.append((cost, pid))
    except Exception as e:
        await update.message.reply_text(f"Ошибка парсинга: {e}")
        return FCT_ROSTER
    if len(pairs) != 20:
        await update.message.reply_text(f"Ошибка: нужно ровно 20 игроков, а сейчас {len(pairs)}. Попробуйте снова.")
        return FCT_ROSTER
    for cost, pid in pairs:
        player = db.get_player_by_id(pid)
        if not player:
            await update.message.reply_text(f"Игрок с id {pid} не найден! Попробуйте снова.")
            return FCT_ROSTER
    try:
        tour_id = int(context.user_data.get('ct_tour_id') or 0)
        if tour_id:
            db.clear_tour_players(tour_id)
            for cost, pid in pairs:
                db.add_tour_player(tour_id, pid, cost)
            try:
                db.clear_tour_roster()
                for cost, pid in pairs:
                    db.add_tour_roster_entry(pid, cost)
            except Exception:
                pass
        else:
            await update.message.reply_text("Внутренняя ошибка: tour_id отсутствует.")
            return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"Не удалось сохранить состав: {e}")
        return ConversationHandler.END
    tour_id = context.user_data.get('ct_tour_id')
    name = context.user_data.get('ct_name')
    start = context.user_data.get('ct_start')
    deadline = context.user_data.get('ct_deadline')
    end = context.user_data.get('ct_end')
    await update.message.reply_text(
        "Тур успешно создан!\n"
        f"ID: {tour_id}\nНазвание: {name}\nСтарт: {start}\nДедлайн: {deadline}\nОкончание: {end}\n"
        f"Изображение: {context.user_data.get('ct_image_filename', '-')}."
    )
    for k in ['ct_name', 'ct_start', 'ct_deadline', 'ct_end', 'ct_image_filename', 'ct_tour_id']:
        context.user_data.pop(k, None)
    return ConversationHandler.END


async def cancel(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Создание тура отменено.")
    for k in ['ct_name', 'ct_start', 'ct_deadline', 'ct_end', 'ct_image_filename', 'ct_tour_id']:
        context.user_data.pop(k, None)
    return ConversationHandler.END

