# game_db.py
import sqlite3

def init_db():
    with sqlite3.connect('game.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                score INTEGER DEFAULT 0  -- Add score column
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY,
                user_id TEXT,
                number INTEGER,
                attempts INTEGER,
                finished INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(username)
            )
        ''')
        conn.commit()

def get_db_connection():
    conn = sqlite3.connect('game.db')
    conn.row_factory = sqlite3.Row
    return conn

# Initialize the database
init_db()
