import sqlite3
from contextlib import closing

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

def update_hc_balance(telegram_id, amount):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute('UPDATE users SET hc_balance = hc_balance + ? WHERE telegram_id = ?', (amount, telegram_id))

def get_all_users():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return conn.execute('SELECT telegram_id FROM users').fetchall()

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