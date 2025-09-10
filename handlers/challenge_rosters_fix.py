import datetime
from telegram import Update
from telegram.ext import ContextTypes
import db


async def challenge_rosters_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ-команда: /challenge_rosters <challenge_id>
    Печатает заявки участников челленджа с выбранными игроками по позициям.
    """
    # Проверка прав администратора через уже имеющийся хелпер
    try:
        from handlers.admin_handlers import admin_only
    except Exception:
        async def admin_only(_u, _c):
            return True

    if not await admin_only(update, context):
        return

    # парсинг аргумента id
    challenge_id = None
    try:
        if context.args and len(context.args) >= 1:
            challenge_id = int(context.args[0])
    except Exception:
        challenge_id = None
    if not challenge_id:
        await update.message.reply_text("Использование: /challenge_rosters <challenge_id>")
        return

    # Получаем заявки по челленджу
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
        await update.message.reply_text(f"Ошибка запроса: {e}")
        return

    if not rows:
        await update.message.reply_text(f"По челленджу #{challenge_id} записей не найдено.")
        return

    def name_club(pid):
        if not pid:
            return "—"
        try:
            p = db.get_player_by_id(int(pid))
            if p:
                return f"{p[1]} ({p[3]})"
        except Exception:
            pass
        return str(pid)

    parts = []
    cur_lines = [f"Составы участников челленджа #{challenge_id}:", ""]
    for r in rows:
        uname = ("@" + (r["username"] or "").strip()) if r["username"] else "—"
        name = r["name"] or "—"
        status = (r["status"] or "").lower()
        stake = r["stake"] or 0
        fwd = name_club(r["forward_id"]) if r["forward_id"] else "—"
        dfd = name_club(r["defender_id"]) if r["defender_id"] else "—"
        gk = name_club(r["goalie_id"]) if r["goalie_id"] else "—"

        status_icon = {
            'in_progress': '⏳ в процессе',
            'completed': '✅ завершён',
            'canceled': '⚠ отменён',
            'refunded': '↩ возвращён',
        }.get(status, status or '—')

        cur_lines.append(f"• {uname} | {name} | {status_icon} | Ставка: {stake} HC")
        cur_lines.append(f"Нападающий: {fwd}")
        cur_lines.append(f"Защитник: {dfd}")
        cur_lines.append(f"Вратарь: {gk}")
        cur_lines.append("")

        joined = "\n".join(cur_lines)
        if len(joined) > 3500:
            parts.append(joined)
            cur_lines = []
    if cur_lines:
        parts.append("\n".join(cur_lines))

    for part in parts:
        try:
            await update.message.reply_text(part)
        except Exception:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=part)

