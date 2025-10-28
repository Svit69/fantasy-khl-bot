import datetime
from telegram import Update
from telegram.ext import ContextTypes
import db


def _iso_to_msk(dt_str: str) -> datetime.datetime | None:
    if not dt_str:
        return None
    try:
        dt = datetime.datetime.fromisoformat(str(dt_str))
    except Exception:
        return None
    # Assume UTC if naive
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    else:
        dt = dt.astimezone(datetime.timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo("Europe/Moscow"))
    except Exception:
        return dt.astimezone(datetime.timezone(datetime.timedelta(hours=3)))


def _fmt_date_msk(dt: datetime.datetime | None) -> str:
    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ]
    if not dt:
        return "—"
    return f"{dt.day} {months[dt.month - 1]} ({dt.strftime('%H:%M')} мск)"


async def challenge_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        cid = int(query.data.replace("challenge_info_", ""))
    except Exception:
        await query.edit_message_text("Не удалось разобрать идентификатор челленджа.")
        return

    ch = None
    try:
        ch = db.get_challenge_by_id(cid)
    except Exception:
        ch = None
    if not ch:
        await query.edit_message_text("Челлендж не найден.")
        return

    # ch: (id, start_date, deadline, end_date, image_filename, status, image_file_id, age_mode)
    start_dt = _iso_to_msk(ch[1])
    deadline_dt = _iso_to_msk(ch[2])
    end_dt = _iso_to_msk(ch[3])
    age_mode = (ch[7] if len(ch) > 7 else 'default') or 'default'
    mode_label = 'U23' if age_mode == 'under23' else 'regular'

    txt = (
        f"�������� №{ch[0]}\n"
        f"������: {ch[5]}\n\n"
        f"�����: {mode_label}\n"
        f"�����: {_fmt_date_msk(start_dt)}\n"
        f"�������: {_fmt_date_msk(deadline_dt)}\n"
        f"���������: {_fmt_date_msk(end_dt)}\n"
    )

    try:
        await query.edit_message_text(txt)
    except Exception:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=txt)

