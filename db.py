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