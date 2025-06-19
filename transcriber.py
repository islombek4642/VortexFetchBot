import os
import logging
from wit import Wit
import asyncio

# Logging sozlamalari
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Wit.ai klientini sozlash
# WIT_AI_TOKEN ni .env faylidan olish kerak
WIT_AI_TOKEN = os.getenv("WIT_AI_TOKEN")

if not WIT_AI_TOKEN:
    logger.warning("WIT_AI_TOKEN muhit o'zgaruvchisi topilmadi. Transkripsiya funksiyasi ishlamaydi.")
    client = None
else:
    try:
        client = Wit(WIT_AI_TOKEN)
        logger.info("Wit.ai klienti muvaffaqiyatli ishga tushirildi.")
    except Exception as e:
        logger.error(f"Wit.ai klientini ishga tushirishda xatolik: {e}")
        client = None

async def transcribe_audio_from_file(audio_path: str) -> str:
    """
    Wit.ai yordamida audio faylni asinxron ravishda matnga o'giradi.
    Audio faylning to'liq yo'lini (path) qabul qiladi.
    Transkripsiya qilingan matnni (string) qaytaradi.
    """
    if not client:
        error_message = "Xatolik: Transkripsiya xizmati sozlanmagan (WIT_AI_TOKEN topilmadi)."
        logger.error(error_message)
        return error_message

    if not os.path.exists(audio_path):
        error_message = f"Xatolik: Audio fayl topilmadi: {audio_path}"
        logger.error(error_message)
        return error_message

    def sync_transcribe():
        """Sinxron Wit.ai API so'rovini alohida thread'da ishga tushirish uchun funksiya."""
        with open(audio_path, 'rb') as audio_file:
            try:
                # Wit.ai API ga audio yuborish
                # Content-Type fayl formatiga qarab o'zgarishi mumkin.
                # Eng keng tarqalgan formatlar uchun 'audio/mpeg' yoki 'audio/wav' ishlatiladi.
                resp = client.speech(audio_file, {'Content-Type': 'audio/mpeg'})
                
                # Wit.ai javobidan matnni ajratib olish
                transcript = resp.get('text') or resp.get('_text')
                
                if not transcript and isinstance(resp, list) and resp:
                    # Ba'zi hollarda javob list ko'rinishida kelishi mumkin
                    transcript = resp[-1].get('text') or resp[-1].get('_text')

                return transcript if transcript else "Matn aniqlanmadi."
            except Exception as e:
                logger.error(f"Wit.ai API bilan ishlashda xatolik: {e}", exc_info=True)
                return "Transkripsiya vaqtida API xatoligi yuz berdi."

    try:
        loop = asyncio.get_event_loop()
        # Sinxron funksiyani asinxron kodda bloklamasdan ishlatish
        transcript = await loop.run_in_executor(None, sync_transcribe)
        
        if not transcript or not transcript.strip():
             logger.warning(f"'{audio_path}' faylidan matn aniqlanmadi.")
             return "Matn aniqlanmadi."
             
        logger.info(f"'{audio_path}' fayli muvaffaqiyatli transkripsiya qilindi.")
        return transcript
        
    except Exception as e:
        logger.error(f"Transkripsiya vaqtida kutilmagan xatolik: {e}", exc_info=True)
        return "Transkripsiya vaqtida kutilmagan xatolik yuz berdi."
