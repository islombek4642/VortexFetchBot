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
        self.WIT_AI_TOKEN = os.getenv('WIT_AI_TOKEN')
        self.YOUTUBE_COOKIES = os.getenv('YOUTUBE_COOKIES')
        self.ADMIN_ID = None

        # --- File Paths ---
        self.DOWNLOAD_PATH = 'downloads'
        self.COOKIE_FILE_PATH = "cookies.txt"
        self.DB_FILE = "bot_users.db"

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
        """Creates necessary directories and files. Should be called once at startup."""
        # Create download directory
        os.makedirs(self.DOWNLOAD_PATH, exist_ok=True)
        logger.info(f"Download directory ensured to exist: '{self.DOWNLOAD_PATH}'")

        # Create YouTube cookie file from environment variable
        if self.YOUTUBE_COOKIES:
            try:
                with open(self.COOKIE_FILE_PATH, 'w', encoding='utf-8') as f:
                    f.write(self.YOUTUBE_COOKIES)
                logger.info(f"YouTube cookie file '{self.COOKIE_FILE_PATH}' successfully created.")
            except IOError as e:
                logger.error(f"Error writing cookie file: {e}")
        else:
            logger.warning("YOUTUBE_COOKIES env var not set. Age-restricted downloads may fail.")

# --- Global Singleton Instance ---
# This creates a single, globally accessible instance of the configuration.
# Other modules can `from config import settings` and use `settings.TOKEN` etc.
try:
    settings = Config()
except ConfigError as e:
    logger.error(e)
    exit(1) # Exit if critical config is missing or invalid
