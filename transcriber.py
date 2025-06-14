import os
import logging
import asyncio
import collections.abc
from typing import AsyncGenerator
from wit import Wit
from dotenv import load_dotenv
from pydub import AudioSegment
from pydub.utils import make_chunks

# Logging sozlamalari
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# .env faylidan o'zgaruvchilarni yuklash
load_dotenv()
WIT_AI_TOKEN = os.getenv("WIT_AI_TOKEN")

wit_client = None
if not WIT_AI_TOKEN:
    logger.error("WIT_AI_TOKEN muhit o'zgaruvchisi topilmadi.")
else:
    try:
        wit_client = Wit(WIT_AI_TOKEN)
        logger.info("Wit.ai mijozi muvaffaqiyatli sozlandi.")
    except Exception as e:
        logger.error(f"Wit.ai mijozini sozlashda xatolik: {e}")

async def _transcribe_chunk(chunk_path: str, index: int, max_retries: int = 3) -> str:
    """Yordamchi funksiya: bitta audio bo'lakni matnga o'giradi, xatolik bo'lsa qayta urinadi."""
    if not wit_client:
        logger.error(f"Bo'lak {index+1}: Wit.ai mijozi sozlanmagan.")
        return ""

    loop = asyncio.get_event_loop()

    def sync_speech_call():
        with open(chunk_path, 'rb') as audio_file:
            resp = wit_client.speech(audio_file, {'Content-Type': 'audio/wav'})
            if resp:
                if isinstance(resp, collections.abc.Iterator):
                    return next(resp, None)
                return resp
            return None

    for attempt in range(max_retries + 1):
        try:
            logger.info(f"{index+1}-bo'lak Wit.ai'ga yuborilmoqda (urinish {attempt+1}/{max_retries+1})...")
            response = await loop.run_in_executor(None, sync_speech_call)
            if response and 'text' in response and response['text']:
                logger.info(f"{index+1}-bo'lak muvaffaqiyatli o'girildi.")
                return response['text']
            else:
                logger.warning(f"{index+1}-bo'lakni o'girishda xatolik yoki bo'sh matn. Javob: {response}")
        except Exception as e:
            logger.error(f"{index+1}-bo'lakni o'girishda xatolik (urinish {attempt+1}): {e}")
        
        if attempt < max_retries:
            await asyncio.sleep(2)
    
    logger.error(f"{index+1}-bo'lak barcha urinishlardan so'ng ham o'girilmadi.")
    return ""


async def transcribe_audio_from_file(audio_path: str) -> AsyncGenerator[tuple[str, int, int], None]:
    """
    Wit.ai yordamida audioni matnga o'giradi va natijalarni qismlarga bo'lib (yield), jonli tarzda qaytaradi.
    Qaytaradi: (matn bo'lagi, joriy bo'lak raqami, umumiy bo'laklar soni)
    """
    if not wit_client or not os.path.exists(audio_path):
        return

    try:
        audio = AudioSegment.from_file(audio_path)
        audio = audio.set_channels(1) # Monoga o'tkazish
        chunk_length_ms = 10 * 1000 # Bo'lak hajmini 25s ga o'zgartirish
        chunks = make_chunks(audio, chunk_length_ms)
        total_chunks = len(chunks)

        if total_chunks == 0:
            logger.warning("Audio faylni bo'laklarga bo'lib bo'lmadi.")
            return

        logger.info(f"Audio fayl {total_chunks} ta bo'lakka bo'lindi.")
        
        for i, chunk in enumerate(chunks):
            base_name = os.path.basename(audio_path).rsplit('.', 1)[0]
            chunk_name = f"downloads/chunk_{base_name}_{i}.wav"
            
            chunk.export(chunk_name, format="wav")
            
            text = await _transcribe_chunk(chunk_name, i)
            if text:
                yield text, i + 1, total_chunks
            
            try:
                os.remove(chunk_name)
            except OSError as e:
                logger.error(f"Vaqtinchalik faylni o'chirishda xatolik '{chunk_name}': {e}")

        logger.info("Barcha bo'laklarni qayta ishlash yakunlandi.")

    except Exception as e:
        logger.error(f"Transkripsiya paytida kutilmagan xatolik: {e}", exc_info=True)
