import sqlite3
import logging
from datetime import datetime
from config import settings

logger = logging.getLogger(__name__)

class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initializes the database connection and creates tables."""
        try:
            self.conn = sqlite3.connect(settings.DB_FILE, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._create_tables()
            logger.info(f"Database connection to '{settings.DB_FILE}' established.")
        except sqlite3.Error as e:
            logger.error(f"Database connection failed: {e}", exc_info=True)
            raise

    def _create_tables(self):
        """Creates the necessary database tables if they don't exist."""
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT,
                    last_name TEXT,
                    username TEXT,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                )
            ''')
        logger.info("'users' table initialized.")

    def update_user(self, user_id: int, first_name: str, last_name: str, username: str):
        """Adds a new user or updates an existing one's details and last_seen timestamp."""
        now = datetime.now(settings.TASHKENT_TZ).strftime("%Y-%m-%d %H:%M:%S")
        with self.conn:
            cursor = self.conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            if cursor.fetchone():
                self.conn.execute('''
                    UPDATE users 
                    SET first_name = ?, last_name = ?, username = ?, last_seen = ? 
                    WHERE user_id = ?
                ''', (first_name, last_name, username, now, user_id))
            else:
                self.conn.execute('''
                    INSERT INTO users (user_id, first_name, last_name, username, first_seen, last_seen) 
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, first_name, last_name, username, now, now))

    def get_total_user_count(self) -> int:
        """Returns the total number of users in the database."""
        with self.conn:
            cursor = self.conn.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]

    def get_users_paginated(self, page: int, limit: int = 10) -> list[sqlite3.Row]:
        """Returns a paginated list of users, ordered by their last seen time."""
        offset = (page - 1) * limit
        with self.conn:
            cursor = self.conn.execute("SELECT * FROM users ORDER BY last_seen DESC LIMIT ? OFFSET ?", (limit, offset))
            return cursor.fetchall()

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed.")

# --- Global Singleton Instance ---
# Other modules can `from database import db` and use its methods.
db = Database()

