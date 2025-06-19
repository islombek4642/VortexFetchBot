
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# --- Local Imports ---
from config import settings, logger
import database

from handlers import general, callbacks

async def post_init(application: Application) -> None:
    """Post-initialization function to set bot commands."""
    await application.bot.set_my_commands([
        ('start', 'Botni ishga tushirish'),
        ('help', 'Yordam'),
        ('stats', 'Statistika (admin uchun)'),
    ])

def main() -> None:
    """Initializes and runs the bot."""
    # Setup environment (create directories, cookie files, etc.) before anything else
    settings.setup_environment()

    logger.info("Bot is starting...")

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(settings.TOKEN).post_init(post_init).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", general.start))
    application.add_handler(CommandHandler("help", general.help_command))
    application.add_handler(CommandHandler("stats", general.stats_command))

    # Register message handlers for different types of content
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, general.handle_message))
    application.add_handler(MessageHandler((filters.AUDIO | filters.VIDEO | filters.VOICE), general.handle_media))

    # Register callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(callbacks.button))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot has started successfully. Polling for updates...")
    application.run_polling()

if __name__ == '__main__':
    main()
