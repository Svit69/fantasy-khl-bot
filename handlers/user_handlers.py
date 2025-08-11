from telegram import Update, InputFile, ReplyKeyboardMarkup, MessageEntity, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import BadRequest
from telegram.constants import MessageEntityType
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
import db
import os
from utils import is_admin, IMAGES_DIR, logger, CHALLENGE_IMAGE_PATH_FILE

def escape_md(text):
    # Все спецсимволы MarkdownV2
    for ch in r'\_*[]()~`>#+-=|{}.!':
        text = text.replace(ch, '\\' + ch)
    return text

async def send_player_selected_message(query, player, budget, context):
    left = budget - context.user_data['tour_selected']['spent']
    player_name = escape_md(str(player[2]))
    cost = escape_md(str(player[7]))
    left_str = escape_md(str(left))
    msg = f'Вы выбрали {player_name} \\({cost}\\)\n\n*Оставшийся бюджет: {left_str}*'
    await query.edit_message_text(msg, parse_mode="MarkdownV2")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Универсально получаем message для reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message
    user = update.effective_user
    registered = db.register_user(user.id, user.username, user.full_name)

    # --- Реферал: если пользователь пришёл по ссылке ref_<id>,
    # и это его ПЕРВАЯ регистрация (registered == True), начисляем рефереру +50 HC
    try:
        if registered and getattr(context, 'args', None):
            arg0 = context.args[0] if len(context.args) > 0 else ''
            if isinstance(arg0, str) and arg0.startswith('ref_'):
                ref_str = arg0[4:]
                if ref_str.isdigit():
                    referrer_id = int(ref_str)
                    if referrer_id != user.id:
                        # Вставим запись реферала, если для этого user_id её ещё не было
                        if db.add_referral_if_new(user.id, referrer_id):
                            # Бонус зависит от активности подписки у реферера
                            try:
                                from db import is_subscription_active
                                bonus = 100 if is_subscription_active(referrer_id) else 50
                            except Exception:
                                bonus = 50
                            db.update_hc_balance(referrer_id, bonus)
                            # Уведомим реферера (если можно)
                            try:
                                new_balance = db.get_user_by_id(referrer_id)
                                new_balance = new_balance[3] if new_balance else '—'
                                await context.bot.send_message(
                                    chat_id=referrer_id,
                                    text=f'🎉 По вашей реферальной ссылке зарегистрировался новый участник!\n+{bonus} HC начислено. Текущий баланс: {new_balance} HC.'
                                )
                            except Exception:
                                pass
                            # Сообщим пользователю, что он пришёл по ссылке
                            try:
                                await message.reply_text('Вы зарегистрировались по реферальной ссылке — добро пожаловать!')
                            except Exception:
                                pass
    except Exception as e:
        # Не прерываем старт при ошибке реферальной обработки
        try:
            await message.reply_text(f"[WARN] Ошибка обработки реферала: {e}")
        except Exception:
            pass
    msg_id = f"Ваш Telegram ID: {user.id}\n"
    if is_admin(user.id):
        keyboard = [["/tour", "/hc"], ["/send_tour_image", "/addhc", "/send_results", "/add_player", "/list_players"]]
        msg = (
            f'Привет, {user.full_name}! Ты зарегистрирован как администратор Fantasy KHL.\n\n'
            'Доступные команды:\n/tour — показать состав на тур\n/hc — баланс HC\n/send_tour_image — загрузить и разослать изображение тура\n/addhc — начислить HC пользователю\n/send_results — разослать результат тура\n/add_player — добавить игрока\n/list_players — список игроков'
        )
    else:
        keyboard = [["/tour", "/hc", "/rules", "/shop"]]
        msg = (
            f'Привет, {user.full_name}! Добро пожаловать в Фентези Драфт КХЛ\n\n'
            '🔸 Собирай свою команду на каждый тур\n'
            '🔸 Следи за результатами туров\n'
            '🔸 Зарабатывай и копи Hockey Coin (HC)\n'
            '🔸 Меняй Hockey Coin (HC) на призы\n\n'
            'Доступные команды:\n'
            '/tour — тур и управление командой\n'
            '/hc — твой баланс Hockey Coin\n'
            '/rules — правила сборки составов\n'
            '/shop — магазин призов'
        )
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    if registered:
        await message.reply_text(msg_id + msg, reply_markup=markup)
    else:
        await message.reply_text(
            escape_md("⚠️ Ты уже в списке генеральных менеджеров Фентези Драфта КХЛ.\n\nФормируй состав и следи за результатами туров - /tour"),
            reply_markup=markup,
            parse_mode="MarkdownV2"
        )

# --- TOUR ConversationHandler states ---

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    # Определим текущий бонус: 100 HC при активной подписке, иначе 50 HC
    try:
        from db import is_subscription_active
        bonus = 100 if is_subscription_active(user.id) else 50
    except Exception:
        bonus = 50
    text = (
        f"🔗 Ваша реферальная ссылка:\n"
        f"{link}\n\n"
        f"Приглашайте друзей! За каждого нового участника вы получите +{bonus} HC после его регистрации."
    )
    keyboard = [[InlineKeyboardButton('Скопировать ссылку', url=link)]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from utils import create_yookassa_payment
    user = update.effective_user
    payment_url, payment_id = create_yookassa_payment(user.id)
    # Сохраняем payment_id в БД (можно добавить функцию)
    # db.save_payment_id(user.id, payment_id)
    text = (
        f"💳 <b>Подписка на Fantasy KHL</b>\n\n"
        f"Стоимость: <b>299 руб/месяц</b>\n\n"
        f"Нажмите кнопку ниже для оплаты через ЮKassa. После успешной оплаты подписка активируется автоматически."
    )
    keyboard = [[InlineKeyboardButton('Оплатить 299₽ через ЮKassa', url=payment_url)]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# --- CHALLENGE ---
async def challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    # Только для подписчиков
    try:
        from db import is_subscription_active
        if not is_subscription_active(user.id):
            await update.message.reply_text("Функция доступна только подписчикам. Оформите подписку: /subscribe")
            return
    except Exception:
        await update.message.reply_text("Не удалось проверить подписку. Попробуйте позже или оформите /subscribe.")
        return

    # Список доступных челленджей: все со статусом "активен" и "в игре". Если таких нет — показать последний "завершен".
    challenges = []
    try:
        challenges = db.get_all_challenges() or []
    except Exception:
        challenges = []

    active_or_play = [c for c in challenges if len(c) > 5 and c[5] in ("активен", "в игре")]
    last_finished = None
    if challenges:
        # выбрать последний завершенный по end_date
        try:
            import datetime
            finished = [c for c in challenges if len(c) > 5 and c[5] == "завершен"]
            def parse_iso(s):
                try:
                    return datetime.datetime.fromisoformat(str(s))
                except Exception:
                    return datetime.datetime.min
            if finished:
                last_finished = sorted(finished, key=lambda c: parse_iso(c[3]) or datetime.datetime.min)[-1]
        except Exception:
            pass

    list_to_show = active_or_play if active_or_play else ([last_finished] if last_finished else [])

    if not list_to_show:
        await update.message.reply_text("Сейчас нет доступных челленджей. Загляните позже.")
        return

    lines = ["*Доступные челленджи:*"]
    # Вспомогательная функция: ISO -> текст в МСК (Europe/Moscow)
    def iso_to_msk_text(dt_str: str) -> str:
        import datetime as _dt
        months = [
            "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"
        ]
        if not dt_str:
            return ""
        try:
            dt = _dt.datetime.fromisoformat(str(dt_str))
        except Exception:
            return str(dt_str)
        # Считаем, что хранимое время — UTC (наивное -> проставим UTC)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        else:
            dt = dt.astimezone(_dt.timezone.utc)
        # Перевод в МСК
        try:
            from zoneinfo import ZoneInfo  # Python 3.9+
            msk = dt.astimezone(ZoneInfo("Europe/Moscow"))
        except Exception:
            # Фолбэк: фиксированный UTC+3 (Москва без перехода)
            msk = dt.astimezone(_dt.timezone(_dt.timedelta(hours=3)))
        day = msk.day
        month_name = months[msk.month - 1]
        time_part = msk.strftime("%H:%M")
        return f"{day} {month_name} {time_part} (мск)"
    buttons = []
    for c in list_to_show:
        # c: (id, start, deadline, end, image_filename, status, [image_file_id])
        cid = c[0]
        deadline = c[2]
        end = c[3]
        status = c[5] if len(c) > 5 else ''
        if status == 'завершен':
            line = f"🔺 №{cid} [завершен] посмотреть результаты"
        elif status == 'в игре':
            line = f"🔹 №{cid} [начался] подведение итогов: {iso_to_msk_text(end)}"
        elif status == 'активен':
            line = f"🔸 №{cid} [сбор составов] дедлайн сборки состава: {iso_to_msk_text(deadline)}"
        else:
            line = f"№{cid} [{status}]"
        lines.append(line)
        buttons.append([InlineKeyboardButton(f"Открыть #{cid}", callback_data=f"challenge_open_{cid}")])

    await update.message.reply_text("\n\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')


async def challenge_open_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    try:
        cid = int(data.replace("challenge_open_", ""))
    except Exception:
        await query.edit_message_text("Некорректный выбор челленджа.")
        return

    # Найдем челлендж по id
    ch = None
    try:
        rows = db.get_all_challenges() or []
        for r in rows:
            if r[0] == cid:
                ch = r
                break
    except Exception:
        ch = None
    if not ch:
        await query.edit_message_text("Челлендж не найден.")
        return

    # Попробуем отправить картинку челленджа как фото
    image_sent = False
    image_file_id = ch[6] if len(ch) >= 7 else ''
    if image_file_id:
        try:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_file_id)
            image_sent = True
        except Exception:
            logger.warning("send_photo by file_id failed in open_callback", exc_info=True)
    if not image_sent:
        try:
            fname = ch[4] if len(ch) > 4 else ''
            if fname:
                fpath = os.path.join(IMAGES_DIR, fname)
                if os.path.exists(fpath):
                    with open(fpath, 'rb') as fp:
                        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=InputFile(fp, filename=fname))
                        image_sent = True
        except Exception:
            logger.error("send_photo from local file failed in open_callback", exc_info=True)

    # Меню действий по челленджу
    status = ch[5] if len(ch) > 5 else ''
    text = (
        f"Челлендж #{ch[0]}\n"
        f"Статус: {status}\n"
        f"Старт: {ch[1]}\nДедлайн: {ch[2]}\nОкончание: {ch[3]}"
    )
    buttons = [[InlineKeyboardButton("Инфо", callback_data=f"challenge_info_{ch[0]}")]]
    if status == "активен":
        buttons.append([InlineKeyboardButton("Собрать состав", callback_data=f"challenge_build_{ch[0]}")])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=InlineKeyboardMarkup(buttons))


async def challenge_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        cid = int(query.data.replace("challenge_info_", ""))
    except Exception:
        await query.edit_message_text("Некорректный запрос.")
        return
    # Найдем челлендж
    ch = None
    try:
        rows = db.get_all_challenges() or []
        for r in rows:
            if r[0] == cid:
                ch = r
                break
    except Exception:
        ch = None
    if not ch:
        await query.edit_message_text("Челлендж не найден.")
        return
    status = ch[5] if len(ch) > 5 else ''
    txt = (
        f"Информация по челленджу #{ch[0]}\n"
        f"Статус: {status}\n"
        f"Старт: {ch[1]}\nДедлайн: {ch[2]}\nОкончание: {ch[3]}\n\n"
        f"Если статус 'активен' — можете собрать состав."
    )
    await query.edit_message_text(txt)

def _parse_shop_items(text: str):
    items = []
    if not text:
        return items
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        if not (line.startswith('🔸') or line.startswith('•') or line.startswith('-')):
            continue
        # Убираем маркер
        raw = line.lstrip('🔸').lstrip('•').lstrip('-').strip()
        # Разделитель — может быть длинное тире или дефис
        sep = '—' if '—' in raw else (' - ' if ' - ' in raw else '-')
        if sep not in raw:
            # Пропускаем некорректные строки
            continue
        name, price = raw.split(sep, 1)
        name = name.strip()
        price = price.strip()
        if name:
            items.append((name, price))
    return items

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать содержимое магазина: текст + картинка + инлайн-кнопки товаров."""
    try:
        text, image_filename, image_file_id = db.get_shop_content()
    except Exception as e:
        await update.message.reply_text(f"Ошибка получения данных магазина: {e}")
        return
    if not text and not image_filename and not image_file_id:
        await update.message.reply_text("Магазин пока пуст. Загляните позже.")
        return
    # Построим инлайн-кнопки из текста
    items = _parse_shop_items(text or '')
    buttons = []
    for idx, (name, price) in enumerate(items, start=1):
        label = f"{name} — {price}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"shop_item_{idx}")])
    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    caption = text if text else None
    # Попытаемся отправить фото по file_id
    if image_file_id:
        try:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_file_id, caption=caption, reply_markup=reply_markup)
            return
        except Exception:
            logger.warning("send_photo by file_id failed in /shop", exc_info=True)
    # Попробуем отправить локальный файл
    if image_filename:
        fpath = os.path.join(IMAGES_DIR, image_filename)
        if os.path.exists(fpath):
            try:
                with open(fpath, 'rb') as fp:
                    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=InputFile(fp, filename=image_filename), caption=caption, reply_markup=reply_markup)
                    return
            except Exception:
                logger.error("send_photo from local file failed in /shop", exc_info=True)
    # Если фото не получилось — отправим просто текст
    if caption:
        await update.message.reply_text(caption, reply_markup=reply_markup)
    else:
        await update.message.reply_text("Магазин недоступен.")

async def shop_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # shop_item_<n>
    try:
        await query.edit_message_reply_markup(reply_markup=query.message.reply_markup)
    except BadRequest as e:
        # Игнорируем 'Message is not modified'
        if 'Message is not modified' not in str(e):
            raise
    try:
        idx = int(data.replace('shop_item_', ''))
    except Exception:
        idx = None
    # Получим список товаров заново из БД
    try:
        text, _, _ = db.get_shop_content()
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Ошибка чтения магазина: {e}")
        return
    items = _parse_shop_items(text or '')
    if not idx or idx < 1 or idx > len(items):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Некорректный выбор товара.")
        return
    name, price_str = items[idx - 1]
    # Извлечём число из строки цены (например, '35 000 HC' -> 35000)
    digits = ''.join(ch for ch in price_str if ch.isdigit())
    try:
        price = int(digits) if digits else 0
    except Exception:
        price = 0
    # Баланс пользователя
    user = update.effective_user
    balance = 0
    try:
        row = db.get_user_by_id(user.id)
        if row and len(row) > 3 and isinstance(row[3], (int, float)):
            balance = int(row[3])
        elif row and len(row) > 3:
            # На случай, если хранится строкой
            try:
                balance = int(str(row[3]))
            except Exception:
                balance = 0
    except Exception:
        balance = 0
    if price <= 0:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Товар: {name}\nЦена: {price_str}\n\nНе удалось распознать цену. Свяжитесь с администратором.")
        return
    if balance < price:
        need = price - balance
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"Товар: {name}\nЦена: {price_str}\n\n"
                f"Недостаточно средств: не хватает {need} HC.\n"
                f"Вы можете подключить подписку /subscribe за 299 руб/месяц, чтобы быстрее накапливать HC."
            )
        )
        return
    # Баланса достаточно — подтверждаем и уведомляем админа
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"Товар: {name}\nЦена: {price_str}\n\n"
            f"У вас достаточно HC (баланс: {balance} HC). Подтверждение и оформление заказа скоро добавим."
        )
    )
    # Уведомление админа(ов)
    try:
        admin_text = (
            "🛒 Запрос на покупку\n\n"
            f"Пользователь: {user.full_name} (@{user.username or '-'}, id={user.id})\n"
            f"Товар: {name}\n"
            f"Цена: {price_str}\n"
            f"Баланс: {balance} HC\n"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text)
    except Exception:
        logger.warning("Failed to notify admin about shop purchase", exc_info=True)


async def challenge_build_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        cid = int(query.data.replace("challenge_build_", ""))
    except Exception:
        await query.edit_message_text("Некорректный запрос.")
        return
    # Проверим, что выбранный челлендж активен
    ch = None
    try:
        rows = db.get_all_challenges() or []
        for r in rows:
            if r[0] == cid:
                ch = r
                break
    except Exception:
        ch = None
    if not ch:
        await query.edit_message_text("Челлендж не найден.")
        return
    status = ch[5] if len(ch) > 5 else ''
    if status != "активен":
        await query.edit_message_text("Сбор состава недоступен: челлендж не активен.")
        return

    # Переиспользуем текущую механику: выбор уровня вызова
    text = (
        "Выберите уровень вызова для челленджа:\n\n"
        "⚡️ 50 HC\n⚡️ 100 HC\n⚡️ 500 HC"
    )
    keyboard = [
        [
            InlineKeyboardButton('⚡️ 50 HC', callback_data='challenge_level_50'),
            InlineKeyboardButton('⚡️ 100 HC', callback_data='challenge_level_100'),
            InlineKeyboardButton('⚡️ 500 HC', callback_data='challenge_level_500'),
        ]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def challenge_level_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    level = data.replace('challenge_level_', '')
    try:
        level_int = int(level)
    except Exception:
        await query.edit_message_text("Некорректный уровень вызова.")
        return
    user = update.effective_user
    user_row = db.get_user_by_id(user.id)
    balance = user_row[3] if user_row else 0
    if balance < level_int:
        text = (
            f"Недостаточно HC для уровня {level_int} HC.\n"
            f"Текущий баланс: {balance} HC.\n\n"
            "Выберите доступный уровень вызова:"
        )
        keyboard = [
            [
                InlineKeyboardButton('⚡️ 50 HC', callback_data='challenge_level_50'),
                InlineKeyboardButton('⚡️ 100 HC', callback_data='challenge_level_100'),
                InlineKeyboardButton('⚡️ 500 HC', callback_data='challenge_level_500'),
            ]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    # Баланс достаточен — фиксируем выбор
    context.user_data['challenge_level'] = level_int
    await query.edit_message_text(
        f"Уровень вызова выбран: {level_int} HC. Баланс: {balance} HC. Теперь выбери трёх игроков (функция подготавливается)."
    )


TOUR_START, TOUR_FORWARD_1, TOUR_FORWARD_2, TOUR_FORWARD_3, TOUR_DEFENDER_1, TOUR_DEFENDER_2, TOUR_GOALIE, TOUR_CAPTAIN, PREMIUM_TEAM, PREMIUM_POSITION = range(10)

async def tour_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем объект сообщения для ответа (универсально для Update и CallbackQuery)
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message

    # Проверяем активную подписку
    try:
        from db import is_subscription_active
        user = update.effective_user
        if not is_subscription_active(user.id):
            await message.reply_text(
                "Подписка не активна. Оформите или продлите подписку командой /subscribe, затем повторите попытку."
            )
            return ConversationHandler.END
    except Exception:
        # При ошибке проверки не блокируем, но даём подсказку
        try:
            await message.reply_text("Не удалось проверить подписку. Если доступ ограничен, используйте /subscribe.")
        except Exception:
            pass

    # --- Определяем активный тур ---
    from db import get_active_tour
    active_tour = get_active_tour()
    if not active_tour:
        await message.reply_text("Нет активного тура для сбора состава. Обратитесь к администратору.")
        return ConversationHandler.END
async def tour_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    # Получаем объект сообщения для ответа (универсально для Update и CallbackQuery)
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message

    # --- Определяем активный тур ---
    from db import get_active_tour, get_user_tour_roster, get_player_by_id
    active_tour = get_active_tour()
    if not active_tour:
        await message.reply_text("Нет активного тура для сбора состава. Обратитесь к администратору.")
        return ConversationHandler.END
    context.user_data['active_tour_id'] = active_tour['id']

    user_id = update.effective_user.id
    tour_id = active_tour['id']
    user_roster = get_user_tour_roster(user_id, tour_id)
    if user_roster and user_roster.get('roster'):
        # Форматируем состав для вывода
        def format_user_roster_md(roster_data):
            from utils import escape_md
            roster = roster_data['roster']
            captain_id = roster_data.get('captain_id')
            spent = roster_data.get('spent', 0)
            # Получаем инфу по игрокам
            goalie = get_player_by_id(roster.get('goalie'))
            defenders = [get_player_by_id(pid) for pid in roster.get('defenders', [])]
            forwards = [get_player_by_id(pid) for pid in roster.get('forwards', [])]
            def fmt(p):
                if not p: return "-"
                return f"{p[1]} ({p[3]})"
            g_str = escape_md(fmt(goalie))
            d_str = escape_md(f"{fmt(defenders[0])} - {fmt(defenders[1])}") if len(defenders) == 2 else "-"
            f_str = escape_md(f"{fmt(forwards[0])} - {fmt(forwards[1])} - {fmt(forwards[2])}") if len(forwards) == 3 else "-"
            captain = None
            for p in [goalie] + defenders + forwards:
                if p and p[0] == captain_id:
                    captain = fmt(p)
            cap_str = f"Капитан: {escape_md(captain)}" if captain else "Капитан: -"
            lines = [
                '*Ваш сохранённый состав:*',
                '',
                g_str,
                d_str,
                f_str,
                '',
                cap_str,
                f'Потрачено: *{escape_md(str(spent))}* HC'
            ]
            return '\n'.join(lines)

        text = format_user_roster_md(user_roster)
        keyboard = [[InlineKeyboardButton('Пересобрать состав', callback_data='restart_tour')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(text, reply_markup=reply_markup, parse_mode="MarkdownV2")
        return ConversationHandler.END

    # --- Если состава нет, запускаем обычный сценарий выбора ---
    # 1. Отправить картинку тура и вводный текст с бюджетом
    budget = db.get_budget() or 0
    roster = db.get_tour_roster_with_player_info()
    forwards = [p for p in roster if p[3].lower() == 'нападающий']
    defenders = [p for p in roster if p[3].lower() == 'защитник']
    goalies = [p for p in roster if p[3].lower() == 'вратарь']
    context.user_data['tour_budget'] = budget
    context.user_data['tour_roster'] = roster
    context.user_data['tour_selected'] = {
        'forwards': [],
        'defenders': [],
        'goalie': None,
        'captain': None,
        'spent': 0
    }
    context.user_data['tour_selected'] = {'forwards': [], 'defenders': [], 'goalie': None, 'captain': None, 'spent': 0}
    # Отправить картинку (если есть)
    try:
        tour_img_path = None
        tour_img_txt = os.path.join(os.getcwd(), 'latest_tour.txt')
        if os.path.exists(tour_img_txt):
            with open(tour_img_txt, 'r') as f:
                fname = f.read().strip()
                if fname:
                    fpath = os.path.join(IMAGES_DIR, fname)
                    if os.path.exists(fpath):
                        tour_img_path = fpath
        if not tour_img_path:
            # fallback: last by name
            files = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
            if files:
                tour_img_path = os.path.join(IMAGES_DIR, sorted(files)[-1])
        if tour_img_path:
            with open(tour_img_path, 'rb') as img:
                await update.message.reply_photo(photo=InputFile(img))
    except Exception as e:
        logger.error(f'Ошибка при отправке изображения тура: {e}')
    # Вводный текст
    # Формируем строку дедлайна
    deadline = active_tour.get('deadline', '')
    deadline_str = str(deadline).replace('.', '\\.')
    # Формируем красивый текст с MarkdownV2
    intro = rf"""*Список игроков на текущий тур\!* Выбери к себе в состав:
🔸3 нападающих
🔸2 защитников
🔸1 вратаря

Назначь одного полевого игрока из состава капитаном \(его очки умножим на х1\.5\)

*Ваш бюджет: {budget}*

Принимаем составы до: {deadline_str}"""

    # Если у пользователя активная подписка — добавим блок про премиум
    try:
        from db import is_subscription_active
        if is_subscription_active(update.effective_user.id):
            premium_line = "\n\n💎  Премиум: у тебя доступен персональный бонус — \\+1 игрок в пул \\(" \
                           "+ доступно: 1/1 \\) Выбирай с умом!"
            # Исправим строку на корректную без конкатенации для читаемости
            premium_line = "\n\n💎  Премиум: у тебя доступен персональный бонус — \\+1 игрок в пул \\(" \
                           "доступно: 1/1\\) Выбирай с умом\\!"
            intro = intro + premium_line
    except Exception:
        pass

    await message.reply_text(intro, parse_mode="MarkdownV2")
    # Для премиум-пользователей — показать кнопку активации бонуса
    try:
        from db import is_subscription_active
        if is_subscription_active(update.effective_user.id):
            print("[DEBUG] tour_start: user has active subscription, showing premium button")
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton('Добавить игрока в пул', callback_data='premium_add_pool')]]
            )
            sent = await message.reply_text('💎 Премиум-опция', reply_markup=kb)
            try:
                # Запомним для диагностики id сообщения с премиум-кнопкой
                context.user_data['premium_button_chat_id'] = sent.chat_id
                context.user_data['premium_button_message_id'] = sent.message_id
                print(f"[DEBUG] tour_start: premium button message_id={sent.message_id}")
            except Exception as e:
                print(f"[WARN] tour_start: failed to store premium button ids: {e}")
    except Exception:
        pass
    # Сразу показываем выбор первого нападающего!
    return await tour_forward_1(update, context)


async def premium_add_pool_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Обработка нажатия премиум-кнопки: фиксируем флаг в user_data
    query = update.callback_query
    try:
        print(f"[DEBUG] premium_add_pool_callback: received callback data={query.data}")
    except Exception:
        pass
    await query.answer()
    try:
        from db import is_subscription_active
        if not is_subscription_active(update.effective_user.id):
            print("[DEBUG] premium_add_pool_callback: subscription inactive")
            await query.message.reply_text("Премиум недоступен. Оформите /subscribe, чтобы активировать бонус.")
            return TOUR_FORWARD_1
    except Exception:
        print("[WARN] premium_add_pool_callback: failed to check subscription")
    # Установим флаги премиум-режима: добавление в пул (без автодобавления в состав)
    context.user_data['premium_extra_available'] = True
    context.user_data['premium_mode'] = 'add_to_pool'
    print("[DEBUG] premium_add_pool_callback: premium_extra_available=True set")
    # Удалим предыдущее сообщение с выбором игроков, если сохранено
    try:
        chat_id = context.user_data.get('last_choice_chat_id')
        msg_id = context.user_data.get('last_choice_message_id')
        if chat_id and msg_id:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            print(f"[DEBUG] premium_add_pool_callback: deleted last choice message id={msg_id}")
            # Очистим сохранённые значения
            context.user_data.pop('last_choice_chat_id', None)
            context.user_data.pop('last_choice_message_id', None)
    except Exception:
        print("[WARN] premium_add_pool_callback: failed to delete last choice message")
    # Также удалим сообщение с самой премиум-кнопкой
    try:
        await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
        print(f"[DEBUG] premium_add_pool_callback: deleted premium button message id={query.message.message_id}")
    except Exception:
        print("[WARN] premium_add_pool_callback: failed to delete premium button message")
    await query.message.reply_text("💎 Персональный бонус активирован: +1 игрок в пул.\n\nНапишите команду игрока")
    return PREMIUM_TEAM


async def premium_team_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем текст команды и просим выбрать позицию
    team_text = update.message.text.strip()
    context.user_data['premium_team_query'] = team_text
    try:
        print(f"[DEBUG] premium_team_input: received team text='{team_text}'")
    except Exception:
        pass
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton('нападающий', callback_data='premium_pos_нападающий')],
        [InlineKeyboardButton('защитник', callback_data='premium_pos_защитник')],
        [InlineKeyboardButton('вратарь', callback_data='premium_pos_вратарь')],
    ])
    await update.message.reply_text('Выберите позицию игрока', reply_markup=kb)
    return PREMIUM_POSITION


async def premium_position_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    pos = data.replace('premium_pos_', '')
    context.user_data['premium_position'] = pos
    print(f"[DEBUG] premium_position_selected: pos={pos}")
    # Покажем список игроков, отфильтрованных по команде и позиции (ИЗ ВСЕЙ БАЗЫ ИГРОКОВ)
    try:
        team_text = (context.user_data.get('premium_team_query') or '').strip().lower()
        from db import get_all_players
        all_players = get_all_players()  # (id, name, position, club, nation, age, price)
        budget = context.user_data.get('tour_budget', 0)
        spent = context.user_data.get('tour_selected', {}).get('spent', 0)
        left = max(0, budget - spent)
        # Исключения по уже выбранным
        selected = context.user_data.get('tour_selected', {})
        exclude_ids = []
        next_state = TOUR_FORWARD_1
        if pos == 'нападающий':
            exclude_ids = selected.get('forwards', [])
            next_state = TOUR_FORWARD_1
        elif pos == 'защитник':
            exclude_ids = selected.get('defenders', [])
            # Выберем подходящее состояние в зависимости от уже выбранных
            next_state = TOUR_DEFENDER_1 if len(exclude_ids) == 0 else TOUR_DEFENDER_2
        elif pos == 'вратарь':
            gid = selected.get('goalie')
            exclude_ids = [gid] if gid else []
            next_state = TOUR_GOALIE
        # Фильтрация по позиции, команде, бюджету и исключениям
        def team_match(t):
            try:
                return team_text in str(t or '').lower()
            except Exception:
                return False
        # Исключим игроков, уже включённых в туровый ростер
        tour_roster = context.user_data.get('tour_roster', [])
        tour_ids = set([tr[1] for tr in tour_roster])  # p.id из турового списка
        # Индексы в players: 0-id,1-name,2-position,3-club,6-price
        filtered = [
            p for p in all_players
            if p[2].lower() == pos
            and p[0] not in exclude_ids
            and p[0] not in tour_ids
            and (p[6] or 0) <= left
            and team_match(p[3])
        ]
        print(f"[DEBUG] premium_position_selected: team='{team_text}', found={len(filtered)} players in DB (excluding tour roster), left={left}")
        if not filtered:
            await query.message.reply_text("По заданным фильтрам игроков не найдено. Измените команду или позицию.")
            return next_state
        # Построим клавиатуру
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = []
        for p in filtered:
            btn_text = f"{p[1]} — {p[6]} HC"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pick_{p[0]}_{pos}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = f"Найденные игроки ({pos}, команда содержит: '{team_text}') — осталось HC: {left}"
        sent = await query.message.reply_text(text, reply_markup=reply_markup)
        # Сохраним, чтобы мочь удалить далее при необходимости
        try:
            context.user_data['last_choice_chat_id'] = sent.chat_id
            context.user_data['last_choice_message_id'] = sent.message_id
        except Exception:
            pass
        return next_state
    except Exception as e:
        print(f"[ERROR] premium_position_selected building list: {e}")
        await query.message.reply_text(f"Ошибка построения списка: {e}")
        return TOUR_FORWARD_1

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

async def send_player_choice(update, context, position, exclude_ids, next_state, budget):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    # Универсально получаем message для reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message
    # Получаем актуальный ростер
    roster = context.user_data['tour_roster']
    # Фильтруем по позиции и исключениям
    players = [p for p in roster if p[3].lower() == position and p[1] not in exclude_ids and p[7] <= budget]
    if not players:
        # Проверка: если не хватает HC для обязательного выбора
        text = (
            '🚨 Вы привысили потолок зарплат. Пересоберите состав, чтобы вписаться в лимит.'
        )
        keyboard = [
            [InlineKeyboardButton('Пересобрать состав', callback_data='restart_tour')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(text, reply_markup=reply_markup)
        return ConversationHandler.END
    keyboard = []
    for p in players:
        btn_text = f"{p[2]} — {p[7]} HC"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pick_{p[1]}_{position}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Выберите {position} (осталось HC: {budget})"
    sent_msg = await message.reply_text(text, reply_markup=reply_markup)
    # Запомним последнее сообщение с выбором, чтобы мочь удалить при активации премиум-режима
    try:
        context.user_data['last_choice_chat_id'] = sent_msg.chat_id
        context.user_data['last_choice_message_id'] = sent_msg.message_id
    except Exception:
        pass
    return next_state
    keyboard = []
    for p in players:
        btn_text = f"{p[2]} — {p[7]} HC"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pick_{p[1]}_{position}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Выберите {position} (осталось HC: {budget})"
    await message.reply_text(text, reply_markup=reply_markup)
    return next_state

async def tour_forward_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    picked = context.user_data['tour_selected']['forwards']
    return await send_player_choice(update, context, 'нападающий', picked, TOUR_FORWARD_2, budget)


async def tour_forward_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data
        print(f"Callback data: {data}", flush=True)
        # Ожидается формат pick_<player_id>_нападающий
        if not data.startswith('pick_') or '_нападающий' not in data:
            await query.edit_message_text('Некорректный выбор.')
            return TOUR_FORWARD_1
        pid = int(data.split('_')[1])
        # Получаем игрока по id
        roster = context.user_data['tour_roster']
        player = next((p for p in roster if p[1] == pid), None)
        added_personal = False
        if not player:
            # Fallback: ищем в общей БД игроков
            try:
                pdb = db.get_player_by_id(pid)
                if pdb:
                    # Преобразуем к формату: (tr.cost, p.id, p.name, p.position, p.club, p.nation, p.age, p.price)
                    player = (pdb[6], pdb[0], pdb[1], pdb[2], pdb[3], pdb[4], pdb[5], pdb[6])
                    # Добавим этого игрока в персональный туровый список пользователя, если ещё нет
                    try:
                        if not any(p_[1] == pdb[0] for p_ in roster):
                            context.user_data['tour_roster'].append(player)
                        added_personal = True
                        # Пометим использование премиум-бонуса
                        context.user_data['premium_extra_available'] = False
                    except Exception:
                        pass
                else:
                    await query.edit_message_text('Игрок не найден.')
                    return TOUR_FORWARD_1
            except Exception:
                await query.edit_message_text('Игрок не найден.')
                return TOUR_FORWARD_1
        # Если активен режим добавления в пул — не добавляем в состав, а только расширяем пул
        if context.user_data.get('premium_mode') == 'add_to_pool':
            try:
                # Убедимся, что игрок есть в персональном пуле
                roster = context.user_data['tour_roster']
                if not any(p_[1] == player[1] for p_ in roster):
                    context.user_data['tour_roster'].append(player)
                # Выключаем режим и сжигаем бонус
                context.user_data['premium_mode'] = None
                context.user_data['premium_extra_available'] = False
                # Покажем обычный выбор нападающих с учётом расширенного пула
                budget = context.user_data['tour_budget']
                spent = context.user_data['tour_selected']['spent']
                left = budget - spent
                picked = context.user_data['tour_selected']['forwards']
                await query.edit_message_text(f"Добавлен в ваш пул: {player[2]} ({player[4]}). Теперь выберите нападающего.")
                next_state = TOUR_FORWARD_2 if len(picked) == 0 else TOUR_FORWARD_3
                return await send_player_choice(update, context, 'нападающий', picked, next_state, left)
            except Exception as e:
                await query.edit_message_text(f"Ошибка добавления в пул: {e}")
                return TOUR_FORWARD_1
        # Проверяем бюджет
        budget = context.user_data['tour_budget']
        spent = context.user_data['tour_selected']['spent']
        if spent + player[7] > budget:
            await query.edit_message_text(f'Недостаточно HC для выбора {player[1]}!')
            return TOUR_FORWARD_1
        # Сохраняем выбор
        context.user_data['tour_selected']['forwards'].append(pid)
        context.user_data['tour_selected']['spent'] += player[7]
        left = budget - context.user_data['tour_selected']['spent']
        player_name = escape_md(str(player[2]))
        cost = escape_md(str(player[7]))
        left_str = escape_md(str(left))
        msg = f'Вы выбрали {player_name} \\({cost}\\)\n\n*Оставшийся бюджет: {left_str}*'
        await query.edit_message_text(msg, parse_mode="MarkdownV2")
        if len(context.user_data['tour_selected']['forwards']) == 1:
            print("tour_forward_callback SUCCESS: переход к tour_forward_2", flush=True)
            return await tour_forward_2(update, context)
        elif len(context.user_data['tour_selected']['forwards']) == 2:
            print("tour_forward_callback SUCCESS: переход к tour_forward_3", flush=True)
            return await tour_forward_3(update, context)
        elif len(context.user_data['tour_selected']['forwards']) == 3:
            print("tour_forward_callback SUCCESS: переход к tour_defender_1", flush=True)
            await tour_defender_1(update, context)
            return TOUR_DEFENDER_1
    except Exception as e:
        print(f"tour_forward_callback ERROR: {e}", flush=True)
        logger.exception("Exception in tour_forward_callback")
        await query.edit_message_text(f"Ошибка: {e}")
        return TOUR_FORWARD_1
    finally:
        print("tour_forward_callback FINISHED", flush=True)


async def tour_forward_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = context.user_data['tour_selected']['forwards']
    return await send_player_choice(update, context, 'нападающий', picked, TOUR_FORWARD_3, left)


async def tour_forward_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = context.user_data['tour_selected']['forwards']
    # Показываем клавиатуру для третьего нападающего, next_state — TOUR_FORWARD_3
    return await send_player_choice(update, context, 'нападающий', picked, TOUR_FORWARD_3, left)

async def tour_defender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data
        print(f"Callback data: {data}", flush=True)
        # Ожидается формат pick_<player_id>_защитник
        if not data.startswith('pick_') or '_защитник' not in data:
            await query.edit_message_text('Некорректный выбор.')
            return TOUR_DEFENDER_1
        pid = int(data.split('_')[1])
        roster = context.user_data['tour_roster']
        player = next((p for p in roster if p[1] == pid), None)
        added_personal = False
        if not player:
            # Fallback: ищем в общей БД игроков
            try:
                pdb = db.get_player_by_id(pid)
                if pdb:
                    player = (pdb[6], pdb[0], pdb[1], pdb[2], pdb[3], pdb[4], pdb[5], pdb[6])
                    try:
                        if not any(p_[1] == pdb[0] for p_ in roster):
                            context.user_data['tour_roster'].append(player)
                        added_personal = True
                        context.user_data['premium_extra_available'] = False
                    except Exception:
                        pass
                else:
                    await query.edit_message_text('Игрок не найден.')
                    return TOUR_DEFENDER_1
            except Exception:
                await query.edit_message_text('Игрок не найден.')
                return TOUR_DEFENDER_1
        # Режим добавления в пул — без автодобавления в состав
        if context.user_data.get('premium_mode') == 'add_to_pool':
            try:
                roster = context.user_data['tour_roster']
                if not any(p_[1] == player[1] for p_ in roster):
                    context.user_data['tour_roster'].append(player)
                context.user_data['premium_mode'] = None
                context.user_data['premium_extra_available'] = False
                budget = context.user_data['tour_budget']
                spent = context.user_data['tour_selected']['spent']
                left = budget - spent
                picked = context.user_data['tour_selected']['defenders']
                await query.edit_message_text(f"Добавлен в ваш пул: {player[2]} ({player[4]}). Теперь выберите защитника.")
                next_state = TOUR_DEFENDER_2
                return await send_player_choice(update, context, 'защитник', picked, next_state, left)
            except Exception as e:
                await query.edit_message_text(f"Ошибка добавления в пул: {e}")
                return TOUR_DEFENDER_1
        budget = context.user_data['tour_budget']
        spent = context.user_data['tour_selected']['spent']
        if spent + player[7] > budget:
            await query.edit_message_text(f'Недостаточно HC для выбора {player[1]}!')
            return TOUR_DEFENDER_1
        context.user_data['tour_selected']['defenders'].append(pid)
        context.user_data['tour_selected']['spent'] += player[7]
        left = budget - context.user_data['tour_selected']['spent']
        player_name = escape_md(str(player[2]))
        cost = escape_md(str(player[7]))
        left_str = escape_md(str(left))
        msg = f'Вы выбрали {player_name} \\({cost}\\)\n\n*Оставшийся бюджет: {left_str}*'
        await query.edit_message_text(msg, parse_mode="MarkdownV2")
        if len(context.user_data['tour_selected']['defenders']) == 1:
            print("tour_defender_callback SUCCESS: переход к tour_defender_2", flush=True)
            return await tour_defender_2(update, context)
        elif len(context.user_data['tour_selected']['defenders']) == 2:
            print("tour_defender_callback SUCCESS: переход к tour_goalie", flush=True)
            await tour_goalie(update, context)
            return TOUR_GOALIE
    except Exception as e:
        print(f"tour_defender_callback ERROR: {e}", flush=True)
        logger.exception("Exception in tour_defender_callback")
        await query.edit_message_text(f"Ошибка: {e}")
        return TOUR_DEFENDER_1
    finally:
        print("tour_defender_callback FINISHED", flush=True)


async def tour_defender_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = context.user_data['tour_selected']['defenders']
    return await send_player_choice(update, context, 'защитник', picked, TOUR_DEFENDER_2, left)

async def tour_defender_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = context.user_data['tour_selected']['defenders']
    # Показываем клавиатуру для второго защитника, next_state — TOUR_DEFENDER_2
    return await send_player_choice(update, context, 'защитник', picked, TOUR_DEFENDER_2, left)

async def tour_goalie_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data
        print(f"Callback data: {data}", flush=True)
        # Ожидается формат pick_<player_id>_вратарь
        if not data.startswith('pick_') or '_вратарь' not in data:
            await query.edit_message_text('Некорректный выбор.')
            return TOUR_GOALIE
        pid = int(data.split('_')[1])
        roster = context.user_data['tour_roster']
        player = next((p for p in roster if p[1] == pid), None)
        added_personal = False
        if not player:
            # Fallback: ищем в общей БД игроков
            try:
                pdb = db.get_player_by_id(pid)
                if pdb:
                    player = (pdb[6], pdb[0], pdb[1], pdb[2], pdb[3], pdb[4], pdb[5], pdb[6])
                    try:
                        if not any(p_[1] == pdb[0] for p_ in roster):
                            context.user_data['tour_roster'].append(player)
                        added_personal = True
                        context.user_data['premium_extra_available'] = False
                    except Exception:
                        pass
                else:
                    await query.edit_message_text('Игрок не найден.')
                    return TOUR_GOALIE
            except Exception:
                await query.edit_message_text('Игрок не найден.')
                return TOUR_GOALIE
        # Режим добавления в пул — без автодобавления в состав
        if context.user_data.get('premium_mode') == 'add_to_pool':
            try:
                roster = context.user_data['tour_roster']
                if not any(p_[1] == player[1] for p_ in roster):
                    context.user_data['tour_roster'].append(player)
                context.user_data['premium_mode'] = None
                context.user_data['premium_extra_available'] = False
                budget = context.user_data['tour_budget']
                spent = context.user_data['tour_selected']['spent']
                left = budget - spent
                picked = []
                if context.user_data['tour_selected']['goalie']:
                    picked = [context.user_data['tour_selected']['goalie']]
                await query.edit_message_text(f"Добавлен в ваш пул: {player[2]} ({player[4]}). Теперь выберите вратаря.")
                return await send_player_choice(update, context, 'вратарь', picked, TOUR_CAPTAIN, left)
            except Exception as e:
                await query.edit_message_text(f"Ошибка добавления в пул: {e}")
                return TOUR_GOALIE
        budget = context.user_data['tour_budget']
        spent = context.user_data['tour_selected']['spent']
        if spent + player[7] > budget:
            await query.edit_message_text(f'Недостаточно HC для выбора {player[1]}!')
            return TOUR_GOALIE
        context.user_data['tour_selected']['goalie'] = pid
        context.user_data['tour_selected']['spent'] += player[7]
        left = budget - context.user_data['tour_selected']['spent']
        player_name = escape_md(str(player[2]))
        cost = escape_md(str(player[7]))
        left_str = escape_md(str(left))
        msg = f'Вы выбрали {player_name} \\({cost}\\)\n\n*Оставшийся бюджет: {left_str}*'
        await query.edit_message_text(msg, parse_mode="MarkdownV2")
        # Показываем этап выбора капитана
        return await tour_captain(update, context)
    except Exception as e:
        print(f"tour_goalie_callback ERROR: {e}", flush=True)
        logger.exception("Exception in tour_goalie_callback")
        await query.edit_message_text(f"Ошибка: {e}")
        return TOUR_GOALIE
    finally:
        print("tour_goalie_callback FINISHED", flush=True)


async def tour_goalie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget = context.user_data['tour_budget']
    spent = context.user_data['tour_selected']['spent']
    left = budget - spent
    picked = []
    # Вратарь только один, не нужен exclude кроме уже выбранного
    if context.user_data['tour_selected']['goalie']:
        picked = [context.user_data['tour_selected']['goalie']]
    return await send_player_choice(update, context, 'вратарь', picked, TOUR_CAPTAIN, left)


async def tour_captain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    # Универсально получаем message для reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message

    selected = context.user_data['tour_selected']
    roster = context.user_data['tour_roster']
    # Собираем id полевых игроков
    field_ids = selected['forwards'] + selected['defenders']
    # Получаем инфу по игрокам
    candidates = [p for p in roster if p[1] in field_ids]
    keyboard = [
        [InlineKeyboardButton(f"{p[2]} ({p[3]})", callback_data=f"pick_captain_{p[1]}")]
        for p in candidates
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "Назначь одного полевого игрока из состава капитаном. Его итоговые очки умножим на 1.5"
    await message.reply_text(text, reply_markup=reply_markup)
    return TOUR_CAPTAIN

# --- Обработчик выбора капитана ---
async def tour_captain_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith('pick_captain_'):
        await query.edit_message_text('Некорректный выбор капитана.')
        return TOUR_CAPTAIN
    captain_id = int(data.replace('pick_captain_', ''))
    selected = context.user_data['tour_selected']
    roster = context.user_data['tour_roster']
    field_ids = selected['forwards'] + selected['defenders']
    if captain_id not in field_ids:
        await query.edit_message_text('Капитан должен быть полевым игроком из вашего состава!')
        return TOUR_CAPTAIN
    context.user_data['tour_selected']['captain'] = captain_id
    # Формируем красивое итоговое сообщение с кастомным эмодзи
    # def custom_emoji_entity(emoji_id, offset):
    #     return MessageEntity(
    #         type=MessageEntityType.CUSTOM_EMOJI,
    #         offset=offset,
    #         length=1,  # ASCII-символ
    #         custom_emoji_id=str(emoji_id)
    #     )

    def get_name(pid, captain=False):
        p = next((x for x in roster if x[1]==pid), None)
        if not p:
            return str(pid)
        base = f"{p[2]} ({p[4]})"
        if captain:
            return f"🏅 {base}"
        return base

    def format_final_roster_md(goalie, defenders, forwards, captain, spent, budget):
        lines = [
            '*Ваш итоговый состав:*',
            '',
            escape_md(goalie),
            escape_md(defenders),
            escape_md(forwards),
            '',
            f'Капитан: {escape_md(captain)}',
            f'Потрачено: *{escape_md(str(spent))}*/*{escape_md(str(budget))}*'
        ]
        return '\n'.join(lines)

    goalie_str = get_name(selected['goalie'])
    defenders_str = f"{get_name(selected['defenders'][0])} - {get_name(selected['defenders'][1])}"
    forwards_str = (
        f"{get_name(selected['forwards'][0])} - "
        f"{get_name(selected['forwards'][1])} - "
        f"{get_name(selected['forwards'][2])}"
    )
    captain_str = get_name(captain_id)
    spent = selected['spent']
    budget = context.user_data.get('tour_budget', 0)

    user_id = update.effective_user.id
    tour_id = context.user_data.get('active_tour_id', 1)
    roster_dict = {
        'goalie': selected['goalie'],
        'defenders': selected['defenders'],
        'forwards': selected['forwards']
    }
    from db import save_user_tour_roster
    save_user_tour_roster(user_id, tour_id, roster_dict, captain_id, spent)

    text = format_final_roster_md(goalie_str, defenders_str, forwards_str, captain_str, spent, budget)
    keyboard = [[InlineKeyboardButton('Пересобрать состав', callback_data='restart_tour')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )
    return ConversationHandler.END


async def restart_tour_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from db import get_active_tour, clear_user_tour_roster
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    active_tour = get_active_tour()
    if active_tour:
        tour_id = active_tour['id']
        clear_user_tour_roster(user_id, tour_id)
    # Запускаем процесс выбора состава заново через /tour (ConversationHandler entry_point)
    await context.bot.send_message(chat_id=query.message.chat_id, text="/tour")
    return ConversationHandler.END

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from db import get_budget
    # Универсально получаем message для reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message
    budget = get_budget()
    budget_str = str(budget).replace("-", r"\-") if budget is not None else 'N/A'
    text = rf"""*Правила игры:*

Соберите свою команду из 6 игроков \(3 нападающих, 2 защитника, 1 вратарь\) с ограниченным бюджетом\. У каждого игрока своя стоимость \- 10, 30, 40 или 50 единиц\.

⚡️ Назначь одного полевого игрока из состава капитаном

*Ваш бюджет: {budget_str}*

Собрать состав \- /tour"""
    await message.reply_text(text, parse_mode="MarkdownV2")

async def hc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Универсально получаем message для reply_text
    message = getattr(update, "effective_message", None)
    if message is None and hasattr(update, "message"):
        message = update.message
    elif message is None and hasattr(update, "callback_query"):
        message = update.callback_query.message

    user = update.effective_user
    data = db.get_user_by_id(user.id)
    if data:
        await message.reply_text(f'💰 Твой баланс: {data[3]} HC')
    else:
        await message.reply_text(
            '🚫 Тебя еще нет в списке генменеджеров Фентези Драфт КХЛ\n\n'
            'Зарегистрируйся через /start — и вперёд к сборке состава!'
        )
