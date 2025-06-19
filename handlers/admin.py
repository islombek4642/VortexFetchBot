from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database
from config import ADMIN_ID, logger, tashkent_tz
from utils.decorators import register_user

async def _generate_stats_message_and_keyboard(page: int) -> (str, InlineKeyboardMarkup):
    """Generates the text and keyboard for a given stats page."""
    total_users = database.get_total_user_count()
    users = database.get_users_for_page(page)

    if not users:
        return "Foydalanuvchilar topilmadi.", None

    message_text = f"📊 <b>Bot Statistikasi</b> 📊\n\nJami foydalanuvchilar: <b>{total_users}</b>\n\n"
    message_text += "<b>Oxirgi kirgan foydalanuvchilar:</b>\n"
    for user in users:
        user_id, username, first_name, last_name, last_seen_utc = user
        last_seen_tashkent = last_seen_utc.astimezone(tashkent_tz).strftime('%Y-%m-%d %H:%M:%S')
        display_name = first_name or username or str(user_id)
        message_text += f"- <a href='tg://user?id={user_id}'>{display_name}</a> (so'nggi faollik: {last_seen_tashkent})\n"

    total_pages = database.get_total_user_pages()
    message_text += f"\nSahifa: {page + 1}/{total_pages}"

    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"stats_page_{page - 1}"))
    if page < total_pages - 1:
        navigation_buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"stats_page_{page + 1}"))

    keyboard = [navigation_buttons] if navigation_buttons else None
    return message_text, InlineKeyboardMarkup(keyboard) if keyboard else None

@register_user
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays bot usage statistics, admin-only."""
    user_id = update.effective_user.id
    if str(user_id) != str(ADMIN_ID):
        await update.message.reply_text("Bu buyruq faqat admin uchun.")
        return

    message_text, reply_markup = await _generate_stats_message_and_keyboard(page=0)
    await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='HTML', disable_web_page_preview=True)
