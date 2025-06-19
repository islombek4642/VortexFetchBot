from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from database import db
from config import logger

def register_user(func):
    """A decorator that registers/updates user info in the database before executing the command."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update:
            user = update.effective_user
            if user:
                try:
                    logger.debug(f"Registering user: {user.id} - {user.username}")
                    db.update_user(
                        user_id=user.id,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        username=user.username
                    )
                except Exception as e:
                    logger.error(f"Failed to register/update user {user.id}: {e}", exc_info=True)
        return await func(update, context, *args, **kwargs)
    return wrapped
