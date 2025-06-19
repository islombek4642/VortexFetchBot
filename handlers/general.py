from telegram import Update
from telegram.ext import ContextTypes
from utils.decorators import register_user

@register_user
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Assalomu alaykum, {user.mention_html()}!",
        reply_markup=None,
    )

@register_user
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a detailed help message with all available commands and features."""
    help_text = """
👋 Salom! Men video yuklovchi va qo'shiq aniqlovchi botman.

Mening asosiy vazifalarim:
1️⃣ <b>Video Yuklash</b>: TikTok, Instagram, YouTube kabi platformalardan video havolasini yuboring, men uni sizga video formatda yuboraman.
2️⃣ <b>Qo'shiqni Aniqlash</b>: Agar yuborilgan videoda musiqa bo'lsa, men uni aniqlashga harakat qilaman va sizga audio formatda yuklab olishni taklif qilaman.
3️⃣ <b>Ovozni Matnga O'girish</b>: Menga audio, video yoki ovozli xabar yuboring, men uni matnga o'girib beraman.

<b>Buyruqlar:</b>
• /start - Botni ishga tushirish
• /help - Ushbu yordam xabarini ko'rsatish

Foydalanish oddiy: shunchaki video havolasini yoki faylni yuboring!
"""
    await update.message.reply_text(help_text, parse_mode='HTML')
