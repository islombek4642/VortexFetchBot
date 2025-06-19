from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
import database
from config import logger

def register_user(func):
    """A decorator that registers/updates user info in the database before executing the command."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update:
            user = update.effective_user
            if user:
                logger.debug(f"Registering user: {user.id} - {user.username}")
                database.update_user(
                    user_id=user.id,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    username=user.username
                )
        return await func(update, context, *args, **kwargs)
    return wrapped
