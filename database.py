import sqlite3
import logging
from datetime import datetime

# Logging sozlamalari
logger = logging.getLogger(__name__)

DB_FILE = "bot_users.db"

def init_db():
    """Ma'lumotlar bazasini va 'users' jadvalini yaratadi."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Ma'lumotlar bazasi muvaffaqiyatli ishga tushirildi.")
    except Exception as e:
        logger.error(f"DBni ishga tushirishda xatolik: {e}", exc_info=True)

def update_user(user_id: int, first_name: str, last_name: str, username: str):
    """Foydalanuvchini bazaga qo'shadi yoki ma'lumotlarini va oxirgi faollik vaqtini yangilaydi."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone():
        # Foydalanuvchi mavjud, 'last_seen'ni yangilaymiz
        cursor.execute('''
            UPDATE users 
            SET first_name = ?, last_name = ?, username = ?, last_seen = ? 
            WHERE user_id = ?
        ''', (first_name, last_name, username, now, user_id))
    else:
        # Yangi foydalanuvchi
        cursor.execute('''
            INSERT INTO users (user_id, first_name, last_name, username, first_seen, last_seen) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, first_name, last_name, username, now, now))
    
    conn.commit()
    conn.close()

def get_total_user_count() -> int:
    """Bazadagi jami foydalanuvchilar sonini qaytaradi."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_users_paginated(page: int, limit: int = 10) -> list:
    """Foydalanuvchilar ro'yxatini sahifalarga bo'lib qaytaradi."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    offset = (page - 1) * limit
    cursor.execute("SELECT * FROM users ORDER BY last_seen DESC LIMIT ? OFFSET ?", (limit, offset))
    users = cursor.fetchall()
    conn.close()
    return users
