import os
import logging
from dotenv import load_dotenv
import pytz

# --- Setup Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """Custom exception for configuration-related errors."""
    pass

class Config:
    """Manages loading, validation, and access to all configuration settings."""
    def __init__(self):
        load_dotenv()

        # --- Bot Credentials & Settings ---
        self.TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.ADMIN_ID_STR = os.getenv('ADMIN_ID')
        self.ADMIN_ID = None

        # --- File Paths ---
        self.DOWNLOAD_PATH = 'downloads'
        self.DB_FILE = "bot_users.db"
        # --- Optional Cookie File Paths ---
        self.YOUTUBE_COOKIE_FILE = os.getenv('YOUTUBE_COOKIE_FILE')
        self.INSTAGRAM_COOKIE_FILE = os.getenv('INSTAGRAM_COOKIE_FILE')

        # --- Timezone ---
        self.TASHKENT_TZ = pytz.timezone('Asia/Tashkent')

        self._validate()

    def _validate(self):
        """Validates critical configuration values after loading."""
        if not self.TOKEN:
            raise ConfigError("FATAL: TELEGRAM_BOT_TOKEN environment variable not set!")

        if not self.ADMIN_ID_STR:
            logger.warning("ADMIN_ID environment variable not set! Admin commands will not be restricted.")
        else:
            try:
                self.ADMIN_ID = int(self.ADMIN_ID_STR)
            except ValueError:
                raise ConfigError("FATAL: ADMIN_ID is not a valid integer. Please check your .env file.")

    def setup_environment(self):
        """Creates necessary directories and validates file paths. Should be called once at startup."""
        # Create download directory
        os.makedirs(self.DOWNLOAD_PATH, exist_ok=True)
        logger.info(f"Download directory ensured to exist: '{self.DOWNLOAD_PATH}'")

        # Check if cookie files exist and log warnings if not
        if self.YOUTUBE_COOKIE_FILE and not os.path.exists(self.YOUTUBE_COOKIE_FILE):
            logger.warning(
                f"YouTube cookie file specified but not found at '{self.YOUTUBE_COOKIE_FILE}'. "
                "Age-restricted downloads may fail."
            )
        elif self.YOUTUBE_COOKIE_FILE:
            logger.info(f"YouTube cookie file found: '{self.YOUTUBE_COOKIE_FILE}'")
        else:
            logger.warning(
                "YOUTUBE_COOKIE_FILE not set in .env. Age-restricted downloads may fail."
            )

        if self.INSTAGRAM_COOKIE_FILE and not os.path.exists(self.INSTAGRAM_COOKIE_FILE):
            logger.warning(
                f"Instagram cookie file specified but not found at '{self.INSTAGRAM_COOKIE_FILE}'. "
                "Instagram downloads may fail."
            )
        elif self.INSTAGRAM_COOKIE_FILE:
            logger.info(f"Instagram cookie file found: '{self.INSTAGRAM_COOKIE_FILE}'")
        else:
            logger.warning(
                "INSTAGRAM_COOKIE_FILE not set in .env. Instagram downloads may fail."
            )

# --- Global Singleton Instance ---
# This creates a single, globally accessible instance of the configuration.
# Other modules can `from config import settings` and use `settings.TOKEN` etc.
try:
    settings = Config()
except ConfigError as e:
    logger.error(e)
    exit(1) # Exit if critical config is missing or invalid
