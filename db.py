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