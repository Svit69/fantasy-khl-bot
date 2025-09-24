from telegram import Update
from telegram.ext import ContextTypes

import db


def _format_player(pid):
    if not pid:
        return '—'
    try:
        player = db.get_player_by_id(int(pid))
        if player:
            return f"{player[1]} ({player[3]})"
    except Exception:
        pass
    return str(pid)


def _build_roster_message(challenge_id, rows):
    lines = [f'Составы участников челленджа #{challenge_id}:', '']
    status_map = {
        'in_progress': '⏳ в процессе',
        'completed': '✅ завершён',
        'canceled': '⚠ отменён',
        'refunded': '↩ возвращён',
    }
    messages = []
    for row in rows:
        username = ('@' + (row['username'] or '').strip()) if row['username'] else '—'
        name = row['name'] or '—'
        status = (row['status'] or '').lower()
        stake = row['stake'] or 0
        icon = status_map.get(status, status or '—')
        lines.append(f'• {username} | {name} | {icon} | Ставка: {stake} HC')
        lines.append(f'Нападающий: {_format_player(row["forward_id"])}')
        lines.append(f'Защитник: {_format_player(row["defender_id"])}')
        lines.append(f'Вратарь: {_format_player(row["goalie_id"])}')
        lines.append('')
        chunk = '\n'.join(lines)
        if len(chunk) > 3500:
            messages.append(chunk)
            lines = []
    if lines:
        messages.append('\n'.join(lines))
    return messages


async def challenge_rosters_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        from handlers.admin_handlers import admin_only
    except Exception:
        async def admin_only(_u, _c):
            return True

    if not await admin_only(update, context):
        return

    explicit_id = False
    challenge_ids = []
    if context.args and len(context.args) >= 1:
        try:
            challenge_id = int(context.args[0])
        except Exception:
            await update.message.reply_text('Использование: /challenge_rosters <challenge_id>')
            return
        challenge_ids = [challenge_id]
        explicit_id = True
    else:
        try:
            challenges = db.get_all_challenges() or []
        except Exception as exc:
            await update.message.reply_text(f'Не удалось получить список челленджей: {exc}')
            return
        active = [c for c in challenges if len(c) > 5 and (c[5] or '').lower() == 'активен']
        if not active:
            await update.message.reply_text('Нет активных челленджей.')
            return
        challenge_ids = [c[0] for c in active]

    for ch_id in challenge_ids:
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
                    ''',
                    (ch_id,),
                ).fetchall()
        except Exception as exc:
            await update.message.reply_text(f'Ошибка запроса по челленджу #{ch_id}: {exc}')
            continue

        if not rows:
            if explicit_id or len(challenge_ids) == 1:
                await update.message.reply_text(f'По челленджу #{ch_id} записей не найдено.')
            continue

        for message in _build_roster_message(ch_id, rows):
            try:
                await update.message.reply_text(message)
            except Exception:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
