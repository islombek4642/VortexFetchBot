import os
import logging
import asyncio
from wit import Wit
from dotenv import load_dotenv

# Logging sozlamalari
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# .env faylidan o'zgaruvchilarni yuklash
load_dotenv()
WIT_AI_TOKEN = os.getenv("WIT_AI_TOKEN")

wit_client = None
if not WIT_AI_TOKEN:
    logger.error("WIT_AI_TOKEN muhit o'zgaruvchisi topilmadi. Iltimos, uni .env fayliga yoki tizimga qo'shing.")
else:
    try:
        wit_client = Wit(WIT_AI_TOKEN)
        logger.info("Wit.ai mijozi muvaffaqiyatli sozlandi.")
    except Exception as e:
        logger.error(f"Wit.ai mijozini sozlashda xatolik: {e}")

async def transcribe_audio_from_file(audio_path: str) -> (str, str):
    """
    Wit.ai API yordamida audio faylni matnga o'giradi.
    Qaytadigan qiymatlar: (transkripsiya qilingan matn, til uchun belgi)
    """
    if not wit_client:
        return "Xatolik: Wit.ai mijozi sozlanmagan.", "n/a"

    if not os.path.exists(audio_path):
        return f"Xatolik: Audio fayl topilmadi: {audio_path}", "n/a"

    try:
        logger.info(f"'{audio_path}' fayli Wit.ai'ga yuborilmoqda...")
        
        loop = asyncio.get_event_loop()

        def sync_speech_call():
            with open(audio_path, 'rb') as audio_file:
                # wit.speech sinxron kutubxona bo'lgani uchun uni executor'da ishga tushiramiz
                resp = wit_client.speech(audio_file, {'Content-Type': 'audio/mpeg'})
                # Wit.ai dan kelgan javob generator bo'lishi mumkin, birinchi natijani olamiz
                if resp:
                    return next(resp, None)
                return None

        response = await loop.run_in_executor(None, sync_speech_call)

        if response and 'text' in response and response['text']:
            text = response['text']
            logger.info(f"Wit.ai transkripsiya natijasi: {text}")
            # Wit.ai tilni aniq qaytarmaydi, shuning uchun manbani ko'rsatamiz
            return text, "wit.ai"
        else:
            logger.warning(f"Wit.ai dan matn olinmadi yoki matn bo'sh. To'liq javob: {response}")
            return "Matn aniqlanmadi.", "n/a"

    except Exception as e:
        logger.error(f"Wit.ai transkripsiya paytida xatolik: {e}", exc_info=True)
        return f"Transkripsiya paytida xatolik yuz berdi.", "n/a"
