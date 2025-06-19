
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- Local Imports ---
from config import TOKEN, logger
import database

# --- Handler Imports ---
from handlers.general import start, help_command
from handlers.admin import stats
from handlers.downloader import download_video
from handlers.callbacks import button
from handlers.transcription import handle_media_for_transcription


def main() -> None:
    """Start the bot."""
    # Initialize the database
    database.init_db()
    
    logger.info("Bot is starting...")

    # Create the Application and pass it your bot's token.
    application = ApplicationBuilder().token(TOKEN).build()

    # === Command Handlers ===
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats))

    # === Message Handlers ===
    # For video links
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))
    # For audio/video/voice files for transcription
    application.add_handler(MessageHandler(filters.AUDIO | filters.VIDEO | filters.VOICE, handle_media_for_transcription))

    # === Callback Query Handler ===
    application.add_handler(CallbackQueryHandler(button))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot has started successfully. Polling for updates...")
    application.run_polling()


if __name__ == '__main__':
    main()

