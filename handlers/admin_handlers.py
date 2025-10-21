from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup, Bot\nfrom telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters\nfrom config import ADMIN_ID
import db
import os
import json
import logging
from utils import is_admin, send_message_to_users, IMAGES_DIR, TOUR_IMAGE_PATH_FILE, CHALLENGE_IMAGE_PATH_FILE, logger
import asyncio
import datetime
import re
import uuid
from typing import Dict, Iterable, List, Tuple

def _is_user_blocked_safe(user_id: int) -> bool:
    checker = getattr(db, 'is_user_blocked', None)
    if callable(checker):
        try:
            return bool(checker(user_id))
        except Exception:
            pass
    try:
        row = db.get_user_by_id(user_id)
    except Exception:
        row = None
    if not row:
        return False
    try:
        return bool(row[4])
    except Exception:
        return False

# --- Р”РѕР±Р°РІР»РµРЅРёРµ РёРіСЂРѕРєР° ---
ADD_NAME, ADD_POSITION, ADD_CLUB, ADD_NATION, ADD_AGE, ADD_PRICE = range(6)

# --- Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ РёРіСЂРѕРєР° ---
EDIT_NAME, EDIT_POSITION, EDIT_CLUB, EDIT_NATION, EDIT_AGE, EDIT_PRICE = range(6, 12)

# (Р·Р°СЂРµР·РµСЂРІРёСЂРѕРІР°РЅРѕ РґР»СЏ Р±СѓРґСѓС‰РёС… РєРѕРЅСЃС‚Р°РЅС‚ СЃРѕСЃС‚РѕСЏРЅРёР№ 12-13)

# --- РњР°РіР°Р·РёРЅ: СЃРѕСЃС‚РѕСЏРЅРёСЏ РґРёР°Р»РѕРіР° ---
SHOP_TEXT_WAIT = 30
SHOP_IMAGE_WAIT = 31

async def add_image_shop_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text("РћС‚РїСЂР°РІСЊС‚Рµ С‚РµРєСЃС‚ РѕРїРёСЃР°РЅРёСЏ РјР°РіР°Р·РёРЅР°:")
    return SHOP_TEXT_WAIT

async def add_image_shop_text(update, context):
    text = (update.message.text or '').strip()
    try:
        db.update_shop_text(text)
        context.user_data['shop_text'] = text
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СЃРѕС…СЂР°РЅРµРЅРёСЏ С‚РµРєСЃС‚Р°: {e}")
        return ConversationHandler.END
    await update.message.reply_text("РўРµРїРµСЂСЊ РѕС‚РїСЂР°РІСЊС‚Рµ РѕРґРЅРѕ С„РѕС‚Рѕ РјР°РіР°Р·РёРЅР° РІ СЃР»РµРґСѓСЋС‰РµРј СЃРѕРѕР±С‰РµРЅРёРё.")
    return SHOP_IMAGE_WAIT

async def add_image_shop_photo(update, context):
    if not update.message or not update.message.photo:
        await update.message.reply_text("РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РѕС‚РїСЂР°РІСЊС‚Рµ РёРјРµРЅРЅРѕ С„РѕС‚Рѕ.")
        return SHOP_IMAGE_WAIT
    try:
        photo = update.message.photo[-1]
        file_id = photo.file_id
        tg_file = await photo.get_file()
        os.makedirs(IMAGES_DIR, exist_ok=True)
        filename = 'shop.jpg'
        file_path = os.path.join(IMAGES_DIR, filename)
        # РїРѕРїС‹С‚РєР° СѓРЅРёРІРµСЂСЃР°Р»СЊРЅРѕР№ Р·Р°РіСЂСѓР·РєРё РґР»СЏ PTB v20
        try:
            await tg_file.download_to_drive(file_path)
        except Exception:
            await tg_file.download(custom_path=file_path)
        db.update_shop_image(filename, file_id)
        await update.message.reply_text("Р“РѕС‚РѕРІРѕ. РњР°РіР°Р·РёРЅ РѕР±РЅРѕРІР»С‘РЅ.")
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СЃРѕС…СЂР°РЅРµРЅРёСЏ С„РѕС‚Рѕ: {e}")
    return ConversationHandler.END

# --- /change_player_price ---


class ChannelBonusCommand:
    WAITING_LIST: int = 40200
    WAITING_AMOUNT: int = 40201

    def __init__(self, db_gateway=db, channel_username: str = '@goalevaya', admin_id: int = ADMIN_ID):
        self._db = db_gateway
        self._channel_username = channel_username
        self._admin_id = admin_id

    def build_handler(self) -> ConversationHandler:
        return ConversationHandler(
            entry_points=[CommandHandler('channel_bonus', self.start)],
            states={
                self.WAITING_LIST: [MessageHandler(filters.TEXT & (~filters.COMMAND), self.collect_usernames)],
                self.WAITING_AMOUNT: [MessageHandler(filters.TEXT & (~filters.COMMAND), self.collect_amount)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
            allow_reentry=True,
            name='channel_bonus_conv',
            persistent=False,
        )

    def build_callback_handler(self) -> CallbackQueryHandler:
        return CallbackQueryHandler(self.handle_callback, pattern=r'^channel_bonus:')

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not await admin_only(update, context):
            return ConversationHandler.END
        context.user_data['channel_bonus'] = {}
        await update.message.reply_text(
            'Пришли список никнеймов, каждый с новой строки. Пример:
'
            '@nickname1
@nickname2
@nickname3

'
            'После получения списка затем укажи размер бонуса, и я отправлю сообщения только этим пользователям.
'
            'Отправь /cancel для отмены.'
        )
        return self.WAITING_LIST

    async def collect_usernames(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not await admin_only(update, context):
            return ConversationHandler.END
        raw_text = (update.message.text or '').strip()
        usernames = self._extract_usernames(raw_text)
        if not usernames:
            await update.message.reply_text('Не удалось распознать никнеймы. Убедись, что каждый ник на отдельной строке и начинается с символа @.')
            return self.WAITING_LIST

        entries: List[Dict[str, str]] = []
        missing: List[str] = []
        duplicates: List[str] = []
        already_rewarded: List[str] = []
        seen: set[str] = set()

        for original in usernames:
            normalized = original.lower()
            if normalized in seen:
                duplicates.append(original)
                continue
            seen.add(normalized)
            row = self._db.get_user_by_username_insensitive(original)
            if not row:
                missing.append(original)
                continue
            user_id = row[0]
            username = row[1] or original
            eligible = not self._db.has_channel_bonus_reward(user_id)
            if not eligible:
                already_rewarded.append(original)
            entries.append({
                'input': original,
                'username': username,
                'user_id': user_id,
                'eligible': eligible,
            })

        if not entries:
            await update.message.reply_text('Не нашлось пользователей среди указанных никнеймов. Команда завершена.')
            context.user_data.pop('channel_bonus', None)
            return ConversationHandler.END

        eligible_count = sum(1 for item in entries if item['eligible'])
        summary_lines = [
            f'Всего никнеймов: {len(usernames)}',
            f'Найдено в базе: {len(entries)}',
            f'Доступно для начисления: {eligible_count}',
        ]
        if missing:
            summary_lines.append('Не найдены в базе: ' + ', '.join(f'@{name}' for name in missing))
        if duplicates:
            summary_lines.append('Продублированы: ' + ', '.join(f'@{name}' for name in duplicates))
        if already_rewarded:
            summary_lines.append('Уже получали бонус: ' + ', '.join(f'@{name}' for name in already_rewarded))

        await update.message.reply_text('
'.join(summary_lines) + '

Укажи размер бонуса (целое число HC).')

        context.user_data['channel_bonus'] = {
            'entries': entries,
            'missing': missing,
            'duplicates': duplicates,
            'already_rewarded': already_rewarded,
        }
        return self.WAITING_AMOUNT

    async def collect_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not await admin_only(update, context):
            return ConversationHandler.END
        data = context.user_data.get('channel_bonus') or {}
        entries = data.get('entries') or []
        if not entries:
            await update.message.reply_text('Контекст потерян. Начни заново: /channel_bonus.')
            return ConversationHandler.END

        amount_text = (update.message.text or '').strip()
        if not amount_text.isdigit():
            await update.message.reply_text('Размер бонуса должен быть положительным целым числом. Попробуй ещё раз.')
            return self.WAITING_AMOUNT
        amount = int(amount_text)
        if amount <= 0:
            await update.message.reply_text('Размер бонуса должен быть больше нуля. Попробуй ещё раз.')
            return self.WAITING_AMOUNT

        eligible_entries = [item for item in entries if item['eligible']]
        if not eligible_entries:
            await update.message.reply_text('Все перечисленные пользователи уже получали такой бонус ранее. Начислять нечего.')
            context.user_data.pop('channel_bonus', None)
            return ConversationHandler.END

        delivered: List[str] = []
        failed: List[str] = []

        for entry in eligible_entries:
            user_id = entry['user_id']
            input_username = entry['input']
            try:
                self._db.clear_channel_bonus_requests(user_id)
                token = uuid.uuid4().hex
                allowed_by = update.effective_user.id if update.effective_user else None
                self._db.create_channel_bonus_request(token, user_id, amount, allowed_by)
                text = self._build_bonus_message(amount)
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton('Проверить подписку', callback_data=f'channel_bonus:{token}')]])
                await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode='HTML',
                    disable_web_page_preview=True,
                    reply_markup=keyboard
                )
                delivered.append(f'@{input_username}')
            except Exception as error:
                logger.error('Failed to send channel bonus message.', exc_info=True)
                failed.append(f'@{input_username}: {error}')

        summary = ['Рассылка завершена.']
        if delivered:
            summary.append('Сообщения доставлены: ' + ', '.join(delivered))
        if data.get('already_rewarded'):
            summary.append('Уже получали бонус: ' + ', '.join(f'@{name}' for name in data['"already_rewarded"']))
        if data.get('missing'):
            summary.append('Не найдены в базе: ' + ', '.join(f'@{name}' for name in data['"missing"']))
        if failed:
            summary.append('Не удалось отправить: ' + ', '.join(failed))

        await update.message.reply_text('
'.join(summary))
        context.user_data.pop('channel_bonus', None)
        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text('Рассылка бонуса отменена.')
        context.user_data.pop('channel_bonus', None)
        return ConversationHandler.END

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        token = (query.data or '').split(':', 1)[-1]
        request = self._db.get_channel_bonus_request(token)
        if not request:
            await self._safe_edit(query, 'Эта ссылка больше недействительна.')
            return

        user_id = request['user_id']
        amount = request['amount']
        status = request['status']

        if query.from_user.id != user_id:
            await query.answer('Эта кнопка предназначена не для вас.', show_alert=True)
            return

        if status == 'rewarded':
            await self._safe_edit(query, 'Бонус уже начислен. Спасибо!')
            return
        if status != 'pending':
            await self._safe_edit(query, 'Эта ссылка больше недоступна.')
            return

        try:
            member = await context.bot.get_chat_member(self._channel_username, user_id)
            subscribed = self._is_active_member(member)
        except Exception as error:
            if self._is_user_missing_error(error):
                subscribed = False
            else:
                logger.error('Failed to verify subscription for channel bonus.', exc_info=True)
                await query.answer('Не удалось проверить подписку. Попробуйте позже.', show_alert=True)
                return

        if not subscribed:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton('Проверить подписку', callback_data=f'channel_bonus:{token}')]])
            await self._safe_edit(query, 'Кажется, вы ещё не подписались на канал. Подпишитесь и нажмите кнопку ещё раз.', keyboard)
            return

        result = self._db.mark_channel_bonus_rewarded(token)
        if not result or result.get('status') != 'rewarded':
            await self._safe_edit(query, 'Эта ссылка больше недоступна.')
            return

        self._db.update_hc_balance(user_id, amount)
        success_text = f'Бонус +{amount} HC начислен! Благодарим за подписку 💛'
        await self._safe_edit(query, success_text)

        username = query.from_user.username or ''
        label = f'@{username}' if username else f'id {user_id}'
        admin_message = f'Пользователь {label} получил +{amount} HC за подписку на канал.'
        try:
            await context.bot.send_message(chat_id=self._admin_id, text=admin_message)
        except Exception:
            logger.error('Failed to notify admins about channel bonus reward.', exc_info=True)

    def _extract_usernames(self, raw_text: str) -> List[str]:
        usernames: List[str] = []
        for line in raw_text.splitlines():
            value = line.strip()
            if not value:
                continue
            if value.startswith('@'):
                value = value[1:]
            value = re.sub(r'^https?://t\.me/', '', value, flags=re.IGNORECASE)
            if self._USERNAME_RE.match(value):
                usernames.append(value)
        return usernames

    def _build_bonus_message(self, amount: int) -> str:
        return (
            'Дорогой менеджер, кажется, вы ещё не с нами в нашем <a href="https://t.me/goalevaya">телеграм-канале Голевая</a> 💛

'
            'Там мы делимся анонсами, полезными советами и новостями о драфте — всё, чтобы играть было ещё интереснее. '
            f'Будем рады видеть вас в команде! В знак благодарности за подписку на канал даём +{amount} HC на ваш счёт 🎁'
        )

    # eslint-disable-next-line class-methods-use-this
    def _is_active_member(self, member) -> bool:
        if member is None:
            return False
        status = getattr(member, 'status', None)
        if status == 'restricted':
            return bool(getattr(member, 'is_member', False))
        return status in {'creator', 'administrator', 'member'}

    # eslint-disable-next-line class-methods-use-this
    def _is_user_missing_error(self, error: Exception) -> bool:
        description = getattr(error, 'description', None) or getattr(error, 'message', None) or str(error)
        if not isinstance(description, str):
            return False
        lowered = description.lower()
        return 'user not found' in lowered or 'user_not_participant' in lowered or 'chat member not found' in lowered

    async def _safe_edit(self, query, text: str, keyboard: InlineKeyboardMarkup | None = None) -> None:
        try:
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(text, parse_mode='HTML', reply_markup=keyboard)

class ChangePlayerPriceCommand:
    WAITING_INPUT: int = 40010
    _LINE_PATTERN = re.compile(r'^\s*(\d+)\s*:\s*(\d+)\s*$')
    _CHUNK_LIMIT = 3500

    def __init__(self, db_gateway=db):
        self._db = db_gateway

    def build_handler(self) -> ConversationHandler:
        return ConversationHandler(
            entry_points=[CommandHandler('change_player_price', self.start)],
            states={
                self.WAITING_INPUT: [
                    MessageHandler(filters.TEXT & (~filters.COMMAND), self.process_input)
                ],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
            allow_reentry=True,
            name="change_player_price_conv",
            persistent=False,
        )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not await admin_only(update, context):
            return ConversationHandler.END
        prompt = (
            "Введи список игроков и новых цен в формате <code>id: цена</code> одной строкой на игрока.\n"
            "Например:\n"
            "<code>323: 50</code>\n"
            "<code>40: 30</code>\n"
            "<code>24: 30</code>\n\n"
            "Отправь /cancel для отмены."
        )
        await update.message.reply_text(prompt, parse_mode='HTML')
        return self.WAITING_INPUT

    async def process_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not await admin_only(update, context):
            return ConversationHandler.END
        raw_text = (update.message.text or '').strip()
        if not raw_text:
            await update.message.reply_text("Не нашел данных. Введи строки вида id: цена.")
            return self.WAITING_INPUT
        try:
            updates = self._parse_price_updates(raw_text)
        except ValueError as err:
            await update.message.reply_text(str(err))
            return self.WAITING_INPUT
        if not updates:
            await update.message.reply_text("Не нашел строк с парами id и цен. Попробуй снова.")
            return self.WAITING_INPUT
        try:
            updated_players, missing_ids = self._apply_updates(updates.items())
        except Exception as err:
            await update.message.reply_text(f"Ошибка при обновлении: {err}")
            return ConversationHandler.END
        if missing_ids:
            missing_str = ", ".join(str(pid) for pid in missing_ids)
            await update.message.reply_text(f"Не нашел игроков с id: {missing_str}.")
        if updated_players:
            await self._send_player_summaries(update, updated_players)
        else:
            await update.message.reply_text("Не удалось обновить ни одного игрока.")
        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("Изменение стоимости игроков отменено.")
        return ConversationHandler.END

    def _parse_price_updates(self, raw_text: str) -> Dict[int, int]:
        updates: Dict[int, int] = {}
        for line_number, raw_line in enumerate(raw_text.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            match = self._LINE_PATTERN.match(line)
            if not match:
                raise ValueError(f"Строка {line_number} имеет неверный формат. Используй формат id: цена.")
            player_id = int(match.group(1))
            price = int(match.group(2))
            if price < 0:
                raise ValueError(f"Строка {line_number}: цена должна быть неотрицательной.")
            updates[player_id] = price
        return updates

    def _apply_updates(self, updates: Iterable[Tuple[int, int]]) -> Tuple[List[Tuple], List[int]]:
        updated_players: List[Tuple] = []
        missing_ids: List[int] = []
        for player_id, price in updates:
            try:
                updated = self._db.update_player_price(player_id, price)
            except Exception as err:
                raise RuntimeError(f"игрок {player_id}: {err}") from err
            if not updated:
                missing_ids.append(player_id)
                continue
            player = self._db.get_player_by_id(player_id)
            if player:
                updated_players.append(player)
            else:
                missing_ids.append(player_id)
        return updated_players, missing_ids

    async def _send_player_summaries(self, update: Update, players: List[Tuple]) -> None:
        header = "Обновленные игроки:\n"
        lines = [self._format_player(player) for player in players]
        message = header + "\n".join(lines)
        for chunk in self._chunk_text(message):
            await update.message.reply_text(chunk)

    def _format_player(self, player: Tuple) -> str:
        player_id, name, position, club, nation, age, price = player
        return f"{player_id}. {name} | {position} | {club} | {nation} | {age} лет | {price} HC"

    def _chunk_text(self, text: str) -> List[str]:
        if len(text) <= self._CHUNK_LIMIT:
            return [text]
        return [text[i:i + self._CHUNK_LIMIT] for i in range(0, len(text), self._CHUNK_LIMIT)]


class CheckChannelCommand:
    WAITING_LIST: int = 40100
    _CHUNK_LIMIT = 3500
    _USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{5,32}$')

    def __init__(self, db_gateway=db, channel_username: str = '@goalevaya'):
        self._db = db_gateway
        self._channel_username = channel_username

    def build_handler(self) -> ConversationHandler:
        return ConversationHandler(
            entry_points=[CommandHandler('check_channel', self.start)],
            states={
                self.WAITING_LIST: [
                    MessageHandler(filters.TEXT & (~filters.COMMAND), self.process_list)
                ],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
            allow_reentry=True,
            name="check_channel_conv",
            persistent=False,
        )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not await admin_only(update, context):
            return ConversationHandler.END
        prompt = (
            "Введи список никнеймов, каждый с новой строки. Пример:\n"
            "@nickname1\n"
            "@nickname2\n"
            "@nickname3\n\n"
            "После получения списка я проверю, подписан ли каждый из них на канал t.me/goalevaya.\n"
            "Отправь /cancel для отмены."
        )
        await update.message.reply_text(prompt)
        context.user_data.pop('check_channel_usernames', None)
        return self.WAITING_LIST

    async def process_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not await admin_only(update, context):
            return ConversationHandler.END
        raw_text = (update.message.text or '').strip()
        usernames = self._extract_usernames(raw_text)
        if not usernames:
            await update.message.reply_text(
                "Не удалось распознать никнеймы. Убедись, что каждый ник на отдельной строке и начинается с @."
            )
            return self.WAITING_LIST

        await update.message.reply_text("Проверяю подписку, подожди…")

        rows = []
        for username in usernames:
            row = self._db.get_user_by_username_insensitive(username)
            if not row:
                lowered = username.lower()
                if lowered != username:
                    row = self._db.get_user_by_username_insensitive(lowered)
            if not row:
                rows.append(f"@{username} — пользователь не найден в базе бота.")
                continue
            telegram_id = row[0]
            try:
                member = await context.bot.get_chat_member(self._channel_username, telegram_id)
                subscribed = self._is_active_member(member)
                if subscribed:
                    rows.append(f"@{username} — подписан ✅")
                else:
                    rows.append(f"@{username} — не подписан ❌")
            except Exception as error:
                if self._is_user_missing_error(error):
                    rows.append(f"@{username} — не подписан ❌")
                else:
                    message = getattr(error, 'message', None) or getattr(error, 'description', None) or str(error)
                    rows.append(f"@{username} — ошибка проверки: {message}")

        response = ["Результаты проверки подписки на канал t.me/goalevaya:", ""]
        response.extend(rows)
        text = "\n".join(response)
        for chunk in self._chunk_text(text):
            await update.message.reply_text(chunk)
        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("Проверка подписки отменена.")
        return ConversationHandler.END

    def _extract_usernames(self, text: str) -> List[str]:
        usernames = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith('@'):
                line = line[1:]
            line = re.sub(r'^https?://t\.me/', '', line, flags=re.IGNORECASE)
            if self._USERNAME_RE.match(line):
                usernames.append(line)
        return usernames

    def _chunk_text(self, text: str) -> List[str]:
        if len(text) <= self._CHUNK_LIMIT:
            return [text]
        return [text[i:i + self._CHUNK_LIMIT] for i in range(0, len(text), self._CHUNK_LIMIT)]

    # eslint-disable-next-line class-methods-use-this
    def _is_active_member(self, member) -> bool:
        if member is None:
            return False

        status = getattr(member, 'status', None)
        if status == 'restricted':
            return bool(getattr(member, 'is_member', False))

        return status in {'creator', 'administrator', 'member'}

    # eslint-disable-next-line class-methods-use-this
    def _is_user_missing_error(self, error: Exception) -> bool:
        description = getattr(error, 'description', None) or getattr(error, 'message', None) or str(error)
        if not isinstance(description, str):
            return False
        lowered = description.lower()
        return 'user not found' in lowered or 'user_not_participant' in lowered or 'not a member' in lowered


async def add_image_shop_cancel(update, context):
    await update.message.reply_text("РћР±РЅРѕРІР»РµРЅРёРµ РјР°РіР°Р·РёРЅР° РѕС‚РјРµРЅРµРЅРѕ.")
    return ConversationHandler.END

# --- РЈРґР°Р»РµРЅРёРµ РїРѕРґРїРёСЃРѕРє (Р·Р°РїР°СЂРѕР»РµРЅРЅС‹Рµ РєРѕРјР°РЅРґС‹) ---
DEL_SUB_WAIT_PASSWORD = 10010
DEL_SUB_WAIT_USERNAME = 10011

async def delete_sub_by_username_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ.")
        return ConversationHandler.END
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РїР°СЂРѕР»СЊ РґР»СЏ СѓРґР°Р»РµРЅРёСЏ РїРѕРґРїРёСЃРєРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ:")
    return DEL_SUB_WAIT_PASSWORD

async def delete_sub_by_username_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pw = (update.message.text or '').strip()
    checker = _get_purge_password_checker()
    if not checker(pw):
        await update.message.reply_text("РќРµРІРµСЂРЅС‹Р№ РїР°СЂРѕР»СЊ. РћС‚РјРµРЅР°.")
        return ConversationHandler.END
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ @username РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ (Р±РµР· РїСЂРѕР±РµР»РѕРІ):")
    return DEL_SUB_WAIT_USERNAME

async def delete_sub_by_username_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = (update.message.text or '').strip()
    if username.startswith('@'):
        username = username[1:]
    try:
        row = db.get_user_by_username(username)
        if not row:
            await update.message.reply_text("РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ.")
            return ConversationHandler.END
        user_id = row[0] if isinstance(row, tuple) else row['telegram_id'] if isinstance(row, dict) else row[0]
        deleted = db.delete_subscription_by_user_id(user_id)
        await update.message.reply_text(f"РЈРґР°Р»РµРЅРѕ РїРѕРґРїРёСЃРѕРє: {deleted} Сѓ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ @{username}.")
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР°: {e}")
    return ConversationHandler.END

async def delete_sub_by_username_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("РћС‚РјРµРЅРµРЅРѕ.")
    return ConversationHandler.END

PURGE_SUBS_WAIT_PASSWORD = 10020

async def purge_subscriptions_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ.")
        return ConversationHandler.END
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РїР°СЂРѕР»СЊ РґР»СЏ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ СѓРґР°Р»РµРЅРёСЏ Р’РЎР•РҐ РїРѕРґРїРёСЃРѕРє:")
    return PURGE_SUBS_WAIT_PASSWORD

async def purge_subscriptions_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pw = (update.message.text or '').strip()
    checker = _get_purge_password_checker()
    if not checker(pw):
        await update.message.reply_text("РќРµРІРµСЂРЅС‹Р№ РїР°СЂРѕР»СЊ. РћС‚РјРµРЅР°.")
        return ConversationHandler.END
    try:
        deleted = db.purge_all_subscriptions()
        await update.message.reply_text(f"РЈРґР°Р»РµРЅРѕ РїРѕРґРїРёСЃРѕРє: {deleted}.")
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СѓРґР°Р»РµРЅРёСЏ: {e}")
    return ConversationHandler.END

# --- РЈРґР°Р»РµРЅРёРµ РћР”РќРћР“Рћ С‚СѓСЂР° РїРѕ id (Р·Р°РїР°СЂРѕР»РµРЅРЅР°СЏ РєРѕРјР°РЅРґР°) ---
DEL_TOUR_WAIT_PASSWORD = 10030
DEL_TOUR_WAIT_ID = 10031

async def delete_tour_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ.")
        return ConversationHandler.END
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РїР°СЂРѕР»СЊ РґР»СЏ СѓРґР°Р»РµРЅРёСЏ РўРЈР Рђ РїРѕ id:")
    return DEL_TOUR_WAIT_PASSWORD

async def delete_tour_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pw = (update.message.text or '').strip()
    checker = _get_purge_password_checker()
    if not checker(pw):
        await update.message.reply_text("РќРµРІРµСЂРЅС‹Р№ РїР°СЂРѕР»СЊ. РћС‚РјРµРЅР°.")
        return ConversationHandler.END
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ id С‚СѓСЂР° (С†РµР»РѕРµ С‡РёСЃР»Рѕ):")
    return DEL_TOUR_WAIT_ID

async def delete_tour_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (update.message.text or '').strip()
    if not txt.isdigit():
        await update.message.reply_text("РќСѓР¶РЅРѕ С‡РёСЃР»Рѕ. РћС‚РјРµРЅРµРЅРѕ.")
        return ConversationHandler.END
    tour_id = int(txt)
    try:
        deleted = db.delete_tour_by_id(tour_id)
        if deleted:
            await update.message.reply_text(f"РўСѓСЂ #{tour_id} СѓРґР°Р»С‘РЅ. РЎРІСЏР·Р°РЅРЅС‹Рµ РґР°РЅРЅС‹Рµ РѕС‡РёС‰РµРЅС‹.")
        else:
            await update.message.reply_text(f"РўСѓСЂ #{tour_id} РЅРµ РЅР°Р№РґРµРЅ.")
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СѓРґР°Р»РµРЅРёСЏ: {e}")
    return ConversationHandler.END

async def delete_tour_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("РћС‚РјРµРЅРµРЅРѕ.")
    return ConversationHandler.END
# --- PURGE TOURS (Р·Р°РїР°СЂРѕР»РµРЅРЅР°СЏ РєРѕРјР°РЅРґР°) ---
PURGE_WAIT_PASSWORD = 9991

def _get_purge_password_checker():
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ С„СѓРЅРєС†РёСЋ checker(pw:str)->bool, РЅРµ СЂР°СЃРєСЂС‹РІР°СЏ РїР°СЂРѕР»СЊ РІ РєРѕРґРµ.
    РџСЂРѕРІРµСЂСЏРµС‚СЃСЏ СЃРЅР°С‡Р°Р»Р° РїРµСЂРµРјРµРЅРЅР°СЏ РѕРєСЂСѓР¶РµРЅРёСЏ PURGE_TOURS_PASSWORD_HASH (sha256),
    РёРЅР°С‡Рµ PURGE_TOURS_PASSWORD (plain)."""
    import hashlib
    env_hash = os.getenv('PURGE_TOURS_PASSWORD_HASH', '').strip()
    env_plain = os.getenv('PURGE_TOURS_PASSWORD', '').strip()
    if env_hash:
        def check(pw: str) -> bool:
            try:
                return hashlib.sha256((pw or '').encode('utf-8')).hexdigest() == env_hash
            except Exception:
                return False
        return check
    else:
        secret = env_plain
        def check(pw: str) -> bool:
            return (pw or '') == secret and secret != ''
        return check

async def purge_tours_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from utils import is_admin
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ.")
        return ConversationHandler.END
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РїР°СЂРѕР»СЊ РґР»СЏ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ СѓРґР°Р»РµРЅРёСЏ Р’РЎР•РҐ С‚СѓСЂРѕРІ:")
    return PURGE_WAIT_PASSWORD

async def purge_tours_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pw = (update.message.text or '').strip()
    checker = _get_purge_password_checker()
    if not checker(pw):
        await update.message.reply_text("РќРµРІРµСЂРЅС‹Р№ РїР°СЂРѕР»СЊ. РћС‚РјРµРЅР°.")
        return ConversationHandler.END
    try:
        deleted = db.purge_all_tours()
        await update.message.reply_text(f"РЈРґР°Р»РµРЅРѕ С‚СѓСЂРѕРІ: {deleted}. РЎРѕСЃС‚Р°РІС‹ Рё СЃРІСЏР·Р°РЅРЅС‹Рµ РґР°РЅРЅС‹Рµ С‚Р°РєР¶Рµ РѕС‡РёС‰РµРЅС‹.")
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СѓРґР°Р»РµРЅРёСЏ: {e}")
    return ConversationHandler.END

async def purge_tours_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("РћС‚РјРµРЅРµРЅРѕ.")
    return ConversationHandler.END

async def add_image_shop_cancel(update, context):
    await update.message.reply_text("РћР±РЅРѕРІР»РµРЅРёРµ РјР°РіР°Р·РёРЅР° РѕС‚РјРµРЅРµРЅРѕ.")
    return ConversationHandler.END

# --- Р”РѕР±Р°РІР»РµРЅРёРµ РёРіСЂРѕРєР° ---
async def add_player_start(update, context):
    logger.info("add_player_start called")
    if not await admin_only(update, context):
        logger.warning("Admin check failed in add_player_start")
        return ConversationHandler.END
    logger.info("Sending name prompt")
    await update.message.reply_text("Введите имя и фамилию игрока:")
    logger.info(f"Returning ADD_NAME state: {ADD_NAME}")
    return ADD_NAME

async def add_player_name(update, context):
    try:
        logger.info(f"add_player_name called with text: {update.message.text}")
        if not update.message or not update.message.text or not update.message.text.strip():
            await update.message.reply_text("Пожалуйста, введите корректное имя игрока.")
            return ADD_NAME
            
        context.user_data['name'] = update.message.text.strip()
        logger.info(f"Set name to: {context.user_data['name']}")
        logger.info(f"Sending position prompt, will return ADD_POSITION: {ADD_POSITION}")
        
        await update.message.reply_text("Введите позицию (нападающий/защитник/вратарь):")
        return ADD_POSITION
        
    except Exception as e:
        logger.error(f"Error in add_player_name: {str(e)}", exc_info=True)
        if update and update.message:
            await update.message.reply_text("РџСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ РёРјРµРЅРё РёРіСЂРѕРєР°. РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РїРѕРїСЂРѕР±СѓР№С‚Рµ РµС‰Рµ СЂР°Р·.")
        return ADD_NAME  # Возвращаемся к вводу имени

async def add_player_position(update, context):
    context.user_data['position'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите клуб:")
    return ADD_CLUB

async def add_player_club(update, context):
    context.user_data['club'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите нацию:")
    return ADD_NATION

async def add_player_nation(update, context):
    context.user_data['nation'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите возраст (число):")
    return ADD_AGE

async def add_player_age(update, context):
    context.user_data['age'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите стоимость (HC, число):")
    return ADD_PRICE

async def add_player_price(update, context):
    try:
        name = context.user_data.get('name', '')
        position = context.user_data.get('position', '')
        club = context.user_data.get('club', '')
        nation = context.user_data.get('nation', '')
        age = int(context.user_data.get('age', '0'))
        price = int((update.message.text or '0').strip())
        db.add_player(name, position, club, nation, age, price)
        await update.message.reply_text("Игрок добавлен!")
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° РїСЂРё РґРѕР±Р°РІР»РµРЅРёРё: {e}")
    return ConversationHandler.END

async def add_player_cancel(update, context):
    await update.message.reply_text("Добавление отменено.")
    return ConversationHandler.END

# --- РЎРїРёСЃРѕРє / РїРѕРёСЃРє / СѓРґР°Р»РµРЅРёРµ РёРіСЂРѕРєРѕРІ ---
async def list_players(update, context):
    if not await admin_only(update, context):
        return
    try:
        players = db.get_all_players()
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ СЃРїРёСЃРєР° РёРіСЂРѕРєРѕРІ: {e}")
        return
    if not players:
        await update.message.reply_text("Список игроков пуст.")
        return
    msg = "\n".join([
        f"{p[0]}. {p[1]} | {p[2]} | {p[3]} | {p[4]} | {p[5]} лет | {p[6]} HC" for p in players
    ])
    for i in range(0, len(msg), 3500):
        await update.message.reply_text(msg[i:i+3500])

async def find_player(update, context):
    if not await admin_only(update, context):
        return
    if not context.args or not str(context.args[0]).isdigit():
        await update.message.reply_text("Использование: /find_player <id>")
        return
    player_id = int(context.args[0])
    player = db.get_player_by_id(player_id)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    msg = f"{player[0]}. {player[1]} | {player[2]} | {player[3]} | {player[4]} | {player[5]} лет | {player[6]} HC"
    await update.message.reply_text(msg)

async def remove_player(update, context):
    if not await admin_only(update, context):
        return
    if not context.args or not str(context.args[0]).isdigit():
        await update.message.reply_text("Использование: /remove_player <id>")
        return
    player_id = int(context.args[0])
    player = db.get_player_by_id(player_id)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    try:
        if db.remove_player(player_id):
            await update.message.reply_text(f"Игрок {player[1]} (ID: {player_id}) удалён.")
        else:
            await update.message.reply_text("Ошибка при удалении игрока.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при удалении игрока: {e}")

# --- Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ РёРіСЂРѕРєР° ---
async def edit_player_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    if not context.args or not str(context.args[0]).isdigit():
        await update.message.reply_text("Использование: /edit_player <id>")
        return ConversationHandler.END
    player_id = int(context.args[0])
    player = db.get_player_by_id(player_id)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return ConversationHandler.END
    context.user_data['edit_player_id'] = player_id
    await update.message.reply_text("Введите новое имя и фамилию игрока:")
    return EDIT_NAME

async def edit_player_name(update, context):
    context.user_data['edit_name'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите новую позицию (нападающий/защитник/вратарь):")
    return EDIT_POSITION

async def edit_player_position(update, context):
    context.user_data['edit_position'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите новый клуб:")
    return EDIT_CLUB

async def edit_player_club(update, context):
    context.user_data['edit_club'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите новую нацию:")
    return EDIT_NATION

async def edit_player_nation(update, context):
    context.user_data['edit_nation'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите новый возраст (число):")
    return EDIT_AGE

async def edit_player_age(update, context):
    context.user_data['edit_age'] = (update.message.text or '').strip()
    await update.message.reply_text("Введите новую стоимость (HC, число):")
    return EDIT_PRICE

async def edit_player_price(update, context):
    try:
        player_id = int(context.user_data.get('edit_player_id'))
        name = context.user_data.get('edit_name', '')
        position = context.user_data.get('edit_position', '')
        club = context.user_data.get('edit_club', '')
        nation = context.user_data.get('edit_nation', '')
        age = int(context.user_data.get('edit_age', '0'))
        price = int((update.message.text or '0').strip())
        ok = db.update_player(player_id, name, position, club, nation, age, price)
        if ok:
            await update.message.reply_text("Игрок успешно обновлён!")
        else:
            await update.message.reply_text("Не удалось обновить игрока.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при обновлении: {e}")
    finally:
        for k in ('edit_player_id','edit_name','edit_position','edit_club','edit_nation','edit_age'):
            context.user_data.pop(k, None)
    return ConversationHandler.END

async def edit_player_cancel(update, context):
    await update.message.reply_text("Редактирование отменено.")
    return ConversationHandler.END

# --- РўСѓСЂ: РґРѕР±Р°РІРёС‚СЊ Рё РІС‹РІРµСЃС‚Рё СЃРѕСЃС‚Р°РІ ---
SET_BUDGET_WAIT = 21

async def set_budget_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text("Please send the new budget as a positive integer (e.g., 180):")
    return SET_BUDGET_WAIT

async def set_budget_process(update, context):
    text = update.message.text.strip()
    try:
        value = int(text)
        if value <= 0:
            await update.message.reply_text("Budget must be a positive integer!")
            return ConversationHandler.END
        db.set_budget(value)
        await update.message.reply_text(f"Budget set successfully: {value}")
    except Exception:
        await update.message.reply_text("Error! Please send a positive integer.")
    return ConversationHandler.END

SET_TOUR_ROSTER_WAIT = 20

async def set_tour_roster_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text(
        "РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РѕС‚РїСЂР°РІСЊС‚Рµ СЃРїРёСЃРѕРє РёРіСЂРѕРєРѕРІ РЅР° С‚СѓСЂ РІ С„РѕСЂРјР°С‚Рµ:\n50: 28, 1, ...\n40: ... Рё С‚.Рґ. (СЂРѕРІРЅРѕ 20 РёРіСЂРѕРєРѕРІ)"
    )
    return SET_TOUR_ROSTER_WAIT

async def set_tour_roster_process(update, context):
    text = update.message.text
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    ids = []
    try:
        for line in lines:
            if ':' not in line:
                await update.message.reply_text(f"РќРµРІРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚ СЃС‚СЂРѕРєРё: {line}")
                return ConversationHandler.END
            cost_str, ids_str = line.split(':', 1)
            cost = int(cost_str.strip())
            id_list = [int(x.strip()) for x in ids_str.split(',') if x.strip()]
            for player_id in id_list:
                ids.append((cost, player_id))
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СЂР°Р·Р±РѕСЂР°: {e}")
        return ConversationHandler.END
    if len(ids) != 20:
        await update.message.reply_text(f"РћС€РёР±РєР°: РґРѕР»Р¶РЅРѕ Р±С‹С‚СЊ СЂРѕРІРЅРѕ 20 РёРіСЂРѕРєРѕРІ, Р° РЅРµ {len(ids)}")
        return ConversationHandler.END
    # РџСЂРѕРІРµСЂРєР°, С‡С‚Рѕ РІСЃРµ РёРіСЂРѕРєРё СЃСѓС‰РµСЃС‚РІСѓСЋС‚
    for cost, player_id in ids:
        player = db.get_player_by_id(player_id)
        if not player:
            await update.message.reply_text(f"РРіСЂРѕРє СЃ id {player_id} РЅРµ РЅР°Р№РґРµРЅ!")
            return ConversationHandler.END
    db.clear_tour_roster()
    for cost, player_id in ids:
        db.add_tour_roster_entry(player_id, cost)
    await update.message.reply_text("РЎРѕСЃС‚Р°РІ РЅР° С‚СѓСЂ СѓСЃРїРµС€РЅРѕ СЃРѕС…СЂР°РЅС‘РЅ!")
    return ConversationHandler.END

async def get_tour_roster(update, context):
    if not await admin_only(update, context):
        return
    roster = db.get_tour_roster_with_player_info()
    if not roster:
        await update.message.reply_text("РЎРѕСЃС‚Р°РІ РЅР° С‚СѓСЂ РЅРµ Р·Р°РґР°РЅ.")
        return
    msg = "РЎРѕСЃС‚Р°РІ РЅР° С‚СѓСЂ:\n"
    for cost, pid, name, pos, club, nation, age, price in roster:
        msg += f"{cost}: {pid}. {name} | {pos} | {club} | {nation} | {age} лет | {price} HC\n"
    await update.message.reply_text(msg)

# --- РЎРїРёСЃРѕРє РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ Рё РїРѕРґРїРёСЃРѕРє ---
async def show_users(update, context):
    if not await admin_only(update, context):
        return
    import datetime
    # РџРѕР»СѓС‡Р°РµРј РІСЃРµС… РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ Рё РёС… РїРѕРґРїРёСЃРєРё
    with db.closing(db.sqlite3.connect(db.DB_NAME)) as conn:
        users = conn.execute('SELECT telegram_id, username, name, hc_balance FROM users').fetchall()
        subs = {row[0]: row[1] for row in conn.execute('SELECT user_id, paid_until FROM subscriptions').fetchall()}
    now = datetime.datetime.utcnow()
    lines = []
    for user_id, username, name, hc_balance in users:
        paid_until = subs.get(user_id)
        active = False
        if paid_until:
            try:
                dt = datetime.datetime.fromisoformat(str(paid_until))
                active = dt > now
            except Exception:
                active = False
        status = '✔ подписка активна' if active else '✖ нет подписки'
        lines.append(f"{user_id} | {username or '-'} | {name or '-'} | {status} | HC: {hc_balance if hc_balance is not None else 0}")
    if not lines:
        await update.message.reply_text("Нет пользователей.")
    else:
        msg = 'Пользователи и подписки:\n\n' + '\n'.join(lines)
        for i in range(0, len(msg), 4000):
            await update.message.reply_text(msg[i:i+4000])

# --- Р§РµР»Р»РµРЅРґР¶: РІС‹РІРѕРґ СЃРѕСЃС‚Р°РІРѕРІ РїРѕ id ---



# --- Пользователи с активной подпиской ---
async def list_active_subscribers(update, context):
    if not await admin_only(update, context):
        return
    import datetime
    try:
        from zoneinfo import ZoneInfo
    except Exception:
        ZoneInfo = None
    tz = None
    if ZoneInfo is not None:
        try:
            tz = ZoneInfo('Europe/Moscow')
        except Exception:
            tz = None
    if tz is None:
        tz = datetime.timezone(datetime.timedelta(hours=3))
    now = db.get_moscow_now().astimezone(tz)
    with db.closing(db.sqlite3.connect(db.DB_NAME)) as conn:
        conn.row_factory = db.sqlite3.Row
        rows = conn.execute(
            '''
            SELECT u.telegram_id,
                   u.username,
                   u.name,
                   u.hc_balance,
                   MAX(s.paid_until) AS paid_until
            FROM subscriptions AS s
            JOIN users AS u ON u.telegram_id = s.user_id
            WHERE s.paid_until IS NOT NULL
            GROUP BY u.telegram_id, u.username, u.name, u.hc_balance
            '''
        ).fetchall()
    def _parse_paid_until(value):
        if value is None:
            return None
        try:
            dt = datetime.datetime.fromisoformat(str(value))
        except Exception:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        else:
            dt = dt.astimezone(tz)
        return dt
    active_rows = []
    for row in rows:
        paid_until_dt = _parse_paid_until(row['paid_until'])
        if paid_until_dt and paid_until_dt > now:
            active_rows.append((paid_until_dt, row))
    if not active_rows:
        await update.message.reply_text('Нет активных подписчиков.')
        return
    active_rows.sort(key=lambda item: item[0], reverse=True)
    lines = []
    for paid_until_dt, row in active_rows:
        formatted_until = paid_until_dt.strftime('%d.%m.%Y %H:%M')
        lines.append(
            f"{row['telegram_id']} | {row['username'] or '-'} | {row['name'] or '-'} | HC: {row['hc_balance'] if row['hc_balance'] is not None else 0} | подписка до: {formatted_until}"
        )
    header = 'Активные подписчики:\n\n'
    message = header + '\n'.join(lines)
    for i in range(0, len(message), 4000):
        await update.message.reply_text(message[i:i + 4000])


# --- Рассылка по списку пользователей ---
async def message_users_bulk_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return ConversationHandler.END
    for key in (
        'bulk_targets',
        'bulk_text',
        'bulk_dt_utc',
        'bulk_dt_desc',
        'bulk_photo_file_id',
    ):
        context.user_data.pop(key, None)
    await update.message.reply_text(
        'Вставьте список пользователей (по одному @username или ID на строку). Можно использовать /cancel для отмены.'
    )
    return BULK_MSG_WAIT_RECIPIENTS


async def message_users_bulk_recipients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = (update.message.text or '').strip()
    if not raw_text:
        await update.message.reply_text('Список пуст. Вставьте пользователей ещё раз (или /cancel).')
        return BULK_MSG_WAIT_RECIPIENTS
    identifiers = [line.strip() for line in raw_text.splitlines() if line.strip()]
    targets = []
    missing = []
    seen_ids = set()
    for identifier in identifiers:
        user, label = _resolve_user(identifier)
        if not user:
            missing.append(identifier)
            continue
        user_id = user[0]
        if user_id in seen_ids:
            continue
        seen_ids.add(user_id)
        display = label or (f"@{user[1]}" if user[1] else f"id {user_id}")
        name = user[2] or ''
        if name:
            display = f"{display} ({name})"
        targets.append({'user_id': int(user_id), 'label': display})
    if not targets:
        msg = 'Не удалось найти ни одного пользователя из списка. Проверьте @username и отправьте снова (или /cancel).'
        if missing:
            msg += '\nНе найдены: ' + ', '.join(missing)
        await update.message.reply_text(msg)
        return BULK_MSG_WAIT_RECIPIENTS
    context.user_data['bulk_targets'] = targets
    summary_lines = [f"Найдено получателей: {len(targets)}"]
    preview = [f"• {item['label']}" for item in targets]
    max_preview = 20
    if len(preview) > max_preview:
        summary_lines.extend(preview[:max_preview])
        summary_lines.append(f"… и ещё {len(preview) - max_preview}")
    else:
        summary_lines.extend(preview)
    if missing:
        summary_lines.append('')
        summary_lines.append('Не найдены и будут пропущены:')
        summary_lines.extend([f"• {item}" for item in missing])
    await update.message.reply_text('\n'.join(summary_lines))
    await update.message.reply_text(
        'Введите текст сообщения. HTML-разметка поддерживается (или /cancel).'
    )
    return BULK_MSG_WAIT_TEXT


async def message_users_bulk_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    if not text:
        await update.message.reply_text('Пустой текст. Введите сообщение (или /cancel).')
        return BULK_MSG_WAIT_TEXT
    context.user_data['bulk_text'] = text
    await update.message.reply_text(
        "Когда отправить? Напишите 'сейчас' или дату и время в формате дд.мм.гг чч:мм (МСК), например: 05.09.25 10:30"
    )
    return BULK_MSG_WAIT_SCHEDULE


async def message_users_bulk_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import datetime
    value = (update.message.text or '').strip()
    if not value:
        await update.message.reply_text(
            "Ответ не распознан. Напишите 'сейчас' или дату/время в формате дд.мм.гг чч:мм (МСК)."
        )
        return BULK_MSG_WAIT_SCHEDULE
    lower = value.lower()
    if lower in {'сейчас', 'now', 'сразу', 'немедленно'}:
        context.user_data['bulk_dt_utc'] = None
        context.user_data['bulk_dt_desc'] = 'как можно скорее'
    else:
        dt_msk = None
        for fmt in ('%d.%m.%y %H:%M', '%d.%m.%Y %H:%M'):
            try:
                dt_msk = datetime.datetime.strptime(value, fmt)
                break
            except Exception:
                continue
        if dt_msk is None:
            await update.message.reply_text(
                "Неверный формат даты/времени. Укажите в формате дд.мм.гг чч:мм (МСК), например: 05.09.25 10:30"
            )
            return BULK_MSG_WAIT_SCHEDULE
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo('Europe/Moscow')
        except Exception:
            tz = datetime.timezone(datetime.timedelta(hours=3))
        if dt_msk.tzinfo is None:
            dt_msk = dt_msk.replace(tzinfo=tz)
        else:
            dt_msk = dt_msk.astimezone(tz)
        dt_utc = dt_msk.astimezone(datetime.timezone.utc)
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if dt_utc <= now_utc + datetime.timedelta(seconds=30):
            await update.message.reply_text('Время должно быть в будущем. Укажите дату/время в формате дд.мм.гг чч:мм (МСК).')
            return BULK_MSG_WAIT_SCHEDULE
        context.user_data['bulk_dt_utc'] = dt_utc.isoformat()
        context.user_data['bulk_dt_desc'] = value
    await update.message.reply_text('Нужна ли картинка? (да/нет)')
    return BULK_MSG_WAIT_PHOTO_DECISION


async def message_users_bulk_photo_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ans = (update.message.text or '').strip().lower()
    if ans in _MSG_USER_NO:
        context.user_data['bulk_photo_file_id'] = None
        return await _complete_message_users_bulk(update, context)
    if ans in _MSG_USER_YES:
        await update.message.reply_text("Отправьте изображение одним сообщением (или напишите 'нет').")
        return BULK_MSG_WAIT_PHOTO
    await update.message.reply_text("Ответьте 'да' или 'нет'.")
    return BULK_MSG_WAIT_PHOTO_DECISION


async def message_users_bulk_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo_id = update.message.photo[-1].file_id
        context.user_data['bulk_photo_file_id'] = photo_id
        return await _complete_message_users_bulk(update, context)
    text = (update.message.text or '').strip().lower()
    if text in _MSG_USER_NO:
        context.user_data['bulk_photo_file_id'] = None
        return await _complete_message_users_bulk(update, context)
    await update.message.reply_text('Не удалось распознать фото. Отправьте изображение или напишите "нет".')
    return BULK_MSG_WAIT_PHOTO


async def message_users_bulk_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for key in (
        'bulk_targets',
        'bulk_text',
        'bulk_dt_utc',
        'bulk_dt_desc',
        'bulk_photo_file_id',
    ):
        context.user_data.pop(key, None)
    await update.message.reply_text('Рассылка по списку отменена.')
    return ConversationHandler.END


async def _complete_message_users_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import datetime
    targets = context.user_data.get('bulk_targets') or []
    text = context.user_data.get('bulk_text') or ''
    dt_utc_str = context.user_data.get('bulk_dt_utc')
    dt_desc = context.user_data.get('bulk_dt_desc') or 'как можно скорее'
    photo_id = context.user_data.get('bulk_photo_file_id')
    if not targets or not text:
        await update.message.reply_text('Получатели или текст не найдены. Запустите заново: /message_users.')
        return ConversationHandler.END
    dt_utc = None
    if dt_utc_str:
        try:
            dt_utc = datetime.datetime.fromisoformat(dt_utc_str)
        except Exception:
            dt_utc = None
    job_queue = getattr(getattr(context, 'application', None), 'job_queue', None)
    if dt_utc:
        now = datetime.datetime.now(datetime.timezone.utc)
        delay = max(0, int((dt_utc - now).total_seconds())) if dt_utc > now else 0
        job_data = {
            'text': text,
            'photo': photo_id,
            'targets': targets,
            'admin_chat_id': update.effective_chat.id if update.effective_chat else None,
        }
        if job_queue is not None:
            job_queue.run_once(message_users_bulk_job, when=delay, data=job_data)
        else:
            import asyncio
            from types import SimpleNamespace
            async def _fallback():
                if delay:
                    await asyncio.sleep(delay)
                fake_ctx = SimpleNamespace(bot=context.bot, job=SimpleNamespace(data=job_data), application=context.application)
                await message_users_bulk_job(fake_ctx)
            asyncio.create_task(_fallback())
        await update.message.reply_text(f'Рассылка запланирована на {dt_desc} (МСК).')
    else:
        successes, failures = await _dispatch_bulk_messages(context.bot, targets, text, photo_id)
        result_text = f'Рассылка отправлена. Успешно: {successes} из {len(targets)}.'
        if failures:
            failed_labels = ', '.join(f['label'] for f in failures[:10])
            if len(failures) > 10:
                failed_labels += f" и ещё {len(failures) - 10}"
            result_text += f'\nНе удалось доставить: {failed_labels}'
        await update.message.reply_text(result_text)
    for key in ('bulk_targets', 'bulk_text', 'bulk_dt_utc', 'bulk_dt_desc', 'bulk_photo_file_id'):
        context.user_data.pop(key, None)
    return ConversationHandler.END


async def message_users_bulk_job(context: ContextTypes.DEFAULT_TYPE):
    job = getattr(context, 'job', None)
    data = job.data if job and job.data else {}
    targets = data.get('targets') or []
    text = data.get('text') or ''
    photo_id = data.get('photo')
    admin_chat_id = data.get('admin_chat_id')
    if not text or not targets:
        return
    successes, failures = await _dispatch_bulk_messages(context.bot, targets, text, photo_id)
    if admin_chat_id:
        summary = f'Рассылка завершена. Успешно: {successes} из {len(targets)}.'
        if failures:
            failed_labels = ', '.join(f['label'] for f in failures[:10])
            if len(failures) > 10:
                failed_labels += f" и ещё {len(failures) - 10}"
            summary += f'\nНе удалось доставить: {failed_labels}'
        try:
            await context.bot.send_message(chat_id=admin_chat_id, text=summary)
        except Exception:
            pass


async def _dispatch_bulk_messages(bot, targets, text, photo_id):
    successes = 0
    failures = []
    for target in targets:
        chat_id = target.get('user_id')
        label = target.get('label', str(chat_id))
        try:
            await _send_message_with_optional_photo(bot, int(chat_id), text, photo_id)
            successes += 1
        except Exception as exc:
            failures.append({'label': label, 'error': str(exc)})
            try:
                await bot.send_message(chat_id=int(chat_id), text=text)
            except Exception:
                pass
            logger.warning('Failed to send bulk message to %s: %s', label, exc)
    return successes, failures


async def challenge_rosters_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """РђРґРјРёРЅ-РєРѕРјР°РЅРґР°: /challenge_rosters <challenge_id>
    РџРѕРєР°Р·С‹РІР°РµС‚ СЃРїРёСЃРѕРє РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№, РёС… СЃС‚Р°С‚СѓСЃ Р·Р°СЏРІРєРё, СЃС‚Р°РІРєСѓ Рё РІС‹Р±СЂР°РЅРЅС‹С… РёРіСЂРѕРєРѕРІ (РЅР°РїР°РґР°СЋС‰РёР№/Р·Р°С‰РёС‚РЅРёРє/РІСЂР°С‚Р°СЂСЊ).
    """
    if not await admin_only(update, context):
        return
    # Р Р°Р·Р±РѕСЂ Р°СЂРіСѓРјРµРЅС‚Р°
    challenge_id = None
    try:
        if context.args and len(context.args) >= 1:
            challenge_id = int(context.args[0])
    except Exception:
        challenge_id = None
    if not challenge_id:
        await update.message.reply_text("РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ: /challenge_rosters <challenge_id>")
        return

    # РџРѕР»СѓС‡Р°РµРј Р·Р°РїРёСЃРё Р·Р°СЏРІРѕРє СЃ СЋР·РµСЂР°РјРё
    try:
        with db.closing(db.sqlite3.connect(db.DB_NAME)) as conn:
            conn.row_factory = db.sqlite3.Row
            rows = conn.execute(
                '''
                SELECT ce.user_id,
                       u.username,
                       u.name,
                       ce.stake,
                       ce.forward_id,
                       ce.defender_id,
                       ce.goalie_id,
                       ce.status,
                       ce.created_at
                FROM challenge_entries AS ce
                LEFT JOIN users AS u ON u.telegram_id = ce.user_id
                WHERE ce.challenge_id = ?
                ORDER BY ce.created_at DESC
                ''', (challenge_id,)
            ).fetchall()
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° Р‘Р”: {e}")
        return

    if not rows:
        await update.message.reply_text(f"Р”Р»СЏ С‡РµР»Р»РµРЅРґР¶Р° #{challenge_id} Р·Р°СЏРІРєРё РЅРµ РЅР°Р№РґРµРЅС‹.")
        return

    def name_club(pid):
        if not pid:
            return "вЂ”"
        try:
            p = db.get_player_by_id(int(pid))
            if p:
                return f"{p[1]} ({p[3]})"
        except Exception:
            pass
        return str(pid)

    # Р¤РѕСЂРјРёСЂСѓРµРј СЃРѕРѕР±С‰РµРЅРёРµ СЃ СЂР°Р·Р±РёРµРЅРёРµРј РЅР° С‡Р°СЃС‚Рё
    parts = []
    cur_lines = [f"РЎРѕСЃС‚Р°РІС‹ СѓС‡Р°СЃС‚РЅРёРєРѕРІ С‡РµР»Р»РµРЅРґР¶Р° #{challenge_id}:", ""]
    for r in rows:
        uname = ("@" + (r["username"] or "").strip()) if r["username"] else "вЂ”"
        name = r["name"] or "вЂ”"
        status = (r["status"] or "").lower()
        stake = r["stake"] or 0
        fwd = name_club(r["forward_id"]) if r["forward_id"] else "вЂ”"
        dfd = name_club(r["defender_id"]) if r["defender_id"] else "вЂ”"
        gk = name_club(r["goalie_id"]) if r["goalie_id"] else "вЂ”"

        # РЎС‚Р°С‚СѓСЃ Р·РЅР°С‡РєРѕРј
        status_icon = {
            'in_progress': 'рџџЎ in_progress',
            'completed': 'рџџў completed',
            'canceled': 'вљЄ canceled',
            'refunded': 'вљЄ refunded',
        }.get(status, status or 'вЂ”')

        cur_lines.append(f"вЂў {uname} | {name} | {status_icon} | РЎС‚Р°РІРєР°: {stake} HC")
        cur_lines.append(f"РќР°РїР°РґР°СЋС‰РёР№: {fwd}")
        cur_lines.append(f"Р—Р°С‰РёС‚РЅРёРє: {dfd}")
        cur_lines.append(f"Р’СЂР°С‚Р°СЂСЊ: {gk}")
        cur_lines.append("")

        joined = "\n".join(cur_lines)
        if len(joined) > 3500:  # Р·Р°РїР°СЃ РґРѕ Р»РёРјРёС‚Р° Telegram РІ 4096
            parts.append(joined)
            cur_lines = []
    if cur_lines:
        parts.append("\n".join(cur_lines))

    for part in parts:
        try:
            await update.message.reply_text(part)
        except Exception:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=part)

async def admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id if update.effective_user else None
    if not is_admin(user_id):
        await update.message.reply_text('РќРµС‚ РґРѕСЃС‚СѓРїР°')
        return False
    return True

async def send_tour_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    РЎС†РµРЅР°СЂРёР№:
    1. РђРґРјРёРЅ РѕС‚РїСЂР°РІР»СЏРµС‚ /send_tour_image вЂ” Р±РѕС‚ РїСЂРѕСЃРёС‚ РїСЂРёРєСЂРµРїРёС‚СЊ РєР°СЂС‚РёРЅРєСѓ.
    2. РђРґРјРёРЅ РѕС‚РїСЂР°РІР»СЏРµС‚ С„РѕС‚Рѕ вЂ” Р±РѕС‚ СЃРѕС…СЂР°РЅСЏРµС‚, СЃРѕРѕР±С‰Р°РµС‚ РѕР± СѓСЃРїРµС…Рµ.
    """
    if not await admin_only(update, context):
        logger.info(f"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ {update.effective_user.id} РЅРµ Р°РґРјРёРЅ, РґРѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ.")
        return

    # Р•СЃР»Рё РєРѕРјР°РЅРґР° РІС‹Р·РІР°РЅР° Р±РµР· С„РѕС‚Рѕ, Р·Р°РїСЂР°С€РёРІР°РµРј С„РѕС‚Рѕ

    if not update.message.photo:
        context.user_data['awaiting_tour_image'] = True
        chat_id = update.effective_chat.id
        debug_info = f"[DEBUG] /send_tour_image chat_id: {chat_id}, user_data: {context.user_data}"
        await update.message.reply_text('РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РїСЂРёРєСЂРµРїРёС‚Рµ РєР°СЂС‚РёРЅРєСѓ СЃР»РµРґСѓСЋС‰РёРј СЃРѕРѕР±С‰РµРЅРёРµРј.')
        await update.message.reply_text(debug_info)
        logger.info(f"[DEBUG] РћР¶РёРґР°РЅРёРµ РєР°СЂС‚РёРЅРєРё РѕС‚ Р°РґРјРёРЅР° {update.effective_user.id}, user_data: {context.user_data}")
        return

    # Р•СЃР»Рё С„РѕС‚Рѕ РїСЂРёС€Р»Рѕ РїРѕСЃР»Рµ Р·Р°РїСЂРѕСЃР°


    if context.user_data.get('awaiting_tour_image'):
        logger.info(f"[DEBUG] РџРѕР»СѓС‡РµРЅРѕ С„РѕС‚Рѕ, user_data: {context.user_data}")
        try:
            photo = update.message.photo[-1]
            file = await photo.get_file()
            filename = f"tour_{photo.file_unique_id}.jpg"
            path = os.path.join(IMAGES_DIR, filename)
            await file.download_to_drive(path)
            with open(TOUR_IMAGE_PATH_FILE, 'w') as f:
                f.write(filename)
            context.user_data['awaiting_tour_image'] = False
            await update.message.reply_text(f'вњ… РљР°СЂС‚РёРЅРєР° РїСЂРёРЅСЏС‚Р° Рё СЃРѕС…СЂР°РЅРµРЅР° РєР°Рє `{filename}`. РћРЅР° Р±СѓРґРµС‚ СЂР°Р·РѕСЃР»Р°РЅР° РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј РїСЂРё РєРѕРјР°РЅРґРµ /tour.')
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f'[DEBUG] Р¤РѕС‚Рѕ РѕР±СЂР°Р±РѕС‚Р°РЅРѕ, СЃРѕС…СЂР°РЅРµРЅРѕ РєР°Рє {filename}')
            logger.info(f"РљР°СЂС‚РёРЅРєР° С‚СѓСЂР° СЃРѕС…СЂР°РЅРµРЅР°: {path} (РѕС‚ {update.effective_user.id})")
        except Exception as e:
            logger.error(f'РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РєР°СЂС‚РёРЅРєРё С‚СѓСЂР°: {e}')
            await update.message.reply_text(f'РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РєР°СЂС‚РёРЅРєРё: {e}')
        return

    # Р•СЃР»Рё С„РѕС‚Рѕ РїСЂРёС€Р»Рѕ Р±РµР· Р·Р°РїСЂРѕСЃР°
    await update.message.reply_text('РЎРЅР°С‡Р°Р»Р° РѕС‚РїСЂР°РІСЊС‚Рµ РєРѕРјР°РЅРґСѓ /send_tour_image, Р·Р°С‚РµРј С„РѕС‚Рѕ.')
    logger.info(f"Р¤РѕС‚Рѕ РїРѕР»СѓС‡РµРЅРѕ Р±РµР· Р·Р°РїСЂРѕСЃР° РѕС‚ {update.effective_user.id}")

async def process_tour_image_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        filename = f"tour_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        await file.download_to_drive(path)
        with open(TOUR_IMAGE_PATH_FILE, 'w') as f:
            f.write(filename)
        await update.message.reply_text(f'вњ… РљР°СЂС‚РёРЅРєР° РїСЂРёРЅСЏС‚Р° Рё СЃРѕС…СЂР°РЅРµРЅР° РєР°Рє `{filename}`. РћРЅР° Р±СѓРґРµС‚ СЂР°Р·РѕСЃР»Р°РЅР° РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј РїСЂРё РєРѕРјР°РЅРґРµ /tour.')
        logger.info(f"РљР°СЂС‚РёРЅРєР° С‚СѓСЂР° СЃРѕС…СЂР°РЅРµРЅР°: {path} (РѕС‚ {update.effective_user.id})")
    except Exception as e:
        logger.error(f'РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РєР°СЂС‚РёРЅРєРё С‚СѓСЂР°: {e}')
        await update.message.reply_text(f'РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РєР°СЂС‚РёРЅРєРё: {e}')

async def addhc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_only(update, context):
        return
    if len(context.args) != 2 or not context.args[1].isdigit():
        await update.message.reply_text('РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ: /addhc @username 100')
        return
    username = context.args[0].lstrip('@')
    amount = int(context.args[1])
    user = db.get_user_by_username(username)
    if not user:
        await update.message.reply_text('РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ.')
        return
    db.update_hc_balance(user[0], amount)
    new_balance = db.get_user_by_id(user[0])[3]
    await context.bot.send_message(chat_id=user[0], text=f'рџЋ‰ РўРµР±Рµ РЅР°С‡РёСЃР»РµРЅРѕ {amount} HC!\nрџ’° РќРѕРІС‹Р№ Р±Р°Р»Р°РЅСЃ: {new_balance} HC')
    await update.message.reply_text(f'РџРѕР»СЊР·РѕРІР°С‚РµР»СЋ @{username} РЅР°С‡РёСЃР»РµРЅРѕ {amount} HC.')

# --- Р РµРіРёСЃС‚СЂР°С†РёСЏ С‡РµР»Р»РµРЅРґР¶Р° (+ Р·Р°РіСЂСѓР·РєР° РєР°СЂС‚РёРЅРєРё) ---
CHALLENGE_MODE = 30
CHALLENGE_START = 31
CHALLENGE_DEADLINE = 32
CHALLENGE_END = 33
CHALLENGE_WAIT_IMAGE = 34

def _parse_iso(dt_str: str):
    import datetime
    try:
        return datetime.datetime.fromisoformat(dt_str)
    except Exception:
        return None

async def send_challenge_image_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return ConversationHandler.END
    context.user_data.pop('challenge_mode', None)
    context.user_data.pop('challenge_start', None)
    context.user_data.pop('challenge_deadline', None)
    context.user_data.pop('challenge_end', None)
    await update.message.reply_text(
        'РЎРѕР·РґР°РЅРёРµ С‡РµР»Р»РµРЅРґР¶Р°. Р’РІРµРґРёС‚Рµ РґР°С‚Сѓ РЎРўРђР РўРђ РІ С„РѕСЂРјР°С‚Рµ ISO, РЅР°РїСЂРёРјРµСЂ: 2025-08-08T12:00:00'
    )
    return CHALLENGE_START

async def challenge_input_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    dt = _parse_iso(text)
    if not dt:
        await update.message.reply_text('РќРµРєРѕСЂСЂРµРєС‚РЅР°СЏ РґР°С‚Р°. РџРѕРІС‚РѕСЂРёС‚Рµ РІ С„РѕСЂРјР°С‚Рµ ISO: 2025-08-08T12:00:00')
        return CHALLENGE_START
    context.user_data['challenge_start'] = text
    await update.message.reply_text('Р’РІРµРґРёС‚Рµ Р”Р•Р”Р›РђР™Рќ (РєСЂР°Р№РЅРёР№ СЃСЂРѕРє РІС‹Р±РѕСЂР° СЃРѕСЃС‚Р°РІР°) РІ С„РѕСЂРјР°С‚Рµ ISO: 2025-08-09T18:00:00')
    return CHALLENGE_DEADLINE

async def challenge_input_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    dt = _parse_iso(text)
    if not dt:
        await update.message.reply_text('РќРµРєРѕСЂСЂРµРєС‚РЅР°СЏ РґР°С‚Р°. РџРѕРІС‚РѕСЂРёС‚Рµ РґРµРґР»Р°Р№РЅ РІ С„РѕСЂРјР°С‚Рµ ISO.')
        return CHALLENGE_DEADLINE
    # РџСЂРѕРІРµСЂРёРј РїРѕСЂСЏРґРѕРє
    sd = _parse_iso(context.user_data.get('challenge_start', ''))
    if not sd or not (sd < dt):
        await update.message.reply_text('Р”РµРґР»Р°Р№РЅ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РџРћРЎР›Р• РґР°С‚С‹ СЃС‚Р°СЂС‚Р°. РџРѕРІС‚РѕСЂРёС‚Рµ РІРІРѕРґ РґРµРґР»Р°Р№РЅР°.')
        return CHALLENGE_DEADLINE
    context.user_data['challenge_deadline'] = text
    await update.message.reply_text('Р’РІРµРґРёС‚Рµ Р”РђРўРЈ РћРљРћРќР§РђРќРРЇ РёРіСЂС‹ РІ С„РѕСЂРјР°С‚Рµ ISO: 2025-08-12T23:59:59')
    return CHALLENGE_END

async def challenge_input_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    dt = _parse_iso(text)
    if not dt:
        await update.message.reply_text('РќРµРєРѕСЂСЂРµРєС‚РЅР°СЏ РґР°С‚Р°. РџРѕРІС‚РѕСЂРёС‚Рµ РґР°С‚Сѓ РѕРєРѕРЅС‡Р°РЅРёСЏ РІ С„РѕСЂРјР°С‚Рµ ISO.')
        return CHALLENGE_END
    sd = _parse_iso(context.user_data.get('challenge_start', ''))
    dl = _parse_iso(context.user_data.get('challenge_deadline', ''))
    if not sd or not dl or not (dl < dt):
        await update.message.reply_text('Р”Р°С‚Р° РѕРєРѕРЅС‡Р°РЅРёСЏ РґРѕР»Р¶РЅР° Р±С‹С‚СЊ РџРћРЎР›Р• РґРµРґР»Р°Р№РЅР°. РџРѕРІС‚РѕСЂРёС‚Рµ РґР°С‚Сѓ РѕРєРѕРЅС‡Р°РЅРёСЏ.')
        return CHALLENGE_END
    context.user_data['challenge_end'] = text
    await update.message.reply_text('РўРµРїРµСЂСЊ РїСЂРёС€Р»РёС‚Рµ РљРђР РўРРќРљРЈ С‡РµР»Р»РµРЅРґР¶Р° СЃРѕРѕР±С‰РµРЅРёРµРј РІ С‡Р°С‚.')
    return CHALLENGE_WAIT_IMAGE

async def send_challenge_image_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # РЎРѕС…СЂР°РЅСЏРµРј С„РѕС‚Рѕ
        photo = update.message.photo[-1]
        file = await photo.get_file()
        filename = f"challenge_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        await file.download_to_drive(path)
        with open(CHALLENGE_IMAGE_PATH_FILE, 'w') as f:
            f.write(filename)

        # Р РµРіРёСЃС‚СЂРёСЂСѓРµРј С‡РµР»Р»РµРЅРґР¶ РІ Р‘Р”
        start_date = context.user_data.get('challenge_start')
        deadline = context.user_data.get('challenge_deadline')
        end_date = context.user_data.get('challenge_end')
        image_file_id = getattr(photo, 'file_id', '') or ''
        age_mode = context.user_data.get('challenge_mode', 'default')
        ch_id = db.create_challenge(start_date, deadline, end_date, filename, image_file_id, age_mode)

        await update.message.reply_text(
            f'вњ… Р§РµР»Р»РµРЅРґР¶ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅ (id={ch_id}). РљР°СЂС‚РёРЅРєР° СЃРѕС…СЂР°РЅРµРЅР° РєР°Рє `{filename}`.'
        )
        logger.info(f"Р§РµР»Р»РµРЅРґР¶ {ch_id} СЃРѕР·РґР°РЅ: {start_date} / {deadline} / {end_date}, image={path}")
    except Exception as e:
        logger.error(f'РћС€РёР±РєР° РїСЂРё СЂРµРіРёСЃС‚СЂР°С†РёРё С‡РµР»Р»РµРЅРґР¶Р°: {e}')
        await update.message.reply_text(f'РћС€РёР±РєР° РїСЂРё СЂРµРіРёСЃС‚СЂР°С†РёРё С‡РµР»Р»РµРЅРґР¶Р°: {e}')
    finally:
        # РћС‡РёСЃС‚РёРј РІСЂРµРјРµРЅРЅС‹Рµ РґР°РЅРЅС‹Рµ
        for k in ('challenge_mode','challenge_start','challenge_deadline','challenge_end'):
            context.user_data.pop(k, None)
    return ConversationHandler.END

# --- РњР°РіР°Р·РёРЅ: РѕРїРёСЃР°РЅРёРµ + РєР°СЂС‚РёРЅРєР° ---
SHOP_TEXT_WAIT = 41
SHOP_IMAGE_WAIT = 42

async def add_image_shop_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text(
        "РќР°РїРёС€РёС‚Рµ С‚РµРєСЃС‚ РѕРїРёСЃР°РЅРёСЏ РјР°РіР°Р·РёРЅР°. РњРѕР¶РµС‚Рµ РѕС„РѕСЂРјРёС‚СЊ Р°РєРєСѓСЂР°С‚РЅРѕ (РѕР±С‹С‡РЅС‹Р№ С‚РµРєСЃС‚)."
    )
    return SHOP_TEXT_WAIT

async def add_image_shop_text(update, context):
    text = (update.message.text or '').strip()
    try:
        db.update_shop_text(text)
    except Exception:
        pass
    await update.message.reply_text("РўРµРїРµСЂСЊ РѕС‚РїСЂР°РІСЊС‚Рµ РєР°СЂС‚РёРЅРєСѓ РјР°РіР°Р·РёРЅР° РѕРґРЅРёРј С„РѕС‚Рѕ СЃРѕРѕР±С‰РµРЅРёРµРј.")
    return SHOP_IMAGE_WAIT

async def add_image_shop_photo(update, context):
    if not update.message.photo:
        await update.message.reply_text("РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РѕС‚РїСЂР°РІСЊС‚Рµ РѕРґРЅРѕ С„РѕС‚Рѕ.")
        return SHOP_IMAGE_WAIT
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        filename = f"shop_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        await file.download_to_drive(path)
        # РЎРѕС…СЂР°РЅРёРј file_id РґР»СЏ Р±С‹СЃС‚СЂРѕРіРѕ РїРѕРІС‚РѕСЂРЅРѕРіРѕ РѕС‚РїСЂР°РІР»РµРЅРёСЏ
        db.update_shop_image(filename, photo.file_id)
        await update.message.reply_text("Р“РѕС‚РѕРІРѕ. РњР°РіР°Р·РёРЅ РѕР±РЅРѕРІР»С‘РЅ.")
        logger.info(f"РњР°РіР°Р·РёРЅ РѕР±РЅРѕРІР»С‘РЅ: text set, image {filename}")
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РєР°СЂС‚РёРЅРєРё РјР°РіР°Р·РёРЅР°: {e}")
        await update.message.reply_text(f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РєР°СЂС‚РёРЅРєРё: {e}")
    return ConversationHandler.END

async def send_challenge_image_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text('РћС‚РјРµРЅРµРЅРѕ.')
    except Exception:
        pass
    for k in ('challenge_mode','challenge_start','challenge_deadline','challenge_end'):
        context.user_data.pop(k, None)
    return ConversationHandler.END

async def send_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_only(update, context):
        return
    users = db.get_all_users()
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        filename = f"results_{photo.file_unique_id}.jpg"
        path = os.path.join(IMAGES_DIR, filename)
        await file.download_to_drive(path)
        success, failed = await send_message_to_users(context.bot, users, photo_path=path, caption='рџ“Љ Р РµР·СѓР»СЊС‚Р°С‚С‹ С‚СѓСЂР°:')
        await update.message.reply_text(f'Р РµР·СѓР»СЊС‚Р°С‚С‹ (С„РѕС‚Рѕ) СЂР°Р·РѕСЃР»Р°РЅС‹. РЈСЃРїРµС€РЅРѕ: {success}, РѕС€РёР±РєРё: {failed}')
    elif context.args:
        text = ' '.join(context.args)
        success, failed = await send_message_to_users(context.bot, users, text=f'рџ“Љ Р РµР·СѓР»СЊС‚Р°С‚С‹ С‚СѓСЂР°:\n{text}')
        await update.message.reply_text(f'Р РµР·СѓР»СЊС‚Р°С‚С‹ (С‚РµРєСЃС‚) СЂР°Р·РѕСЃР»Р°РЅС‹. РЈСЃРїРµС€РЅРѕ: {success}, РѕС€РёР±РєРё: {failed}')
    else:
        await update.message.reply_text('РџСЂРёС€Р»РёС‚Рµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ РёР»Рё С‚РµРєСЃС‚ РїРѕСЃР»Рµ РєРѕРјР°РЅРґС‹.')

# --- РЈРїСЂР°РІР»РµРЅРёРµ С‡РµР»Р»РµРЅРґР¶Р°РјРё (СЃРїРёСЃРѕРє/СѓРґР°Р»РµРЅРёРµ) ---
async def list_challenges(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_only(update, context):
        return
    try:
        rows = db.get_all_challenges()
        if not rows:
            await update.message.reply_text('Challenge list is empty.')
            return
        lines = []
        for r in rows:
            ch_id = r[0]
            start_date = r[1]
            deadline = r[2]
            end_date = r[3]
            image_filename = r[4] if len(r) > 4 else ''
            status = r[5] if len(r) > 5 else ''
            image_file_id = r[6] if len(r) > 6 else ''
            age_mode = (r[7] if len(r) > 7 else 'default') or 'default'
            mode_label = 'U21 only' if age_mode == 'under21' else 'regular'
            lines.append(
                "id={id} | {status}\nmode: {mode}\nstart: {start}\ndeadline: {deadline}\nend: {end}\nimage: {image}\n-".format(
                    id=ch_id,
                    status=status,
                    mode=mode_label,
                    start=start_date,
                    deadline=deadline,
                    end=end_date,
                    image=image_filename or image_file_id,
                )
            )
        msg = "\n".join(lines)
        for i in range(0, len(msg), 3500):
            await update.message.reply_text(msg[i:i+3500])
    except Exception as e:
        await update.message.reply_text(f'Failed to load challenges: {e}')
async def delete_challenge_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_only(update, context):
        return
    args = getattr(context, 'args', []) or []
    if not args or not args[0].isdigit():
        await update.message.reply_text('РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ: /delete_challenge <id>')
        return
    ch_id = int(args[0])
    try:
        deleted = db.delete_challenge(ch_id)
        if deleted:
            await update.message.reply_text(f'Р§РµР»Р»РµРЅРґР¶ id={ch_id} СѓРґР°Р»С‘РЅ.')
        else:
            await update.message.reply_text(f'Р§РµР»Р»РµРЅРґР¶ id={ch_id} РЅРµ РЅР°Р№РґРµРЅ.')
    except Exception as e:
        await update.message.reply_text(f'РћС€РёР±РєР° СѓРґР°Р»РµРЅРёСЏ С‡РµР»Р»РµРЅРґР¶Р°: {e}')

# --- РЈРїСЂР°РІР»РµРЅРёРµ С‚СѓСЂР°РјРё (admin) ---
from telegram.ext import CommandHandler, MessageHandler, filters, ConversationHandler
import json

TOUR_NAME, TOUR_START, TOUR_DEADLINE, TOUR_END, TOUR_CONFIRM = range(100, 105)

# --- Р•Р”РРќР«Р™ РџРђРљР•РўРќР«Р™ Р”РРђР›РћР“ РЎРћР—Р”РђРќРРЇ РўРЈР Рђ ---
# Р­С‚Р°РїС‹: РёРјСЏ -> РґР°С‚Р° СЃС‚Р°СЂС‚Р° -> РґРµРґР»Р°Р№РЅ -> РѕРєРѕРЅС‡Р°РЅРёРµ -> С„РѕС‚Рѕ -> СЂРѕСЃС‚РµСЂ -> С„РёРЅР°Р»
CT_NAME, CT_START, CT_DEADLINE, CT_END, CT_IMAGE, CT_ROSTER = range(200, 206)

async def create_tour_full_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    # РћС‡РёСЃС‚РёРј РІСЂРµРјРµРЅРЅС‹Рµ РґР°РЅРЅС‹Рµ РґРёР°Р»РѕРіР°
    for k in ['ct_name', 'ct_start', 'ct_deadline', 'ct_end', 'ct_image_filename', 'ct_tour_id']:
        context.user_data.pop(k, None)
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РЅР°Р·РІР°РЅРёРµ С‚СѓСЂР°:")
    return CT_NAME

async def create_tour_full_name(update, context):
    context.user_data['ct_name'] = (update.message.text or '').strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РґР°С‚Сѓ СЃС‚Р°СЂС‚Р° С‚СѓСЂР° (РґРґ.РјРј.РіРі):")
    return CT_START

async def create_tour_full_start_date(update, context):
    context.user_data['ct_start'] = (update.message.text or '').strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РґРµРґР»Р°Р№РЅ (РґРґ.РјРј.РіРі С‡С‡:РјРј):")
    return CT_DEADLINE

async def create_tour_full_deadline(update, context):
    context.user_data['ct_deadline'] = (update.message.text or '').strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РґР°С‚Сѓ РѕРєРѕРЅС‡Р°РЅРёСЏ С‚СѓСЂР° (РґРґ.РјРј.РіРі):")
    return CT_END

async def create_tour_full_end_date(update, context):
    context.user_data['ct_end'] = (update.message.text or '').strip()
    # РЎРѕР·РґР°С‘Рј С‚СѓСЂ СЃСЂР°Р·Сѓ, С‡С‚РѕР±С‹ РїРѕР»СѓС‡РёС‚СЊ id (Р°РІС‚РѕРёРЅРєСЂРµРјРµРЅС‚)
    try:
        tour_id = db.create_tour(
            context.user_data['ct_name'],
            context.user_data['ct_start'],
            context.user_data['ct_deadline'],
            context.user_data['ct_end']
        )
        context.user_data['ct_tour_id'] = tour_id
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ С‚СѓСЂР°: {e}")
        return ConversationHandler.END
    await update.message.reply_text("РўРµРїРµСЂСЊ РѕС‚РїСЂР°РІСЊС‚Рµ РѕРґРЅРѕ С„РѕС‚Рѕ РґР»СЏ С‚СѓСЂР° СЃРѕРѕР±С‰РµРЅРёРµРј СЃ С„РѕС‚РѕРіСЂР°С„РёРµР№.")
    return CT_IMAGE

async def create_tour_full_photo(update, context):
    if not update.message or not update.message.photo:
        await update.message.reply_text("РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РѕС‚РїСЂР°РІСЊС‚Рµ РёРјРµРЅРЅРѕ С„РѕС‚Рѕ.")
        return CT_IMAGE
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
        # РЎРѕС…СЂР°РЅРёРј "РїРѕСЃР»РµРґРЅСЋСЋ" РєР°СЂС‚РёРЅРєСѓ РґР»СЏ РїРѕРєР°Р·Р° РІ /tour
        try:
            with open(TOUR_IMAGE_PATH_FILE, 'w') as f:
                f.write(filename)
        except Exception:
            logger.warning("Failed to write TOUR_IMAGE_PATH_FILE", exc_info=True)
        context.user_data['ct_image_filename'] = filename
        # РџСЂРёРІСЏР¶РµРј РёР·РѕР±СЂР°Р¶РµРЅРёРµ Рє СЃРѕР·РґР°РЅРЅРѕРјСѓ С‚СѓСЂСѓ
        try:
            tour_id = context.user_data.get('ct_tour_id')
            if tour_id:
                db.update_tour_image(tour_id, filename, photo.file_id)
        except Exception:
            logger.warning("Failed to update tour image in DB", exc_info=True)
        await update.message.reply_text(
            "Р¤РѕС‚Рѕ СЃРѕС…СЂР°РЅРµРЅРѕ. РўРµРїРµСЂСЊ РѕС‚РїСЂР°РІСЊС‚Рµ СЂРѕСЃС‚РµСЂ РІ С„РѕСЂРјР°С‚Рµ:\n"
            "50: 28, 1, ...\n40: ... Рё С‚.Рґ. (СЂРѕРІРЅРѕ 20 РёРіСЂРѕРєРѕРІ)"
        )
        return CT_ROSTER
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СЃРѕС…СЂР°РЅРµРЅРёСЏ С„РѕС‚Рѕ: {e}")
        return ConversationHandler.END

async def create_tour_full_roster(update, context):
    text = (update.message.text or '').strip()
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    pairs = []
    try:
        for line in lines:
            if ':' not in line:
                await update.message.reply_text(f"РќРµРІРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚ СЃС‚СЂРѕРєРё: {line}")
                return CT_ROSTER
            cost_str, ids_str = line.split(':', 1)
            cost = int(cost_str.strip())
            id_list = [int(x.strip()) for x in ids_str.split(',') if x.strip()]
            for pid in id_list:
                pairs.append((cost, pid))
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СЂР°Р·Р±РѕСЂР°: {e}")
        return CT_ROSTER
    if len(pairs) != 20:
        await update.message.reply_text(f"РћС€РёР±РєР°: РґРѕР»Р¶РЅРѕ Р±С‹С‚СЊ СЂРѕРІРЅРѕ 20 РёРіСЂРѕРєРѕРІ, Р° РЅРµ {len(pairs)}. РџРѕРІС‚РѕСЂРёС‚Рµ РІРІРѕРґ.")
        return CT_ROSTER
    # РџСЂРѕРІРµСЂРёРј, С‡С‚Рѕ РёРіСЂРѕРєРё СЃСѓС‰РµСЃС‚РІСѓСЋС‚
    for cost, pid in pairs:
        player = db.get_player_by_id(pid)
        if not player:
            await update.message.reply_text(f"РРіСЂРѕРє СЃ id {pid} РЅРµ РЅР°Р№РґРµРЅ! РџРѕРІС‚РѕСЂРёС‚Рµ РІРІРѕРґ.")
            return CT_ROSTER
    # РЎРѕС…СЂР°РЅСЏРµРј СЂРѕСЃС‚РµСЂ РЅР° РєРѕРЅРєСЂРµС‚РЅС‹Р№ С‚СѓСЂ РІ С‚Р°Р±Р»РёС†Сѓ tour_players
    try:
        tour_id = context.user_data.get('ct_tour_id')
        if tour_id:
            db.clear_tour_players(tour_id)
            for cost, pid in pairs:
                db.add_tour_player(tour_id, pid, cost)
            # РћР±СЂР°С‚РЅР°СЏ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚СЊ: С‚Р°РєР¶Рµ Р·Р°РїРѕР»РЅРёРј СЃС‚Р°СЂСѓСЋ С‚Р°Р±Р»РёС†Сѓ tour_roster,
            # С‚.Рє. С‚РµРєСѓС‰Р°СЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЊСЃРєР°СЏ Р»РѕРіРёРєР° С‡РёС‚Р°РµС‚ РµС‘.
            try:
                db.clear_tour_roster()
                for cost, pid in pairs:
                    db.add_tour_roster_entry(pid, cost)
            except Exception:
                logger.warning("Failed to mirror roster into legacy tour_roster", exc_info=True)
        else:
            await update.message.reply_text("Р’РЅСѓС‚СЂРµРЅРЅСЏСЏ РѕС€РёР±РєР°: tour_id РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚.")
            return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"РћС€РёР±РєР° СЃРѕС…СЂР°РЅРµРЅРёСЏ СЂРѕСЃС‚РµСЂР°: {e}")
        return ConversationHandler.END
    tour_id = context.user_data.get('ct_tour_id')
    name = context.user_data.get('ct_name')
    start = context.user_data.get('ct_start')
    deadline = context.user_data.get('ct_deadline')
    end = context.user_data.get('ct_end')
    await update.message.reply_text(
        "РўСѓСЂ СЃРѕР·РґР°РЅ СѓСЃРїРµС€РЅРѕ!\n"
        f"ID: {tour_id}\nРќР°Р·РІР°РЅРёРµ: {name}\nРЎС‚Р°СЂС‚: {start}\nР”РµРґР»Р°Р№РЅ: {deadline}\nРћРєРѕРЅС‡Р°РЅРёРµ: {end}\n"
        f"РљР°СЂС‚РёРЅРєР°: {context.user_data.get('ct_image_filename', '-')}. Р РѕСЃС‚РµСЂ РїСЂРёРЅСЏС‚."
    )
    # РћС‡РёСЃС‚РёРј РІСЂРµРјРµРЅРЅС‹Рµ РґР°РЅРЅС‹Рµ
    for k in ['ct_name', 'ct_start', 'ct_deadline', 'ct_end', 'ct_image_filename', 'ct_tour_id']:
        context.user_data.pop(k, None)
    return ConversationHandler.END

async def create_tour_full_cancel(update, context):
    await update.message.reply_text("РЎРѕР·РґР°РЅРёРµ С‚СѓСЂР° РѕС‚РјРµРЅРµРЅРѕ.")
    # РћС‡РёСЃС‚РёРј РІСЂРµРјРµРЅРЅС‹Рµ РґР°РЅРЅС‹Рµ
    for k in ['ct_name', 'ct_start', 'ct_deadline', 'ct_end', 'ct_image_filename', 'ct_tour_id']:
        context.user_data.pop(k, None)
    return ConversationHandler.END

create_tour_full_conv = ConversationHandler(
    entry_points=[CommandHandler("create_tour_full", create_tour_full_start)],
    states={
        CT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_full_name)],
        CT_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_full_start_date)],
        CT_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_full_deadline)],
        CT_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_full_end_date)],
        CT_IMAGE: [MessageHandler(filters.PHOTO, create_tour_full_photo)],
        CT_ROSTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_full_roster)],
    },
    fallbacks=[CommandHandler("cancel", create_tour_full_cancel)],
    per_chat=True, per_user=True, per_message=False, allow_reentry=True,
)

async def create_tour_start(update, context):
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РЅР°Р·РІР°РЅРёРµ С‚СѓСЂР°:")
    return TOUR_NAME

async def create_tour_name(update, context):
    context.user_data['tour_name'] = update.message.text.strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РґР°С‚Сѓ СЃС‚Р°СЂС‚Р° С‚СѓСЂР° (РґРґ.РјРј.РіРі):")
    return TOUR_START

async def create_tour_start_date(update, context):
    context.user_data['tour_start'] = update.message.text.strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РґРµРґР»Р°Р№РЅ (РґРґ.РјРј.РіРі С‡С‡:РјРј):")
    return TOUR_DEADLINE

async def create_tour_deadline(update, context):
    context.user_data['tour_deadline'] = update.message.text.strip()
    await update.message.reply_text("Р’РІРµРґРёС‚Рµ РґР°С‚Сѓ РѕРєРѕРЅС‡Р°РЅРёСЏ С‚СѓСЂР° (РґРґ.РјРј.РіРі):")
    return TOUR_END

async def create_tour_end_date(update, context):
    context.user_data['tour_end'] = update.message.text.strip()
    summary = (
        f"РќР°Р·РІР°РЅРёРµ: {context.user_data['tour_name']}\n"
        f"РЎС‚Р°СЂС‚: {context.user_data['tour_start']}\n"
        f"Р”РµРґР»Р°Р№РЅ: {context.user_data['tour_deadline']}\n"
        f"РћРєРѕРЅС‡Р°РЅРёРµ: {context.user_data['tour_end']}\n"
        "\nРџРѕРґС‚РІРµСЂРґРёС‚СЊ СЃРѕР·РґР°РЅРёРµ С‚СѓСЂР°? (РґР°/РЅРµС‚)"
    )
    await update.message.reply_text(summary)
    return TOUR_CONFIRM

async def create_tour_confirm(update, context):
    text = update.message.text.strip().lower()
    if text not in ("РґР°", "РЅРµС‚"):
        await update.message.reply_text("РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РЅР°РїРёС€РёС‚Рµ 'РґР°' РёР»Рё 'РЅРµС‚'.")
        return TOUR_CONFIRM
    if text == "РЅРµС‚":
        await update.message.reply_text("РЎРѕР·РґР°РЅРёРµ С‚СѓСЂР° РѕС‚РјРµРЅРµРЅРѕ.")
        return ConversationHandler.END
    db.create_tour(
        context.user_data['tour_name'],
        context.user_data['tour_start'],
        context.user_data['tour_deadline'],
        context.user_data['tour_end']
    )
    await update.message.reply_text("РўСѓСЂ СѓСЃРїРµС€РЅРѕ СЃРѕР·РґР°РЅ!")
    return ConversationHandler.END

async def create_tour_cancel(update, context):
    await update.message.reply_text("РЎРѕР·РґР°РЅРёРµ С‚СѓСЂР° РѕС‚РјРµРЅРµРЅРѕ.")
    return ConversationHandler.END

create_tour_conv = ConversationHandler(
    entry_points=[CommandHandler("create_tour", create_tour_start)],
    states={
        TOUR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_name)],
        TOUR_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_start_date)],
        TOUR_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_deadline)],
        TOUR_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_end_date)],
        TOUR_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tour_confirm)],
    },
    fallbacks=[CommandHandler("cancel", create_tour_cancel)],
)

async def list_tours(update, context):
    if not await admin_only(update, context):
        return
    tours = db.get_all_tours()
    if not tours:
        await update.message.reply_text("РўСѓСЂРѕРІ РїРѕРєР° РЅРµС‚.")
        return
    msg = "РЎРїРёСЃРѕРє С‚СѓСЂРѕРІ:\n"
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
            f"РЎС‚Р°СЂС‚: {t[2]} | Р”РµРґР»Р°Р№РЅ: {t[3]} | РћРєРѕРЅС‡Р°РЅРёРµ: {t[4]}\n"
            f"РЎС‚Р°С‚СѓСЃ: {t[5]} | РџРѕР±РµРґРёС‚РµР»Рё: {winners}\n"
        )
    await update.message.reply_text(msg)

# --- Push Notifications ---
SEND_PUSH = 100

async def send_push_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """РќР°С‡Р°Р»Рѕ РїСЂРѕС†РµСЃСЃР° РѕС‚РїСЂР°РІРєРё push-СѓРІРµРґРѕРјР»РµРЅРёСЏ"""
    if not await admin_only(update, context):
        return ConversationHandler.END
        
    await update.message.reply_text(
        "вњ‰пёЏ Р’РІРµРґРёС‚Рµ С‚РµРєСЃС‚ push-СѓРІРµРґРѕРјР»РµРЅРёСЏ, РєРѕС‚РѕСЂРѕРµ Р±СѓРґРµС‚ РѕС‚РїСЂР°РІР»РµРЅРѕ РІСЃРµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј Р±РѕС‚Р°:\n"
        "(Р’С‹ РјРѕР¶РµС‚Рµ РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ HTML-СЂР°Р·РјРµС‚РєСѓ: <b>Р¶РёСЂРЅС‹Р№</b>, <i>РєСѓСЂСЃРёРІ</i>, <a href=\"URL\">СЃСЃС‹Р»РєР°</a>)\n\n"
        "Р”Р»СЏ РѕС‚РјРµРЅС‹ РІРІРµРґРёС‚Рµ /cancel"
    )
    return SEND_PUSH

async def send_push_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """РћС‚РїСЂР°РІРєР° push-СѓРІРµРґРѕРјР»РµРЅРёСЏ РІСЃРµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј"""
    message_text = update.message.text
    users = db.get_all_users()
    
    if not users:
        await update.message.reply_text("вќЊ Р’ Р±Р°Р·Рµ РґР°РЅРЅС‹С… РЅРµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№.")
        return ConversationHandler.END
    
    sent_count = 0
    failed_count = 0
    
    progress_msg = await update.message.reply_text(f"рџ”„ РћС‚РїСЂР°РІРєР° СѓРІРµРґРѕРјР»РµРЅРёСЏ {len(users)} РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј...")
    
    for user in users:
        try:
            user_id = user[0] if isinstance(user, (tuple, list)) else user.get('telegram_id')
            if not user_id:
                continue
                
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            sent_count += 1
            
            # РќРµ СЃРїР°РјРёРј СЃР»РёС€РєРѕРј Р±С‹СЃС‚СЂРѕ, С‡С‚РѕР±С‹ РЅРµ РїРѕР»СѓС‡РёС‚СЊ РѕРіСЂР°РЅРёС‡РµРЅРёРµ РѕС‚ Telegram
            if sent_count % 20 == 0:
                await asyncio.sleep(1)
                await progress_msg.edit_text(f"рџ”„ РћС‚РїСЂР°РІР»РµРЅРѕ {sent_count} РёР· {len(users)} СѓРІРµРґРѕРјР»РµРЅРёР№...")
                
        except Exception as e:
            logger.error(f"РћС€РёР±РєР° РїСЂРё РѕС‚РїСЂР°РІРєРµ СѓРІРµРґРѕРјР»РµРЅРёСЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ {user_id}: {e}")
            failed_count += 1
    
    await progress_msg.edit_text(
        f"вњ… Р Р°СЃСЃС‹Р»РєР° Р·Р°РІРµСЂС€РµРЅР°!\n"
        f"вЂў РћС‚РїСЂР°РІР»РµРЅРѕ: {sent_count}\n"
        f"вЂў РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РїСЂР°РІРёС‚СЊ: {failed_count}\n\n"
        f"РўРµРєСЃС‚ СѓРІРµРґРѕРјР»РµРЅРёСЏ:\n{message_text}"
    )
    return ConversationHandler.END

async def send_push_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """РћС‚РјРµРЅР° РѕС‚РїСЂР°РІРєРё push-СѓРІРµРґРѕРјР»РµРЅРёСЏ"""
    await update.message.reply_text("вќЊ РћС‚РїСЂР°РІРєР° СѓРІРµРґРѕРјР»РµРЅРёР№ РѕС‚РјРµРЅРµРЅР°.")
    return ConversationHandler.END

# Р РµРіРёСЃС‚СЂР°С†РёСЏ РѕР±СЂР°Р±РѕС‚С‡РёРєР° РґР»СЏ РєРѕРјР°РЅРґС‹ /push
push_conv = ConversationHandler(
    entry_points=[CommandHandler("push", send_push_start)],
    states={
        SEND_PUSH: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, send_push_process),
            CommandHandler("cancel", send_push_cancel)
        ]
    },
    fallbacks=[CommandHandler("cancel", send_push_cancel)]
)

# --- Р Р°СЃСЃС‹Р»РєР° С‚РѕР»СЊРєРѕ РїРѕРґРїРёСЃС‡РёРєР°Рј ---
BROADCAST_SUBS_WAIT_TEXT = 12001
BROADCAST_SUBS_WAIT_DATETIME = 12003
BROADCAST_SUBS_CONFIRM = 12002

# --- Message to a single user ---
BULK_MSG_WAIT_RECIPIENTS = 12110
BULK_MSG_WAIT_TEXT = 12111
BULK_MSG_WAIT_SCHEDULE = 12112
BULK_MSG_WAIT_PHOTO_DECISION = 12113
BULK_MSG_WAIT_PHOTO = 12114

MSG_USER_WAIT_TARGET = 12100
MSG_USER_WAIT_TEXT = 12101
MSG_USER_WAIT_DATETIME = 12102
MSG_USER_WAIT_PHOTO_DECISION = 12103
MSG_USER_WAIT_PHOTO = 12104
MSG_USER_CONFIRM = 12105

_MSG_USER_YES = {'да', 'д', 'yes', 'y', 'ок', 'ok', 'ага'}
_MSG_USER_NO = {'нет', 'н', 'no', 'n', 'не'}

BLOCK_USER_WAIT_TARGET = 12200
BLOCK_USER_WAIT_USERNAME = 12201
BLOCK_USER_WAIT_PASSWORD = 12202
BLOCK_USER_WAIT_CONFIRM = 12203

_BLOCK_USER_YES = {'да', 'д', 'yes', 'y', 'ок', 'ok'}
_BLOCK_USER_NO = {'нет', 'н', 'no', 'n'}


_BLOCK_USER_NOTIFICATION = (
    "⚠️ Обнаружена подозрительная активность на вашем аккаунте. "
    "Мы вынуждены временно заблокировать доступ до выяснения обстоятельств.\n\n"
    "Возможные причины:\n"
    "- Нарушение правил платформы;\n"
    "- Нарушение законодательства;\n"
    "- Подозрение в мошенничестве;\n"
    "- Накрутка ботов или другой искусственной активности.\n\n"
)


async def message_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return ConversationHandler.END
    for key in ('msg_user_id', 'msg_user_label', 'msg_text', 'msg_dt_utc', 'msg_dt_input', 'msg_photo_file_id'):
        context.user_data.pop(key, None)
    await update.message.reply_text(
        "Введите @username или ID пользователя, которому отправить сообщение (или /cancel):"
    )
    return MSG_USER_WAIT_TARGET

def _resolve_user(identifier: str):
    """Возвращает кортеж (user_row, label) по @username или числовому id.
    user_row — запись из таблицы users, label — строка для отображения цели."""
    identifier = (identifier or '').strip()
    user = None
    label = ''
    if not identifier:
        return None, ''
    if identifier.startswith('@') or not identifier.isdigit():
        username = identifier.lstrip('@')
        try:
            user = db.get_user_by_username(username)
        except Exception:
            user = None
        label = f"@{username}"
    else:
        try:
            user_id = int(identifier)
        except Exception:
            user_id = None
        if user_id is not None:
            try:
                user = db.get_user_by_id(user_id)
            except Exception:
                user = None
            label = f"id {user_id}"
    return user, label

async def message_user_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identifier = (update.message.text or '').strip()
    user, label = _resolve_user(identifier)
    if not user:
        await update.message.reply_text(
            "Пользователь не найден. Введите @username или ID ещё раз (или /cancel):"
        )
        return MSG_USER_WAIT_TARGET
    context.user_data['msg_user_id'] = user[0]  # users.telegram_id
    context.user_data['msg_user_label'] = label or (f"@{user[1]}" if user[1] else f"id {user[0]}")
    await update.message.reply_text(
        f"Цель: {context.user_data['msg_user_label']}\nТеперь отправьте текст сообщения (или /cancel).\n"
        "Поддерживается HTML-разметка (<b>жирный</b>, <i>курсив</i>, ссылки).",
        parse_mode='HTML'
    )
    return MSG_USER_WAIT_TEXT

async def message_user_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    if not text:
        await update.message.reply_text("Текст пуст. Введите текст сообщения (или /cancel):")
        return MSG_USER_WAIT_TEXT
    context.user_data['msg_text'] = text
    await update.message.reply_text(
        "Введите дату и время по МСК: дд.мм.гг чч:мм (или /cancel).\n"
        "Пример: 05.09.25 10:30"
    )
    return MSG_USER_WAIT_DATETIME

async def message_user_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = (update.message.text or '').strip()
    dt_msk = None
    for fmt in ("%d.%m.%y %H:%M", "%d.%m.%Y %H:%M"):
        try:
            dt_msk = datetime.datetime.strptime(s, fmt)
            break
        except Exception:
            pass
    if not dt_msk:
        await update.message.reply_text(
            "Неверный формат даты/времени. Введите в формате дд.мм.гг чч:мм (МСК), например: 05.09.25 10:30"
        )
        return MSG_USER_WAIT_DATETIME
    dt_utc = dt_msk - datetime.timedelta(hours=3)
    now_utc = datetime.datetime.utcnow()
    if dt_utc < now_utc:
        await update.message.reply_text("Время уже прошло. Введите дату/время в будущем (МСК):")
        return MSG_USER_WAIT_DATETIME
    context.user_data['msg_dt_utc'] = dt_utc.isoformat()
    context.user_data['msg_dt_input'] = s
    context.user_data.pop('msg_photo_file_id', None)
    await update.message.reply_text("Хотите добавить картинку к сообщению? Напишите 'да' или 'нет'.")
    return MSG_USER_WAIT_PHOTO_DECISION

async def _send_message_with_optional_photo(bot, chat_id, text, photo_id):
    text = text or ''
    if photo_id:
        caption = text if text and len(text) <= 1024 else None
        sent_caption = False
        try:
            if caption:
                await bot.send_photo(chat_id=chat_id, photo=photo_id, caption=caption, parse_mode='HTML')
                sent_caption = True
            else:
                await bot.send_photo(chat_id=chat_id, photo=photo_id)
        except Exception:
            if caption:
                try:
                    await bot.send_photo(chat_id=chat_id, photo=photo_id, caption=caption)
                    sent_caption = True
                except Exception:
                    await bot.send_photo(chat_id=chat_id, photo=photo_id)
            else:
                await bot.send_photo(chat_id=chat_id, photo=photo_id)
        if text and (not sent_caption or len(text) > 1024):
            try:
                await bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML', disable_web_page_preview=True)
            except Exception:
                await bot.send_message(chat_id=chat_id, text=text)
    elif text:
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML', disable_web_page_preview=True)
        except Exception:
            await bot.send_message(chat_id=chat_id, text=text)

async def _message_user_show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = context.user_data.get('msg_text', '')
    photo_id = context.user_data.get('msg_photo_file_id')
    when_desc = context.user_data.get('msg_dt_input') or 'указанное время'
    try:
        await update.message.reply_text("Предпросмотр сообщения:", parse_mode='HTML')
    except Exception:
        await update.message.reply_text("Предпросмотр сообщения:")
    await _send_message_with_optional_photo(context.bot, update.effective_chat.id, text, photo_id)
    target_label = context.user_data.get('msg_user_label') or 'указанного пользователя'
    await update.message.reply_text(
        f"Отправить пользователю {target_label} в {when_desc} (МСК)?\nНапишите 'да' для подтверждения или 'нет' для отмены."
    )
    return MSG_USER_CONFIRM

async def message_user_photo_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ans = (update.message.text or '').strip().lower()
    if ans in _MSG_USER_YES:
        context.user_data.pop('msg_photo_file_id', None)
        await update.message.reply_text("Прикрепите картинку (отправьте фото или напишите 'нет' для отправки без картинки, /cancel для отмены).")
        return MSG_USER_WAIT_PHOTO
    if ans in _MSG_USER_NO:
        context.user_data.pop('msg_photo_file_id', None)
        return await _message_user_show_preview(update, context)
    await update.message.reply_text("Пожалуйста, ответьте 'да' или 'нет'.")
    return MSG_USER_WAIT_PHOTO_DECISION

async def message_user_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if message and message.photo:
        context.user_data['msg_photo_file_id'] = message.photo[-1].file_id
        return await _message_user_show_preview(update, context)
    text = (message.text or '').strip().lower() if message and message.text else ''
    if text in _MSG_USER_NO:
        context.user_data.pop('msg_photo_file_id', None)
        return await _message_user_show_preview(update, context)
    await update.message.reply_text("Не удалось распознать изображение. Отправьте фото или напишите 'нет' для отправки без картинки (или /cancel).")
    return MSG_USER_WAIT_PHOTO

async def message_user_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ans = (update.message.text or '').strip().lower()
    if ans not in _MSG_USER_YES:
        for key in ('msg_user_id', 'msg_user_label', 'msg_text', 'msg_dt_utc', 'msg_dt_input', 'msg_photo_file_id'):
            context.user_data.pop(key, None)
        await update.message.reply_text("Отправка отменена.")
        return ConversationHandler.END
    text = context.user_data.get('msg_text') or ''
    user_id = context.user_data.get('msg_user_id')
    photo_id = context.user_data.get('msg_photo_file_id')
    if not text or not user_id:
        await update.message.reply_text("Не найдены получатель или текст. Запустите заново: /message_user")
        return ConversationHandler.END
    dt_utc = None
    try:
        dt_utc_str = context.user_data.get('msg_dt_utc')
        if dt_utc_str:
            dt_utc = datetime.datetime.fromisoformat(dt_utc_str)
    except Exception:
        dt_utc = None
    now = datetime.datetime.utcnow()
    delay = 0
    if dt_utc and dt_utc > now:
        delay = max(0, int((dt_utc - now).total_seconds()))
    try:
        jq = getattr(getattr(context, 'application', None), 'job_queue', None)
        job_data = {'text': text, 'user_id': int(user_id), 'photo': photo_id}
        if jq is not None:
            jq.run_once(
                message_user_job,
                when=delay,
                data=job_data
            )
        else:
            from types import SimpleNamespace
            async def _fallback_run():
                if delay:
                    await asyncio.sleep(delay)
                fake_ctx = SimpleNamespace(bot=context.bot, job=SimpleNamespace(data=job_data))
                await message_user_job(fake_ctx)
            asyncio.create_task(_fallback_run())
        when_desc = context.user_data.get('msg_dt_input') or 'как можно скорее'
        await update.message.reply_text(f"Сообщение запланировано на {when_desc} (МСК).")
    except Exception as e:
        await update.message.reply_text(f"Не удалось запланировать отправку: {e}")
    finally:
        for key in ('msg_user_id', 'msg_user_label', 'msg_text', 'msg_dt_utc', 'msg_dt_input', 'msg_photo_file_id'):
            context.user_data.pop(key, None)
    return ConversationHandler.END



async def block_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return ConversationHandler.END
    prompt = (
        "Введите ID пользователя, которого нужно заблокировать (или /cancel для отмены):"
    )
    await update.message.reply_text(prompt)
    return BLOCK_USER_WAIT_TARGET



async def block_user_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_id = (update.message.text or '').strip()
    if not raw_id.isdigit():
        await update.message.reply_text(
            "ID должен состоять только из цифр. Введите корректный ID (или /cancel для отмены):"
        )
        return BLOCK_USER_WAIT_TARGET
    target_id = int(raw_id)
    try:
        user_row = db.get_user_by_id(target_id)
    except Exception:
        user_row = None
    if not user_row:
        await update.message.reply_text(
            "Пользователь с таким ID не найден. Введите ID ещё раз (или /cancel для отмены):"
        )
        return BLOCK_USER_WAIT_TARGET
    if _is_user_blocked_safe(target_id):
        await update.message.reply_text("Этот пользователь уже заблокирован.")
        return ConversationHandler.END
    db_username = (user_row[1] or '').lower()
    context.user_data['block_user_id'] = target_id
    context.user_data['block_user_db_username'] = db_username
    context.user_data['block_user_username'] = ''
    context.user_data['block_user_label'] = f"ID {target_id}"
    await update.message.reply_text(
        "Введите @username пользователя (или '-' если его нет, /cancel для отмены):"
    )
    return BLOCK_USER_WAIT_USERNAME


async def block_user_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id = context.user_data.get('block_user_id')
    if not target_id:
        await update.message.reply_text("Не удалось обработать следующий шаг. Начните заново: /block_user")
        return ConversationHandler.END
    raw_username = (update.message.text or '').strip()
    db_username = (context.user_data.get('block_user_db_username') or '').lower()
    if raw_username == '-':
        if db_username:
            await update.message.reply_text(
                "В базе у пользователя указан username. Введите его в формате @username:"
            )
            return BLOCK_USER_WAIT_USERNAME
        username = ''
    else:
        if not raw_username.startswith('@') or len(raw_username) <= 1:
            await update.message.reply_text(
                "Укажите username в формате @username или '-' если его нет:"
            )
            return BLOCK_USER_WAIT_USERNAME
        username = raw_username[1:].strip()
        if not username:
            await update.message.reply_text(
                "Укажите username в формате @username или '-' если его нет:"
            )
            return BLOCK_USER_WAIT_USERNAME
        if db_username and username.lower() != db_username:
            await update.message.reply_text(
                "Введённый username не совпадает с данными в базе. Проверьте ввод и попробуйте ещё раз:"
            )
            return BLOCK_USER_WAIT_USERNAME
        try:
            other = db.get_user_by_username(username)
        except Exception:
            other = None
        if other and int(other[0]) != int(target_id):
            await update.message.reply_text(
                "Этот username принадлежит другому пользователю. Укажите корректный @username или '-':"
            )
            return BLOCK_USER_WAIT_USERNAME
    label = f"ID {target_id}"
    if raw_username != '-':
        label = f"ID {target_id} (@{username})"
        context.user_data['block_user_username'] = username
    else:
        context.user_data['block_user_username'] = ''
    context.user_data['block_user_label'] = label
    await update.message.reply_text("Введите пароль (или /cancel для отмены):")
    return BLOCK_USER_WAIT_PASSWORD



async def block_user_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    checker = _get_purge_password_checker()
    pw = (update.message.text or '').strip()
    if not checker(pw):
        await update.message.reply_text('Неверный пароль. Операция отменена.')
        for key in ('block_user_id', 'block_user_label', 'block_user_username', 'block_user_db_username', 'block_user_reason'):
            context.user_data.pop(key, None)
        return ConversationHandler.END
    label = context.user_data.get('block_user_label', 'пользователь')
    context.user_data['block_user_reason'] = _BLOCK_USER_NOTIFICATION
    preview = "\n".join([
        f"Подтвердите блокировку пользователя {label}.",
        "",
        f"Пользователь получит уведомление:\n{_BLOCK_USER_NOTIFICATION}",
        "",
        "Подтвердить блокировку? (да/нет)",
    ])
    await update.message.reply_text(preview)
    return BLOCK_USER_WAIT_CONFIRM



async def block_user_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = (update.message.text or '').strip().lower()
    if answer in _BLOCK_USER_NO:
        await update.message.reply_text('Операция отменена.')
        for key in ('block_user_id', 'block_user_label', 'block_user_username', 'block_user_db_username', 'block_user_reason'):
            context.user_data.pop(key, None)
        return ConversationHandler.END
    if answer not in _BLOCK_USER_YES:
        await update.message.reply_text("Напишите 'да' для подтверждения или 'нет' для отмены.")
        return BLOCK_USER_WAIT_CONFIRM
    target_id = context.user_data.get('block_user_id')
    label = context.user_data.get('block_user_label', 'пользователь')
    if not target_id:
        await update.message.reply_text('Не удалось определить пользователя. Попробуйте снова: /block_user')
        return ConversationHandler.END
    admin = update.effective_user
    reason_text = context.user_data.get('block_user_reason', _BLOCK_USER_NOTIFICATION)
    try:
        db.block_user(target_id, admin.id if admin else None, reason_text)
    except Exception as e:
        await update.message.reply_text(f'Не удалось заблокировать пользователя: {e}')
        for key in ('block_user_id', 'block_user_label', 'block_user_username', 'block_user_db_username', 'block_user_reason'):
            context.user_data.pop(key, None)
        return ConversationHandler.END
    try:
        await context.bot.send_message(chat_id=target_id, text=reason_text)
    except Exception:
        pass
    await update.message.reply_text(f'Пользователь {label} заблокирован.')
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f'Администратор {admin.id if admin else ""} заблокировал пользователя {label}.'
        )
    except Exception:
        pass
    for key in ('block_user_id', 'block_user_label', 'block_user_username', 'block_user_db_username', 'block_user_reason'):
        context.user_data.pop(key, None)
    return ConversationHandler.END




async def referral_review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not await admin_only(update, context):
        return
    data = (query.data or '').split(':')
    if len(data) != 4:
        try:
            await query.edit_message_text('⚠️ Некорректные данные заявки.')
        except Exception:
            pass
        return
    action, user_id_str, referrer_id_str = data[1], data[2], data[3]
    try:
        invited_id = int(user_id_str)
        referrer_id = int(referrer_id_str)
    except ValueError:
        try:
            await query.edit_message_text('⚠️ Некорректные параметры заявки.')
        except Exception:
            pass
        return

    admin = update.effective_user
    admin_id = admin.id if admin else None

    if action == 'approve':
        result = db.approve_referral(invited_id, admin_id)
        if result.get('status') != 'rewarded':
            try:
                await query.edit_message_text('⚠️ Заявка уже обработана или не найдена.')
            except Exception:
                pass
            return
        amount = result.get('amount', 0)
        balance = result.get('balance')
        balance_text = balance if balance is not None else '—'
        try:
            await context.bot.send_message(
                chat_id=result.get('referrer_id'),
                text=(
                    '🎉 Реферальный бонус подтверждён администратором.\n'
                    f'+{amount} HC начислены. Текущий баланс: {balance_text} HC.'
                )
            )
        except Exception:
            pass
        try:
            await query.edit_message_text(f'✅ Реферал {invited_id} одобрен. Начислено {amount} HC.')
        except Exception:
            pass
        return

    if action == 'deny':
        result = db.deny_referral(invited_id, admin_id, 'admin_denied')
        if result.get('status') != 'denied':
            try:
                await query.edit_message_text('⚠️ Заявка уже обработана или не найдена.')
            except Exception:
                pass
            return
        strike_count = result.get('strike_count', 0)
        disabled = result.get('disabled', False)
        try:
            text = '🚫 Реферальный бонус отклонён администратором.'
            if strike_count:
                text += f' Страйков: {strike_count}.'
            if disabled:
                text += ' Реферальная ссылка отключена.'
            await context.bot.send_message(chat_id=result.get('referrer_id'), text=text)
        except Exception:
            pass
        reply = f'🚫 Реферал {invited_id} отклонён. Страйков: {strike_count}.'
        if disabled:
            reply += ' Ссылка отключена.'
        try:
            await query.edit_message_text(reply)
        except Exception:
            pass
        return

    try:
        await query.edit_message_text('⚠️ Неизвестное действие для заявки.')
    except Exception:
        pass


async def block_user_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Операция отменена.')
    for key in ('block_user_id', 'block_user_label', 'block_user_username', 'block_user_db_username', 'block_user_reason'):
        context.user_data.pop(key, None)
    return ConversationHandler.END


async def message_user_job(context: ContextTypes.DEFAULT_TYPE):
    """JobQueue callback: отправка сообщения одному пользователю."""
    text = ''
    user_id = None
    photo_id = None
    try:
        job = getattr(context, 'job', None)
        if job and job.data:
            text = job.data.get('text') or ''
            user_id = job.data.get('user_id')
            photo_id = job.data.get('photo')
    except Exception:
        text = ''
    if not text or not user_id:
        return
    try:
        await _send_message_with_optional_photo(context.bot, int(user_id), text, photo_id)
    except Exception:
        try:
            await context.bot.send_message(chat_id=int(user_id), text=text)
        except Exception:
            pass

async def broadcast_subscribers_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text("Введите текст рассылки для подписчиков (или /cancel). Можно использовать HTML-разметку (<b>жирный</b>, <i>курсив</i>, ссылки):", parse_mode='HTML')
    return BROADCAST_SUBS_WAIT_TEXT

async def broadcast_subscribers_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    if not text:
        await update.message.reply_text("РџСѓСЃС‚РѕРµ СЃРѕРѕР±С‰РµРЅРёРµ. Р’РІРµРґРёС‚Рµ С‚РµРєСЃС‚ РёР»Рё /cancel:")
        return BROADCAST_SUBS_WAIT_TEXT
    context.user_data['broadcast_text'] = text
    await update.message.reply_text(
        "Укажите дату и время отправки в формате: дд.мм.гг чч:мм (МСК).\n"
        "Например: 05.09.25 10:30"
    )
    return BROADCAST_SUBS_WAIT_DATETIME

async def broadcast_subscribers_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """РџР°СЂСЃРёС‚ РІСЂРµРјСЏ РІ РњРЎРљ (UTC+3), СЃРѕС…СЂР°РЅСЏРµС‚ РІСЂРµРјСЏ РІ UTC Рё РїСЂРµРґР»Р°РіР°РµС‚ РїРѕРґС‚РІРµСЂРґРёС‚СЊ."""
    s = (update.message.text or '').strip()
    dt_msk = None
    for fmt in ("%d.%m.%y %H:%M", "%d.%m.%Y %H:%M"):
        try:
            dt_msk = datetime.datetime.strptime(s, fmt)
            break
        except Exception:
            pass
    if not dt_msk:
        await update.message.reply_text(
            "Неверный формат даты/времени. Введите в формате дд.мм.гг чч:мм (МСК), например: 05.09.25 10:30"
        )
        return BROADCAST_SUBS_WAIT_DATETIME
    # РџРµСЂРµРІРѕРґ РњРЎРљ (UTC+3) РІ UTC
    dt_utc = dt_msk - datetime.timedelta(hours=3)
    now_utc = datetime.datetime.utcnow()
    if dt_utc < now_utc:
        await update.message.reply_text("Время отправки в прошлом. Укажите дату/время в будущем (МСК):")
        return BROADCAST_SUBS_WAIT_DATETIME
    context.user_data['broadcast_dt_utc'] = dt_utc.isoformat()
    context.user_data['broadcast_dt_input'] = s

    # РџРѕРґСЃС‡РёС‚Р°С‚СЊ С‡РёСЃР»Рѕ Р°РєС‚РёРІРЅС‹С… РїРѕРґРїРёСЃС‡РёРєРѕРІ РЅР° С‚РµРєСѓС‰РёР№ РјРѕРјРµРЅС‚ (РґР»СЏ РёРЅС„РѕСЂРјР°С†РёРё)
    subs = db.get_all_subscriptions()  # [(user_id, paid_until)]
    targets = []
    for user_id, paid_until in subs:
        if not paid_until:
            continue
        try:
            dtp = datetime.datetime.fromisoformat(str(paid_until))
        except Exception:
            continue
        if dtp > now_utc:
            targets.append(user_id)
    cnt = len(targets)
    try:
        await update.message.reply_text("\u041f\u0440\u0435\u0434\u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440 \u0440\u0430\u0441\u0441\u044b\u043b\u043a\u0438:", parse_mode='HTML')
    except Exception:
        await update.message.reply_text("\u041f\u0440\u0435\u0434\u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440 \u0440\u0430\u0441\u0441\u044b\u043b\u043a\u0438:")
    try:
        await update.message.reply_text(context.user_data.get('broadcast_text',''), parse_mode='HTML', disable_web_page_preview=False)
    except Exception:
        await update.message.reply_text(context.user_data.get('broadcast_text',''))
    await update.message.reply_text(f"\u041e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c {cnt} \u043f\u043e\u0434\u043f\u0438\u0441\u0447\u0438\u043a\u0430\u043c \u0432 {s} (\u041c\u0421\u041a)?\\n\u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 '\u0434\u0430' \u0434\u043b\u044f \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f \u0438\u043b\u0438 '\u043d\u0435\u0442' \u0434\u043b\u044f \u043e\u0442\u043c\u0435\u043d\u044b.")
    
    
    return BROADCAST_SUBS_CONFIRM

async def broadcast_subscribers_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ans = (update.message.text or '').strip().lower()
    if ans not in ("да", "д", "yes", "y", "ок", "ok", "ага"):
        await update.message.reply_text("\u0420\u0430\u0441\u0441\u044b\u043b\u043a\u0430 \u043e\u0442\u043c\u0435\u043d\u0435\u043d\u0430.")
        return ConversationHandler.END
    text = context.user_data.get('broadcast_text') or ''
    if not text:
        await update.message.reply_text("\u0422\u0435\u043a\u0441\u0442 \u0440\u0430\u0441\u0441\u044b\u043b\u043a\u0438 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d. \u0417\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u0435 \u0437\u0430\u043d\u043e\u0432\u043e: /broadcast_subscribers")
        return ConversationHandler.END
    # РћРїСЂРµРґРµР»СЏРµРј, РєРѕРіРґР° РѕС‚РїСЂР°РІР»СЏС‚СЊ
    dt_utc_str = context.user_data.get('broadcast_dt_utc')
    dt_utc = None
    if dt_utc_str:
        try:
            dt_utc = datetime.datetime.fromisoformat(dt_utc_str)
        except Exception:
            dt_utc = None
    now = datetime.datetime.utcnow()
    delay = 0
    if dt_utc and dt_utc > now:
        delay = (dt_utc - now).total_seconds()
    # РџР»Р°РЅРёСЂСѓРµРј РѕС‚РїСЂР°РІРєСѓ С‡РµСЂРµР· JobQueue
    try:
        context.application.job_queue.run_once(
            broadcast_subscribers_job,
            when=max(0, int(delay)),
            data={'text': text}
        )
        when_desc = context.user_data.get('broadcast_dt_input') or '\u043a\u0430\u043a \u043c\u043e\u0436\u043d\u043e \u0441\u043a\u043e\u0440\u0435\u0435'
        await update.message.reply_text(f"\u0420\u0430\u0441\u0441\u044b\u043b\u043a\u0430 \u0437\u0430\u043f\u043b\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u043d\u0430 \u043d\u0430 {when_desc} (\u041c\u0421\u041a).")
    except Exception as e:
        await update.message.reply_text(f"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u043f\u043b\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0440\u0430\u0441\u0441\u044b\u043b\u043a\u0443: {e}")
    return ConversationHandler.END
async def broadcast_subscribers_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Р Р°СЃСЃС‹Р»РєР° РѕС‚РјРµРЅРµРЅР°.")
    return ConversationHandler.END

async def broadcast_subscribers_job(context: ContextTypes.DEFAULT_TYPE):
    """JobQueue callback: РѕС‚РїСЂР°РІР»СЏРµС‚ С‚РµРєСЃС‚ РІСЃРµРј Р°РєС‚РёРІРЅС‹Рј РїРѕРґРїРёСЃС‡РёРєР°Рј."""
    text = ''
    try:
        job = getattr(context, 'job', None)
        if job and job.data:
            text = job.data.get('text') or ''
    except Exception:
        text = ''
    now = datetime.datetime.utcnow()
    subs = db.get_all_subscriptions()
    users = []
    for user_id, paid_until in subs:
        if not paid_until:
            continue
        try:
            dt = datetime.datetime.fromisoformat(str(paid_until))
        except Exception:
            continue
        if dt > now:
            users.append((user_id,))
    if not users:
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text="\u0420\u0430\u0441\u0441\u044b\u043b\u043a\u0430: \u043d\u0435\u0442 \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0445 \u043f\u043e\u0434\u043f\u0438\u0441\u0447\u0438\u043a\u043e\u0432 \u043d\u0430 \u043c\u043e\u043c\u0435\u043d\u0442 \u043e\u0442\u043f\u0440\u0430\u0432\u043a\u0438.")
        except Exception:
            pass
        return
    try:
        # РћС‚РїСЂР°РІР»СЏРµРј РїРѕР»РЅС‹Р№ С‚РµРєСЃС‚; РІРєР»СЋС‡Р°РµРј РїСЂРµРґРїСЂРѕСЃРјРѕС‚СЂ СЃСЃС‹Р»РѕРє Рё РїРѕРґРґРµСЂР¶РёРІР°РµРј СЌРјРѕРґР·Рё
        success, failed = await send_message_to_users(
            context.bot,
            users,
            text=text,
            parse_mode='HTML',
            disable_web_page_preview=False,
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"\u0420\u0430\u0441\u0441\u044b\u043b\u043a\u0430 \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u0430. \u0423\u0441\u043f\u0435\u0448\u043d\u043e: {success}, \u043e\u0448\u0438\u0431\u043e\u043a: {failed}.")
        except Exception:
            pass
    except Exception as e:
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"РћС€РёР±РєР° РїСЂРё СЂР°СЃСЃС‹Р»РєРµ: {e}")
        except Exception:
            pass

# --- РђРєС‚РёРІР°С†РёСЏ С‚СѓСЂР° Р°РґРјРёРЅРѕРј ---
async def activate_tour(update, context):
    if not await admin_only(update, context):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ: /activate_tour <id>")
        return
    tour_id = int(context.args[0])
    tours = db.get_all_tours()
    found = False
    for t in tours:
        if t[0] == tour_id:
            db.update_tour_status(tour_id, "Р°РєС‚РёРІРµРЅ")
            found = True
        elif t[5] == "Р°РєС‚РёРІРµРЅ":
            db.update_tour_status(t[0], "СЃРѕР·РґР°РЅ")
    if found:
        await update.message.reply_text(f"РўСѓСЂ {tour_id} Р°РєС‚РёРІРёСЂРѕРІР°РЅ.")
    else:
        await update.message.reply_text(f"РўСѓСЂ СЃ id {tour_id} РЅРµ РЅР°Р№РґРµРЅ.")

# --- Utility: enhanced /addhc supporting @username or user_id ---
async def addhc2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_only(update, context):
        return
    # Expect two arguments: identifier (@username or user_id) and amount
    if len(context.args) != 2 or not context.args[1].isdigit():
        await update.message.reply_text('РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ: /addhc @username 100 РёР»Рё /addhc user_id 100')
        return
    identifier = (context.args[0] or '').strip()
    amount = int(context.args[1])

    # Resolve user either by @username or by numeric id
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
        await update.message.reply_text('РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ.')
        return

    db.update_hc_balance(user[0], amount)
    new_balance = db.get_user_by_id(user[0])[3]

    # Notify the user
    try:
        await context.bot.send_message(
            chat_id=user[0],
            text=f'Р’Р°Рј РЅР°С‡РёСЃР»РµРЅРѕ {amount} HC!\nРўРµРєСѓС‰РёР№ Р±Р°Р»Р°РЅСЃ: {new_balance} HC'
        )
    except Exception:
        pass

    # Reply to admin with more details
    target_label = f"@{resolved_username}" if resolved_username else f"id {user[0]}"
    await update.message.reply_text(f'РќР°С‡РёСЃР»РµРЅРѕ {target_label} {amount} HC.')


async def referral_limit_decision_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not await admin_only(update, context):
        return
    data = (query.data or '').split(':')
    if len(data) != 3:
        try:
            await query.edit_message_text('⚠️ Некорректные данные запроса.')
        except Exception:
            pass
        return
    _, referrer_id_str, decision = data
    try:
        referrer_id = int(referrer_id_str)
    except ValueError:
        try:
            await query.edit_message_text('⚠️ Некорректный идентификатор пользователя.')
        except Exception:
            pass
        return
    user_row = db.get_user_by_id(referrer_id)
    username = user_row[1] if user_row else ''
    name = user_row[2] if user_row else ''
    label = f"@{username}" if username else f"id {referrer_id}"
    if name:
        label = f"{label} ({name})"
    decision = decision.lower()
    if decision == 'yes':
        db.set_referral_disabled(referrer_id, True)
        db.set_referral_limit_state(referrer_id, 3)
        try:
            await context.bot.send_message(chat_id=referrer_id, text='⚠️ Ваша реферальная программа временно ограничена. Новые приглашения недоступны.')
        except Exception:
            pass
        response = f'Ограничение для {label} включено. Новые приглашения не принимаются.'
    elif decision == 'no':
        db.set_referral_limit_state(referrer_id, 2)
        response = f'Ограничение для {label} не устанавливается.'
    else:
        response = '⚠️ Неизвестное решение.'
    try:
        await query.edit_message_text(response)
    except Exception:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

