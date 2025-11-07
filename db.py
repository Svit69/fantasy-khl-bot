import sqlite3
from contextlib import closing
import datetime
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


DB_NAME = 'fantasy_khl.db'

# Referral anti-abuse thresholds (configurable)
REFERRAL_LIMIT_24H = 5
REFERRAL_LIMIT_30D = 10
REFERRAL_LIMIT_TOTAL = 20
REFERRAL_ACCOUNT_LIMIT = 10


# --- Новая таблица для платежей ЮKassa ---
def init_payments_table():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS yookassa_payments (
                    payment_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    status TEXT,
                    created_at TEXT
                )
            ''')

def save_payment_id(user_id, payment_id, status='pending'):
    import datetime
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                'INSERT OR IGNORE INTO yookassa_payments (payment_id, user_id, status, created_at) VALUES (?, ?, ?, ?)',
                (payment_id, user_id, status, datetime.datetime.utcnow().isoformat())
            )

def update_payment_status(payment_id, status):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('UPDATE yookassa_payments SET status = ? WHERE payment_id = ?', (status, payment_id))

def get_pending_payments():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            return conn.execute('SELECT payment_id, user_id FROM yookassa_payments WHERE status = "pending"').fetchall()


DB_NAME = 'fantasy_khl.db'

def init_db():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    name TEXT,
                    hc_balance INTEGER DEFAULT 0,
                    is_blocked INTEGER DEFAULT 0,
                    blocked_at TEXT,
                    blocked_reason TEXT,
                    blocked_by INTEGER
                )
            ''')
            columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
            if 'is_blocked' not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0")
            if 'blocked_at' not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN blocked_at TEXT")
            if 'blocked_reason' not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN blocked_reason TEXT")
            if 'blocked_by' not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN blocked_by INTEGER")
            if 'referral_disabled' not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN referral_disabled INTEGER DEFAULT 0")
            if 'referral_limit_warning_sent' not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN referral_limit_warning_sent INTEGER DEFAULT 0")

            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_block_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    blocked_by INTEGER,
                    reason TEXT,
                    created_at TEXT
                )
            ''')

            # Таблица игроков
            conn.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    position TEXT NOT NULL,
                    club TEXT,
                    nation TEXT,
                    age INTEGER,
                    price INTEGER NOT NULL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS channel_bonus_requests (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    rewarded_at TEXT,
                    allowed_by INTEGER,
                    FOREIGN KEY(user_id) REFERENCES users(telegram_id)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS channel_bonus_rewards (
                    user_id INTEGER PRIMARY KEY,
                    rewarded_at TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    token TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(telegram_id)
                )
            ''')
            # Таблица состава на тур
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tour_roster (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tour_num INTEGER DEFAULT 1,
                    cost INTEGER NOT NULL,
                    player_id INTEGER NOT NULL,
                    FOREIGN KEY(player_id) REFERENCES players(id)
                )
            ''')
            # Таблица для хранения бюджета
            conn.execute('''
                CREATE TABLE IF NOT EXISTS budget (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    value INTEGER NOT NULL
                )
            ''')
            # Таблица туров
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tours (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    deadline TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'создан',
                    winners TEXT DEFAULT ''
                )
            ''')
            # Миграции для таблицы туров: добавить поля для изображения тура
            try:
                conn.execute('ALTER TABLE tours ADD COLUMN image_filename TEXT DEFAULT ""')
            except Exception:
                pass
            try:
                conn.execute('ALTER TABLE tours ADD COLUMN image_file_id TEXT DEFAULT ""')
            except Exception:
                pass
            # Таблица финальных составов пользователей на тур
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_tour_roster (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    tour_id INTEGER NOT NULL,
                    roster_json TEXT NOT NULL,
                    captain_id INTEGER,
                    spent INTEGER,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, tour_id)
                )
            ''')
            # Таблица подписок
            conn.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    user_id INTEGER PRIMARY KEY,
                    paid_until TEXT,
                    last_payment_id TEXT
                )
            ''')

            # Таблица рефералов: кто кого пригласил (один раз на пользователя)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    user_id INTEGER PRIMARY KEY,
                    referrer_id INTEGER
                )
            ''')

            # Таблица отправленных уведомлений по подписке (для дедупликации)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS subscription_notifications (
                    user_id INTEGER NOT NULL,
                    notify_date TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    UNIQUE(user_id, notify_date, kind)
                )
            ''')
            # Таблица состава игроков, привязанного к конкретному туру
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tour_players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tour_id INTEGER NOT NULL,
                    cost INTEGER NOT NULL,
                    player_id INTEGER NOT NULL,
                    FOREIGN KEY(player_id) REFERENCES players(id),
                    FOREIGN KEY(tour_id) REFERENCES tours(id)
                )
            ''')
            # Таблица челленджей
            conn.execute('''
                CREATE TABLE IF NOT EXISTS challenges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_date TEXT NOT NULL,
                    deadline TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    image_filename TEXT NOT NULL,
                    status TEXT NOT NULL,
                    image_file_id TEXT DEFAULT '',
                    age_mode TEXT NOT NULL DEFAULT 'default'
                )
            ''')
            # Миграция: добавить колонку image_file_id при отсутствии
            try:
                conn.execute('ALTER TABLE challenges ADD COLUMN image_file_id TEXT DEFAULT ""')
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE challenges ADD COLUMN age_mode TEXT NOT NULL DEFAULT 'default'")
            except Exception:
                pass
            # Таблица заявок пользователей на челлендж
            conn.execute('''
                CREATE TABLE IF NOT EXISTS challenge_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    challenge_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    stake INTEGER NOT NULL,
                    forward_id INTEGER,
                    defender_id INTEGER,
                    goalie_id INTEGER,
                    status TEXT NOT NULL DEFAULT 'in_progress',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(challenge_id, user_id),
                    FOREIGN KEY(challenge_id) REFERENCES challenges(id)
                )
            ''')
            # Таблица описания магазина (единственная запись id=1)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS shop_content (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    text TEXT DEFAULT '',
                    image_filename TEXT DEFAULT '',
                    image_file_id TEXT DEFAULT ''
                )
            ''')

def register_user(telegram_id, username, name):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()
            if not user:
                conn.execute(
                    'INSERT INTO users (telegram_id, username, name, hc_balance) VALUES (?, ?, ?, 0)',
                    (telegram_id, username, name)
                )
                return True
            return False

def get_user_by_username(username):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

def get_user_by_username_insensitive(username):
    if not username:
        return None
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return conn.execute('SELECT * FROM users WHERE LOWER(username) = LOWER(?)', (username,)).fetchone()

def get_user_by_id(telegram_id):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()

def get_subscription(user_id):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return conn.execute('SELECT * FROM subscriptions WHERE user_id = ?', (user_id,)).fetchone()

def add_or_update_subscription(user_id, paid_until, last_payment_id):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('''
                INSERT INTO subscriptions (user_id, paid_until, last_payment_id)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET paid_until=excluded.paid_until, last_payment_id=excluded.last_payment_id
            ''', (user_id, paid_until, last_payment_id))

def is_subscription_active(user_id: int) -> bool:
    """Возвращает True, если у пользователя есть подписка и paid_until > сейчас (UTC)."""
    try:
        row = get_subscription(user_id)
        if not row:
            return False
        # row: (user_id, paid_until, last_payment_id)
        paid_until = row[1]
        if not paid_until:
            return False
        import datetime
        try:
            dt = datetime.datetime.fromisoformat(paid_until)
        except Exception:
            return False
        return dt > datetime.datetime.utcnow()
    except Exception:
        return False

def update_hc_balance(telegram_id, amount):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('UPDATE users SET hc_balance = hc_balance + ? WHERE telegram_id = ?', (amount, telegram_id))

def has_channel_bonus_reward(user_id: int) -> bool:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        row = conn.execute('SELECT 1 FROM channel_bonus_rewards WHERE user_id = ?', (user_id,)).fetchone()
        return bool(row)


def clear_channel_bonus_requests(user_id: int) -> None:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('DELETE FROM channel_bonus_requests WHERE user_id = ? AND status = ?', (user_id, 'pending'))


def create_channel_bonus_request(token: str, user_id: int, amount: int, allowed_by: int | None) -> None:
    now = datetime.datetime.utcnow().isoformat()
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO channel_bonus_requests (token, user_id, amount, status, created_at, allowed_by)
                VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (token, user_id, amount, now, allowed_by)
            )


def get_channel_bonus_request(token: str):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT token, user_id, amount, status, created_at, rewarded_at, allowed_by
            FROM channel_bonus_requests
            WHERE token = ?
            """,
            (token,)
        ).fetchone()
        return dict(row) if row else None


def mark_channel_bonus_rewarded(token: str):
    now = datetime.datetime.utcnow().isoformat()
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        with conn:
            row = conn.execute(
                'SELECT user_id, amount, status FROM channel_bonus_requests WHERE token = ?',
                (token,)
            ).fetchone()
            if not row:
                return None
            user_id = row['user_id']
            amount = row['amount']
            status = row['status']
            if status != 'pending':
                return {'user_id': user_id, 'amount': amount, 'status': status}
            already_rewarded = conn.execute(
                'SELECT 1 FROM channel_bonus_rewards WHERE user_id = ?',
                (user_id,)
            ).fetchone()
            if already_rewarded:
                conn.execute(
                    'UPDATE channel_bonus_requests SET status = ?, rewarded_at = ? WHERE token = ?',
                    ('duplicate', now, token)
                )
                return {'user_id': user_id, 'amount': amount, 'status': 'duplicate'}
            conn.execute(
                'UPDATE channel_bonus_requests SET status = ?, rewarded_at = ? WHERE token = ?',
                ('rewarded', now, token)
            )
            conn.execute(
                """
                INSERT INTO channel_bonus_rewards (user_id, rewarded_at, amount, token)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO NOTHING
                """,
                (user_id, now, amount, token)
            )
            return {'user_id': user_id, 'amount': amount, 'status': 'rewarded'}

def block_user(telegram_id: int, blocked_by: int = None, reason: str = None) -> None:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                'UPDATE users SET is_blocked = 1, blocked_at = ?, blocked_reason = ?, blocked_by = ? WHERE telegram_id = ?',
                (now, reason or '', blocked_by, telegram_id)
            )
            conn.execute(
                'INSERT INTO user_block_log (user_id, blocked_by, reason, created_at) VALUES (?, ?, ?, ?)',
                (telegram_id, blocked_by, reason or '', now)
            )


def unblock_user(telegram_id: int) -> None:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                'UPDATE users SET is_blocked = 0, blocked_at = NULL, blocked_reason = NULL, blocked_by = NULL WHERE telegram_id = ?',
                (telegram_id,)
            )


def is_user_blocked(telegram_id: int) -> bool:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        row = conn.execute(
            'SELECT is_blocked FROM users WHERE telegram_id = ?',
            (telegram_id,)
        ).fetchone()
    if not row:
        return False
    return bool(row[0])


def get_all_users():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return conn.execute('SELECT telegram_id FROM users').fetchall()

def get_all_subscriptions():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return conn.execute('SELECT user_id, paid_until FROM subscriptions').fetchall()

def has_subscription_notification(user_id: int, notify_date: str, kind: str) -> bool:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        row = conn.execute(
            'SELECT 1 FROM subscription_notifications WHERE user_id=? AND notify_date=? AND kind=?',
            (user_id, notify_date, kind)
        ).fetchone()
        return bool(row)

# --- Удаление подписок ---
def delete_subscription_by_user_id(user_id: int) -> int:
    """Удаляет подписку конкретного пользователя. Возвращает число удалённых строк (0 или 1)."""
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            cur = conn.execute('DELETE FROM subscriptions WHERE user_id = ?', (user_id,))
            return cur.rowcount or 0

def purge_all_subscriptions() -> int:
    """Удаляет все подписки. Возвращает число удалённых строк."""
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            cur = conn.execute('DELETE FROM subscriptions')
            return cur.rowcount or 0

def record_subscription_notification(user_id: int, notify_date: str, kind: str) -> None:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                'INSERT OR IGNORE INTO subscription_notifications (user_id, notify_date, kind) VALUES (?, ?, ?)',
                (user_id, notify_date, kind)
            )

# --- Челленджи ---

def _get_moscow_timezone():
    import datetime, os
    override = os.getenv('BOT_TZ_OFFSET')
    if override is not None:
        try:
            offset_hours = int(override)
            return datetime.timezone(datetime.timedelta(hours=offset_hours))
        except Exception:
            pass
    if ZoneInfo is not None:
        try:
            return ZoneInfo('Europe/Moscow')
        except Exception:
            pass
    return datetime.timezone(datetime.timedelta(hours=3))


def _ensure_moscow_datetime(value):
    if value is None:
        return None
    tz = _get_moscow_timezone()
    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)


def _parse_challenge_datetime(raw: str):
    import datetime as _dt
    if not raw:
        return None
    try:
        dt = _dt.datetime.fromisoformat(str(raw))
    except Exception:
        return None
    return _ensure_moscow_datetime(dt)


def _parse_tour_datetime(raw: str, include_time: bool):
    import datetime as _dt
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    dt = None
    try:
        dt = _dt.datetime.fromisoformat(text)
    except Exception:
        dt = None
    if dt is None:
        formats = ['%d.%m.%Y %H:%M', '%d.%m.%y %H:%M'] if include_time else ['%d.%m.%Y', '%d.%m.%y']
        for fmt in formats:
            try:
                dt = _dt.datetime.strptime(text, fmt)
                break
            except Exception:
                continue
    if dt is None:
        return None
    if not include_time:
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return _ensure_moscow_datetime(dt)


def parse_tour_start_datetime(raw: str):
    return _parse_tour_datetime(raw, include_time=False)


def parse_tour_deadline_datetime(raw: str):
    return _parse_tour_datetime(raw, include_time=True)


def _now_moscow():
    import datetime
    return datetime.datetime.now(_get_moscow_timezone())

def get_moscow_now():
    return _now_moscow()

def create_challenge(start_date: str, deadline: str, end_date: str, image_filename: str, image_file_id: str = '', age_mode: str = 'default') -> int:
    """Создаёт запись челленджа и возвращает его id. Статус вычисляется относительно текущего времени."""
    now = _now_moscow()
    sd = _parse_challenge_datetime(start_date)
    dl = _parse_challenge_datetime(deadline)
    ed = _parse_challenge_datetime(end_date)
    status = 'в ожидании'
    if sd and dl and ed:
        if sd <= now < dl:
            status = 'активен'
        elif dl <= now < ed:
            status = 'в игре'
        elif now >= ed:
            status = 'завершен'
    start_value = sd.isoformat() if sd else (start_date or '')
    deadline_value = dl.isoformat() if dl else (deadline or '')
    end_value = ed.isoformat() if ed else (end_date or '')
    normalized_mode = (age_mode or 'default').strip().lower()
    if normalized_mode not in ('default', 'under23'):
        normalized_mode = 'default'
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            cur = conn.execute(
                'INSERT INTO challenges (start_date, deadline, end_date, image_filename, status, image_file_id, age_mode) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (start_value, deadline_value, end_value, image_filename, status, image_file_id or '', normalized_mode)
            )
            return cur.lastrowid

# --- Менеджеры, зарегистрировавшие состав на тур ---
def get_tour_managers(tour_id: int):
    """Возвращает список менеджеров, у которых сохранён финальный состав на указанный тур.
    Элементы списка — словари: { user_id, username, name, spent, timestamp }.
    """
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            '''
            SELECT utr.user_id AS user_id,
                   u.username AS username,
                   u.name     AS name,
                   utr.spent  AS spent,
                   utr.timestamp AS timestamp
            FROM user_tour_roster AS utr
            LEFT JOIN users AS u ON u.telegram_id = utr.user_id
            WHERE utr.tour_id = ?
            ORDER BY utr.timestamp DESC
            ''', (tour_id,)
        ).fetchall()
        return [dict(r) for r in rows]

def _compute_challenge_status(start_date: str, deadline: str, end_date: str) -> str:
    """Вычисляет статус челленджа на текущий момент по МСК.

    Возвращает: 'в ожидании' | 'активен' | 'в игре' | 'завершен'.
    При ошибках парсинга дат — 'в ожидании'.
    """
    now = _now_moscow()
    sd = _parse_challenge_datetime(start_date)
    dl = _parse_challenge_datetime(deadline)
    ed = _parse_challenge_datetime(end_date)
    status = 'в ожидании'
    if sd and dl and ed:
        if sd <= now < dl:
            status = 'активен'
        elif dl <= now < ed:
            status = 'в игре'
        elif now >= ed:
            status = 'завершен'
    return status


def get_latest_challenge():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        row = conn.execute('SELECT id, start_date, deadline, end_date, image_filename, status, image_file_id, age_mode FROM challenges ORDER BY id DESC LIMIT 1').fetchone()
        if not row:
            return row
        ch_id, start_date, deadline, end_date, image_filename, status, image_file_id, age_mode = row
        cur_status = _compute_challenge_status(start_date, deadline, end_date)
        try:
            if cur_status != status:
                with conn:
                    conn.execute('UPDATE challenges SET status = ? WHERE id = ?', (cur_status, ch_id))
                status = cur_status
        except Exception:
            pass
        return (ch_id, start_date, deadline, end_date, image_filename, status, image_file_id, age_mode)

def get_all_challenges():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        rows = conn.execute('SELECT id, start_date, deadline, end_date, image_filename, status, image_file_id, age_mode FROM challenges ORDER BY id DESC').fetchall()
        updated = []
        for r in rows:
            ch_id, start_date, deadline, end_date, image_filename, status, image_file_id, age_mode = r
            cur_status = _compute_challenge_status(start_date, deadline, end_date)
            if cur_status != status:
                try:
                    with conn:
                        conn.execute('UPDATE challenges SET status = ? WHERE id = ?', (cur_status, ch_id))
                    status = cur_status
                except Exception:
                    status = cur_status
            updated.append((ch_id, start_date, deadline, end_date, image_filename, status, image_file_id, age_mode))
        return updated

def delete_challenge(ch_id: int) -> int:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            cur = conn.execute('DELETE FROM challenges WHERE id = ?', (ch_id,))
            return cur.rowcount

# --- Игроки ---
def add_player(name, position, club, nation, age, price):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                'INSERT INTO players (name, position, club, nation, age, price) VALUES (?, ?, ?, ?, ?, ?)',
                (name, position, club, nation, age, price)
            )

def get_all_players():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return conn.execute('SELECT id, name, position, club, nation, age, price FROM players').fetchall()

def get_player_by_id(player_id):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return conn.execute('SELECT id, name, position, club, nation, age, price FROM players WHERE id = ?', (player_id,)).fetchone()

def clear_tour_roster(tour_num=1):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('DELETE FROM tour_roster WHERE tour_num = ?', (tour_num,))

def add_tour_roster_entry(player_id, cost, tour_num=1):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('INSERT INTO tour_roster (tour_num, cost, player_id) VALUES (?, ?, ?)', (tour_num, cost, player_id))

def get_tour_roster(tour_num=1):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return conn.execute('SELECT cost, player_id FROM tour_roster WHERE tour_num = ? ORDER BY cost DESC, id ASC', (tour_num,)).fetchall()

def set_budget(value):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('INSERT OR REPLACE INTO budget (id, value) VALUES (1, ?)', (value,))

def get_budget():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        row = conn.execute('SELECT value FROM budget WHERE id = 1').fetchone()
        return row[0] if row else None

def get_tour_roster_with_player_info(tour_num=1):
    """Return roster (cost + player info) for the given tour.

    Uses the modern tour_players table first, but falls back to the legacy
    tour_roster table to remain backward compatible with older data.
    """
    if tour_num is None:
        tour_num = 1
    with closing(sqlite3.connect(DB_NAME)) as conn:
        rows = conn.execute(
            '''
            SELECT tp.cost, p.id, p.name, p.position, p.club, p.nation, p.age, p.price
            FROM tour_players tp
            JOIN players p ON tp.player_id = p.id
            WHERE tp.tour_id = ?
            ORDER BY tp.cost DESC, tp.id ASC
            ''',
            (tour_num,)
        ).fetchall()
        if rows:
            return rows
        return conn.execute(
            '''
            SELECT tr.cost, p.id, p.name, p.position, p.club, p.nation, p.age, p.price
            FROM tour_roster tr
            JOIN players p ON tr.player_id = p.id
            WHERE tr.tour_num = ?
            ORDER BY tr.cost DESC, tr.id ASC
            ''',
            (tour_num,)
        ).fetchall()

def remove_player(player_id):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            cursor = conn.execute('DELETE FROM players WHERE id = ?', (player_id,))
            return cursor.rowcount > 0

# --- Challenge entries helpers ---
def get_challenge_by_id(ch_id: int):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        row = conn.execute('SELECT id, start_date, deadline, end_date, image_filename, status, image_file_id, age_mode FROM challenges WHERE id = ?', (ch_id,)).fetchone()
        if not row:
            return row
        cid, start_date, deadline, end_date, image_filename, status, image_file_id, age_mode = row
        cur_status = _compute_challenge_status(start_date, deadline, end_date)
        try:
            if cur_status != status:
                with conn:
                    conn.execute('UPDATE challenges SET status = ? WHERE id = ?', (cur_status, cid))
                status = cur_status
        except Exception:
            pass
        return (cid, start_date, deadline, end_date, image_filename, status, image_file_id, age_mode)

def challenge_get_entry(challenge_id: int, user_id: int):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return conn.execute('SELECT id, stake, forward_id, defender_id, goalie_id, status FROM challenge_entries WHERE challenge_id = ? AND user_id = ?', (challenge_id, user_id)).fetchone()

def create_challenge_entry_and_charge(challenge_id: int, user_id: int, stake: int) -> bool:
    """Создаёт запись участия в челлендже и списывает HC. Возвращает True при успехе.
    Если запись уже есть и статус in_progress/completed — возвращает False (не дублируем).
    """
    if stake <= 0:
        return False
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            # Проверим существование
            row = conn.execute('SELECT id, status FROM challenge_entries WHERE challenge_id = ? AND user_id = ?', (challenge_id, user_id)).fetchone()
            if row:
                cur_status = (row[1] or '').lower()
                # Разрешаем повторный вход, если запись была отменена или возвращена
                if cur_status in ('canceled', 'refunded'):
                    u = conn.execute('SELECT hc_balance FROM users WHERE telegram_id = ?', (user_id,)).fetchone()
                    bal = (u[0] if u else 0)
                    if bal < stake:
                        return False
                    # Списываем и переоткрываем запись: обновляем ставку, очищаем пики и ставим статус in_progress
                    conn.execute('UPDATE users SET hc_balance = hc_balance - ? WHERE telegram_id = ?', (stake, user_id))
                    conn.execute('''
                        UPDATE challenge_entries
                        SET stake = ?, status = 'in_progress', forward_id = NULL, defender_id = NULL, goalie_id = NULL, created_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (stake, row[0]))
                    return True
                # Иначе (in_progress/completed) — не создаём дубликат
                return False
            # Проверим баланс
            u = conn.execute('SELECT hc_balance FROM users WHERE telegram_id = ?', (user_id,)).fetchone()
            bal = (u[0] if u else 0)
            if bal < stake:
                return False
            # Списываем и создаём запись
            conn.execute('UPDATE users SET hc_balance = hc_balance - ? WHERE telegram_id = ?', (stake, user_id))
            conn.execute('INSERT INTO challenge_entries (challenge_id, user_id, stake, status) VALUES (?, ?, ?, ?)', (challenge_id, user_id, stake, 'in_progress'))
            return True

def challenge_set_pick(challenge_id: int, user_id: int, position: str, player_id: int) -> None:
    col = None
    pos = (position or '').lower()
    if pos == 'нападающий':
        col = 'forward_id'
    elif pos == 'защитник':
        col = 'defender_id'
    elif pos == 'вратарь':
        col = 'goalie_id'
    if not col:
        return
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(f'UPDATE challenge_entries SET {col} = ? WHERE challenge_id = ? AND user_id = ?', (player_id, challenge_id, user_id))

def challenge_reset_picks(challenge_id: int, user_id: int) -> None:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('UPDATE challenge_entries SET forward_id = NULL, defender_id = NULL, goalie_id = NULL WHERE challenge_id = ? AND user_id = ?', (challenge_id, user_id))

def challenge_finalize(challenge_id: int, user_id: int) -> None:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('UPDATE challenge_entries SET status = ? WHERE challenge_id = ? AND user_id = ?', ('completed', challenge_id, user_id))

def challenge_cancel_and_refund(challenge_id: int, user_id: int) -> bool:
    """Если запись в статусе in_progress, возвращаем stake пользователю и помечаем как canceled, либо удаляем.
    Возвращает True, если возврат произведён.
    """
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            row = conn.execute('SELECT id, stake, status FROM challenge_entries WHERE challenge_id = ? AND user_id = ?', (challenge_id, user_id)).fetchone()
            if not row:
                return False

            deadline_row = conn.execute('SELECT deadline FROM challenges WHERE id = ?', (challenge_id,)).fetchone()
            deadline_dt = _parse_challenge_datetime(deadline_row[0]) if deadline_row else None
            now_dt = _now_moscow()

            stake = row[1] or 0
            status = (row[2] or 'in_progress').lower()

            if status in ('canceled', 'refunded'):
                return False

            if deadline_dt and now_dt < deadline_dt:
                conn.execute('UPDATE users SET hc_balance = hc_balance + ? WHERE telegram_id = ?', (stake, user_id))
                conn.execute('UPDATE challenge_entries SET status = ? WHERE id = ?', ('canceled', row[0]))
                return True

            return False


def refund_unfinished_after_deadline() -> int:
    """Возвращает HC по незавершённым заявкам после дедлайна. Возвращает число обработанных записей."""
    now = _now_moscow()
    processed = 0
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            rows = conn.execute('SELECT id, deadline FROM challenges').fetchall()
            for ch in rows:
                ch_id, deadline_raw = ch[0], ch[1]
                try:
                    deadline_dt = _parse_challenge_datetime(deadline_raw)
                    if deadline_dt and now >= deadline_dt:
                        entries = conn.execute('SELECT id, user_id, stake FROM challenge_entries WHERE challenge_id = ? AND status = ?', (ch_id, 'in_progress')).fetchall()
                        for entry in entries:
                            conn.execute('UPDATE users SET hc_balance = hc_balance + ? WHERE telegram_id = ?', (entry[2] or 0, entry[1]))
                            conn.execute('UPDATE challenge_entries SET status = ? WHERE id = ?', ('refunded', entry[0]))
                            processed += 1
                except Exception:
                    continue
    return processed


# --- Магазин ---
def set_shop_content(text: str, image_filename: str = '', image_file_id: str = '') -> None:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                'INSERT INTO shop_content (id, text, image_filename, image_file_id) VALUES (1, ?, ?, ?)\n'
                'ON CONFLICT(id) DO UPDATE SET text=excluded.text, image_filename=excluded.image_filename, image_file_id=excluded.image_file_id',
                (text or '', image_filename or '', image_file_id or '')
            )

def update_shop_text(text: str) -> None:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('INSERT INTO shop_content (id, text) VALUES (1, ?)\nON CONFLICT(id) DO UPDATE SET text=excluded.text', (text or '',))

def update_shop_image(image_filename: str, image_file_id: str = '') -> None:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                'INSERT INTO shop_content (id, image_filename, image_file_id) VALUES (1, ?, ?)\n'
                'ON CONFLICT(id) DO UPDATE SET image_filename=excluded.image_filename, image_file_id=excluded.image_file_id',
                (image_filename or '', image_file_id or '')
            )

def get_shop_content():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        row = conn.execute('SELECT text, image_filename, image_file_id FROM shop_content WHERE id = 1').fetchone()
        if not row:
            return ('', '', '')
        return row

def update_player(player_id, name, position, club, nation, age, price):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            cursor = conn.execute(
                'UPDATE players SET name = ?, position = ?, club = ?, nation = ?, age = ?, price = ? WHERE id = ?',
                (name, position, club, nation, age, price, player_id)
            )
            return cursor.rowcount > 0

def update_player_price(player_id: int, price: int) -> bool:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            cursor = conn.execute(
                'UPDATE players SET price = ? WHERE id = ?',
                (price, player_id)
            )
            return cursor.rowcount > 0

def update_player_age(player_id: int, age: int) -> bool:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            cursor = conn.execute(
                'UPDATE players SET age = ? WHERE id = ?',
                (age, player_id)
            )
            return cursor.rowcount > 0

# --- Турнирные туры ---
def create_tour(name, start_date, deadline, end_date, status="создан"):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            cur = conn.execute(
                'INSERT INTO tours (name, start_date, deadline, end_date, status) VALUES (?, ?, ?, ?, ?)',
                (name, start_date, deadline, end_date, status)
            )
            return cur.lastrowid

def get_all_tours():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return conn.execute('SELECT id, name, start_date, deadline, end_date, status, winners FROM tours ORDER BY id').fetchall()

def update_tour_status(tour_id, status):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('UPDATE tours SET status = ? WHERE id = ?', (status, tour_id))

def update_tour_image(tour_id: int, image_filename: str, image_file_id: str = "") -> None:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                'UPDATE tours SET image_filename = ?, image_file_id = ? WHERE id = ?',
                (image_filename or '', image_file_id or '', tour_id)
            )

def get_tour_by_id(tour_id: int):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return conn.execute(
            'SELECT id, name, start_date, deadline, end_date, status, winners, image_filename, image_file_id FROM tours WHERE id = ?',
            (tour_id,)
        ).fetchone()

def clear_tour_players(tour_id: int) -> None:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('DELETE FROM tour_players WHERE tour_id = ?', (tour_id,))

def add_tour_player(tour_id: int, player_id: int, cost: int) -> None:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                'INSERT INTO tour_players (tour_id, cost, player_id) VALUES (?, ?, ?)',
                (tour_id, cost, player_id)
            )

def get_tour_players_with_info(tour_id: int):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return conn.execute('''
            SELECT tp.cost, p.id, p.name, p.position, p.club, p.nation, p.age, p.price
            FROM tour_players tp
            JOIN players p ON tp.player_id = p.id
            WHERE tp.tour_id = ?
            ORDER BY tp.cost DESC, tp.id ASC
        ''', (tour_id,)).fetchall()

def purge_all_tours() -> int:
    """Удаляет все туры и связанные с ними данные. Возвращает количество удалённых туров."""
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            cur = conn.execute('SELECT COUNT(*) FROM tours')
            count = cur.fetchone()[0] or 0
            # Удаляем зависимые данные
            conn.execute('DELETE FROM tour_players')
            conn.execute('DELETE FROM tour_roster')
            conn.execute('DELETE FROM user_tour_roster')
            # Удаляем туры
            conn.execute('DELETE FROM tours')
            return count

# --- Удаление одного тура по id ---
def delete_tour_by_id(tour_id: int) -> int:
    """Удаляет конкретный тур и связанные данные. Возвращает 1 если тур удалён, иначе 0."""
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            # Удаляем зависимые данные
            conn.execute('DELETE FROM tour_players WHERE tour_id = ?', (tour_id,))
            conn.execute('DELETE FROM user_tour_roster WHERE tour_id = ?', (tour_id,))
            # Возможная старая таблица по номеру тура
            try:
                conn.execute('DELETE FROM tour_roster WHERE tour_num = ?', (tour_id,))
            except Exception:
                pass
            cur = conn.execute('DELETE FROM tours WHERE id = ?', (tour_id,))
            return cur.rowcount or 0

# --- Реферальная система ---

def init_referrals_table():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    user_id INTEGER PRIMARY KEY,
                    referrer_id INTEGER,
                    created_at TEXT,
                    status TEXT,
                    reward_amount INTEGER DEFAULT 0,
                    rewarded_at TEXT,
                    note TEXT
                )
            ''')
            columns = {row[1] for row in conn.execute("PRAGMA table_info(referrals)")}
            if 'created_at' not in columns:
                conn.execute("ALTER TABLE referrals ADD COLUMN created_at TEXT")
            if 'status' not in columns:
                conn.execute("ALTER TABLE referrals ADD COLUMN status TEXT")
            if 'reward_amount' not in columns:
                conn.execute("ALTER TABLE referrals ADD COLUMN reward_amount INTEGER DEFAULT 0")
            if 'rewarded_at' not in columns:
                conn.execute("ALTER TABLE referrals ADD COLUMN rewarded_at TEXT")
            if 'note' not in columns:
                conn.execute("ALTER TABLE referrals ADD COLUMN note TEXT")
            if 'reviewed_at' not in columns:
                conn.execute("ALTER TABLE referrals ADD COLUMN reviewed_at TEXT")
            if 'reviewed_by' not in columns:
                conn.execute("ALTER TABLE referrals ADD COLUMN reviewed_by INTEGER")
            conn.execute("UPDATE referrals SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)")
            conn.execute("UPDATE referrals SET status = COALESCE(status, 'legacy')")
            conn.execute("UPDATE referrals SET reward_amount = COALESCE(reward_amount, 0)")



def add_referral_if_new(user_id: int, referrer_id: int) -> bool:
    """Сохраняет пару (user_id -> referrer_id), если для user_id ещё не было записи.
    Возвращает True, если запись была добавлена (т.е. referral новый), иначе False.
    """
    if user_id == referrer_id:
        return False
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            user_row = conn.execute('SELECT referral_disabled, referral_limit_warning_sent FROM users WHERE telegram_id = ?', (referrer_id,)).fetchone()
            disabled = False
            warning_state = 0
            if user_row:
                disabled = bool(user_row[0])
                warning_state = user_row[1] or 0
            if disabled:
                return False
            total_row = conn.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (referrer_id,)).fetchone()
            total_referrals = int(total_row[0]) if total_row and total_row[0] is not None else 0
            if warning_state != 2 and total_referrals >= REFERRAL_ACCOUNT_LIMIT:
                return False
            exists = conn.execute('SELECT 1 FROM referrals WHERE user_id = ?', (user_id,)).fetchone()
            if exists:
                return False
            conn.execute(
                'INSERT INTO referrals (user_id, referrer_id, created_at, status, reward_amount, rewarded_at, note) VALUES (?, ?, ?, ?, 0, NULL, NULL)',
                (user_id, referrer_id, now_iso, 'pending')
            )
            return True





# --- Referral limit helpers ---
def get_referrals_for_referrer(referrer_id: int):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            '''
            SELECT r.user_id, r.status, r.created_at, r.rewarded_at, r.reward_amount,
                   u.username, u.name
            FROM referrals AS r
            LEFT JOIN users AS u ON u.telegram_id = r.user_id
            WHERE r.referrer_id = ?
            ORDER BY r.created_at ASC
            ''',
            (referrer_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def set_referral_limit_state(referrer_id: int, state: int) -> None:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('UPDATE users SET referral_limit_warning_sent = ? WHERE telegram_id = ?', (int(state), referrer_id))


def set_referral_disabled(referrer_id: int, disabled: bool = True) -> None:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('UPDATE users SET referral_disabled = ? WHERE telegram_id = ?', (1 if disabled else 0, referrer_id))


def check_referral_limit_state(referrer_id: int, limit: int = REFERRAL_ACCOUNT_LIMIT) -> dict:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        user_row = conn.execute('SELECT referral_disabled, referral_limit_warning_sent FROM users WHERE telegram_id = ?', (referrer_id,)).fetchone()
        if not user_row:
            return {'total': 0, 'state': 0, 'disabled': False, 'notify': False, 'referrals': []}
        disabled = bool(user_row['referral_disabled'])
        state = user_row['referral_limit_warning_sent'] or 0
        total_row = conn.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (referrer_id,)).fetchone()
        total = int(total_row[0]) if total_row and total_row[0] is not None else 0
        notify = False
        referrals = []
        if total >= limit and not disabled and state == 0:
            referrals = get_referrals_for_referrer(referrer_id)
            with conn:
                conn.execute('UPDATE users SET referral_limit_warning_sent = 1 WHERE telegram_id = ?', (referrer_id,))
            state = 1
            notify = True
        return {'total': total, 'state': state, 'disabled': disabled, 'notify': notify, 'referrals': referrals}
def _count_referrals(conn, referrer_id: int, *, statuses=None, since_hours=None, use_rewarded_timestamp=False, now=None):
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    query = 'SELECT COUNT(*) FROM referrals WHERE referrer_id = ?'
    params = [referrer_id]
    if statuses:
        placeholders = ','.join('?' for _ in statuses)
        query += f" AND status IN ({placeholders})"
        params.extend(statuses)
    if since_hours is not None:
        since = now - datetime.timedelta(hours=since_hours)
        column = 'rewarded_at' if use_rewarded_timestamp else 'created_at'
        query += f" AND {column} >= ?"
        params.append(since.isoformat())
    cur = conn.execute(query, params)
    row = cur.fetchone()
    return int(row[0]) if row and row[0] is not None else 0





def try_reward_referral(user_id: int, referrer_id: int, amount: int) -> dict:
    """Пытается начислить бонус рефереру с учётом ограничений и антинакрутки."""
    now = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now.isoformat()
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        with conn:
            row = conn.execute('SELECT status, reward_amount FROM referrals WHERE user_id = ?', (user_id,)).fetchone()
            if not row:
                return {'status': 'missing'}
            current_status = (row['status'] or '').lower() if row['status'] is not None else 'pending'
            stored_amount = row['reward_amount'] if 'reward_amount' in row.keys() else None
            if current_status not in ('pending', 'pending_admin'):
                return {'status': current_status}

            disabled_row = conn.execute('SELECT referral_disabled FROM users WHERE telegram_id = ?', (referrer_id,)).fetchone()
            if disabled_row and disabled_row[0]:
                conn.execute('UPDATE referrals SET status = ?, note = ? WHERE user_id = ?', ('disabled', 'referrer_disabled', user_id))
                return {'status': 'disabled'}

            counts = {
                'rewarded_24h': _count_referrals(conn, referrer_id, statuses=('rewarded',), since_hours=24, use_rewarded_timestamp=True, now=now),
                'rewarded_30d': _count_referrals(conn, referrer_id, statuses=('rewarded',), since_hours=24 * 30, use_rewarded_timestamp=True, now=now),
                'rewarded_total': _count_referrals(conn, referrer_id, statuses=('rewarded',), use_rewarded_timestamp=True, now=now),
            }

            if current_status == 'pending_admin':
                pending_amount = stored_amount if stored_amount is not None else amount
                return {'status': 'pending_admin', 'amount': pending_amount, 'counts': counts}

            if counts['rewarded_total'] >= REFERRAL_LIMIT_TOTAL:
                conn.execute('UPDATE referrals SET status = ?, note = ? WHERE user_id = ?', ('limit_total', 'total_limit', user_id))
                return {'status': 'limit_total', 'counts': counts}

            if counts['rewarded_30d'] >= REFERRAL_LIMIT_30D:
                conn.execute('UPDATE referrals SET status = ?, note = ? WHERE user_id = ?', ('limit_month', 'monthly_limit', user_id))
                return {'status': 'limit_month', 'counts': counts}

            if counts['rewarded_24h'] >= REFERRAL_LIMIT_24H:
                conn.execute(
                    'UPDATE referrals SET status = ?, reward_amount = ?, note = ? WHERE user_id = ?',
                    ('pending_admin', amount, 'daily_limit', user_id)
                )
                return {'status': 'pending_admin', 'amount': amount, 'counts': counts}

            conn.execute('UPDATE users SET hc_balance = hc_balance + ? WHERE telegram_id = ?', (amount, referrer_id))
            conn.execute(
                'UPDATE referrals SET status = ?, reward_amount = ?, rewarded_at = ?, note = NULL, reviewed_at = ?, reviewed_by = NULL WHERE user_id = ?',
                ('rewarded', amount, now_iso, now_iso, user_id)
            )
            balance_row = conn.execute('SELECT hc_balance FROM users WHERE telegram_id = ?', (referrer_id,)).fetchone()
            balance = balance_row[0] if balance_row else None
            return {'status': 'rewarded', 'amount': amount, 'balance': balance, 'counts': counts}


def get_active_tour():
    import datetime
    now = _now_moscow()
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM tours WHERE status = ? ORDER BY start_date ASC LIMIT 1', ("активен",)).fetchone()
        if row:
            return dict(row)
        rows = conn.execute('SELECT * FROM tours').fetchall()
        for r in rows:
            start_dt = parse_tour_start_datetime(r['start_date'])
            deadline_dt = parse_tour_deadline_datetime(r['deadline'])
            if start_dt and deadline_dt and start_dt <= now < deadline_dt:
                return dict(r)
        return None




def approve_referral(user_id: int, admin_id: int) -> dict:
    """Одобряет отложенный реферал и начисляет бонус."""
    now = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now.isoformat()
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        with conn:
            row = conn.execute('SELECT referrer_id, reward_amount, status FROM referrals WHERE user_id = ?', (user_id,)).fetchone()
            if not row:
                return {'status': 'missing'}
            status = (row['status'] or '').lower() if row['status'] is not None else 'pending'
            if status != 'pending_admin':
                return {'status': status or 'invalid'}
            referrer_id = row['referrer_id']
            amount = row['reward_amount'] or 0
            if amount:
                conn.execute('UPDATE users SET hc_balance = hc_balance + ? WHERE telegram_id = ?', (amount, referrer_id))
            conn.execute(
                'UPDATE referrals SET status = ?, reward_amount = ?, rewarded_at = ?, note = NULL, reviewed_at = ?, reviewed_by = ? WHERE user_id = ?',
                ('rewarded', amount, now_iso, now_iso, admin_id, user_id)
            )
            balance_row = conn.execute('SELECT hc_balance FROM users WHERE telegram_id = ?', (referrer_id,)).fetchone()
            balance = balance_row[0] if balance_row else None
            return {'status': 'rewarded', 'amount': amount, 'referrer_id': referrer_id, 'balance': balance}


def deny_referral(user_id: int, admin_id: int, reason: str = '') -> dict:
    """Отклоняет отложенный реферал и учитывает страйки."""
    now = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now.isoformat()
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        with conn:
            row = conn.execute('SELECT referrer_id, status FROM referrals WHERE user_id = ?', (user_id,)).fetchone()
            if not row:
                return {'status': 'missing'}
            status = (row['status'] or '').lower() if row['status'] is not None else 'pending'
            if status not in ('pending', 'pending_admin'):
                return {'status': status or 'invalid'}
            referrer_id = row['referrer_id']
            conn.execute(
                'UPDATE referrals SET status = ?, note = ?, reward_amount = 0, rewarded_at = NULL, reviewed_at = ?, reviewed_by = ? WHERE user_id = ?',
                ('denied', reason or 'denied', now_iso, admin_id, user_id)
            )
            strikes_row = conn.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND status = ?', (referrer_id, 'denied')).fetchone()
            strike_count = int(strikes_row[0]) if strikes_row and strikes_row[0] is not None else 0
            disabled = False
            if strike_count >= 3:
                conn.execute('UPDATE users SET referral_disabled = 1 WHERE telegram_id = ?', (referrer_id,))
                disabled = True
            return {'status': 'denied', 'referrer_id': referrer_id, 'strike_count': strike_count, 'disabled': disabled}


def is_referrer_disabled(referrer_id: int) -> bool:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        row = conn.execute('SELECT referral_disabled FROM users WHERE telegram_id = ?', (referrer_id,)).fetchone()
    return bool(row[0]) if row else False


def clear_user_tour_roster(user_id, tour_id):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('DELETE FROM user_tour_roster WHERE user_id = ? AND tour_id = ?', (user_id, tour_id))


def save_user_tour_roster(user_id, tour_id, roster_dict, captain_id, spent):
    import json
    roster_json = json.dumps(roster_dict, ensure_ascii=False)
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('''
                INSERT OR REPLACE INTO user_tour_roster (user_id, tour_id, roster_json, captain_id, spent, timestamp)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, tour_id, roster_json, captain_id, spent))


def get_user_tour_roster(user_id, tour_id):
    import json
    with closing(sqlite3.connect(DB_NAME)) as conn:
        row = conn.execute('''
            SELECT roster_json, captain_id, spent, timestamp FROM user_tour_roster
            WHERE user_id = ? AND tour_id = ?
        ''', (user_id, tour_id)).fetchone()
        if row:
            roster = json.loads(row[0])
            return {
                'roster': roster,
                'captain_id': row[1],
                'spent': row[2],
                'timestamp': row[3]
            }
        return None




