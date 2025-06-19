import os
import logging
from dotenv import load_dotenv
import pytz

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# --- Bot Credentials & Settings ---
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID_STR = os.getenv('ADMIN_ID')
WIT_AI_TOKEN = os.getenv('WIT_AI_TOKEN') # For transcription
YOUTUBE_COOKIES = os.getenv('YOUTUBE_COOKIES')

# --- Validate Admin ID ---
ADMIN_ID = None
if not TOKEN:
    logger.error("FATAL: TELEGRAM_BOT_TOKEN environment variable not set!")
    exit()

if not ADMIN_ID_STR:
    logger.warning("ADMIN_ID environment variable not set! Stats command will not be restricted.")
else:
    try:
        ADMIN_ID = int(ADMIN_ID_STR)
    except ValueError:
        logger.error("FATAL: ADMIN_ID is not a valid integer. Please check your .env file.")
        exit()

# --- File Paths ---
DOWNLOAD_PATH = 'downloads'
COOKIE_FILE_PATH = "cookies.txt"

# Create download directory if it doesn't exist
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# --- Timezone ---
tashkent_tz = pytz.timezone('Asia/Tashkent')

# --- YouTube Cookies Setup ---
if YOUTUBE_COOKIES:
    try:
        with open(COOKIE_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(YOUTUBE_COOKIES)
        logger.info("YouTube cookie file successfully created from environment variable.")
    except Exception as e:
        logger.error(f"Error writing cookie file: {e}")
else:
    logger.warning("YOUTUBE_COOKIES environment variable is not set. Some downloads might fail.")
