import sqlite3
from contextlib import closing

DB_NAME = 'fantasy_khl.db'

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
                    hc_balance INTEGER DEFAULT 0
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
                    image_file_id TEXT DEFAULT ''
                )
            ''')
            # Миграция: добавить колонку image_file_id при отсутствии
            try:
                conn.execute('ALTER TABLE challenges ADD COLUMN image_file_id TEXT DEFAULT ""')
            except Exception:
                pass
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
def create_challenge(start_date: str, deadline: str, end_date: str, image_filename: str, image_file_id: str = "") -> int:
    """Создаёт запись челленджа и возвращает его id. Статус вычисляется относительно текущего времени."""
    import datetime
    now = datetime.datetime.utcnow()
    def _parse(s):
        try:
            return datetime.datetime.fromisoformat(s)
        except Exception:
            return None
    sd = _parse(start_date)
    dl = _parse(deadline)
    ed = _parse(end_date)
    status = 'в ожидании'
    if sd and dl and ed:
        if sd <= now < dl:
            status = 'активен'
        elif dl <= now < ed:
            status = 'в игре'
        elif now >= ed:
            status = 'завершен'
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            cur = conn.execute(
                'INSERT INTO challenges (start_date, deadline, end_date, image_filename, status, image_file_id) VALUES (?, ?, ?, ?, ?, ?)',
                (start_date, deadline, end_date, image_filename, status, image_file_id or "")
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

def get_latest_challenge():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        row = conn.execute('SELECT id, start_date, deadline, end_date, image_filename, status, image_file_id FROM challenges ORDER BY id DESC LIMIT 1').fetchone()
        return row

def get_all_challenges():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return conn.execute('SELECT id, start_date, deadline, end_date, image_filename, status FROM challenges ORDER BY id DESC').fetchall()

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
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return conn.execute('''
            SELECT tr.cost, p.id, p.name, p.position, p.club, p.nation, p.age, p.price
            FROM tour_roster tr
            JOIN players p ON tr.player_id = p.id
            WHERE tr.tour_num = ?
            ORDER BY tr.cost DESC, tr.id ASC
        ''', (tour_num,)).fetchall()

def remove_player(player_id):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            cursor = conn.execute('DELETE FROM players WHERE id = ?', (player_id,))
            return cursor.rowcount > 0

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
                    referrer_id INTEGER
                )
            ''')

def add_referral_if_new(user_id: int, referrer_id: int) -> bool:
    """Сохраняет пару (user_id -> referrer_id), если для user_id ещё не было записи.
    Возвращает True, если запись была добавлена (т.е. первый раз), иначе False.
    """
    if user_id == referrer_id:
        return False
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            exists = conn.execute('SELECT 1 FROM referrals WHERE user_id = ?', (user_id,)).fetchone()
            if exists:
                return False
            conn.execute('INSERT INTO referrals (user_id, referrer_id) VALUES (?, ?)', (user_id, referrer_id))
            return True

def set_tour_winners(tour_id, winners):
    import json
    winners_str = json.dumps(winners)
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('UPDATE tours SET winners = ? WHERE id = ?', (winners_str, tour_id))

# --- Получить активный тур ---
def get_active_tour():
    import datetime
    now = datetime.datetime.now()
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        # 1. Сначала ищем тур со статусом "активен"
        row = conn.execute('SELECT * FROM tours WHERE status = ? ORDER BY start_date ASC LIMIT 1', ("активен",)).fetchone()
        if row:
            return dict(row)
        # 2. Если нет — ищем тур по дате
        rows = conn.execute('SELECT * FROM tours').fetchall()
        for r in rows:
            try:
                start = datetime.datetime.strptime(r['start_date'], "%d.%m.%y")
                deadline = datetime.datetime.strptime(r['deadline'], "%d.%m.%y %H:%M")
                if start <= now < deadline:
                    return dict(r)
            except Exception:
                continue
        return None

# --- Финальный состав пользователя на тур ---

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