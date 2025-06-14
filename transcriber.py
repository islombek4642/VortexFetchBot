import os
import logging
import asyncio
import collections.abc
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
    logger.error("WIT_AI_TOKEN muhit o'zgaruvchisi topilmadi. Iltimos, uni .env fayliga yoki tizimga qo'shing.")
else:
    try:
        wit_client = Wit(WIT_AI_TOKEN)
        logger.info("Wit.ai mijozi muvaffaqiyatli sozlandi.")
    except Exception as e:
        logger.error(f"Wit.ai mijozini sozlashda xatolik: {e}")

async def _transcribe_chunk(chunk_path: str, index: int) -> str:
    """Yordamchi funksiya: bitta audio bo'lakni matnga o'giradi."""
    if not wit_client:
        logger.error(f"Bo'lak {index}: Wit.ai mijozi sozlanmagan.")
        return ""

    loop = asyncio.get_event_loop()

    def sync_speech_call():
        with open(chunk_path, 'rb') as audio_file:
            resp = wit_client.speech(audio_file, {'Content-Type': 'audio/mpeg'})
            if resp:
                # Wit.ai ba'zan iterator (generator) o'rniga to'g'ridan-to'g'ri dict qaytarishi mumkin.
                # Ikkala holatni ham to'g'ri ishlash uchun tekshiramiz.
                if isinstance(resp, collections.abc.Iterator):
                    return next(resp, None)
                return resp  # Agar dict bo'lsa, o'zini qaytaramiz
            return None

    try:
        logger.info(f"{index+1}-bo'lak Wit.ai'ga yuborilmoqda...")
        response = await loop.run_in_executor(None, sync_speech_call)
        if response and 'text' in response and response['text']:
            logger.info(f"{index+1}-bo'lak muvaffaqiyatli o'girildi.")
            return response['text']
        else:
            logger.warning(f"{index+1}-bo'lakni o'girishda xatolik yoki bo'sh matn. Javob: {response}")
            return ""
    except Exception as e:
        logger.error(f"{index+1}-bo'lakni o'girishda xatolik: {e}")
        return ""


async def transcribe_audio_from_file(audio_path: str) -> (str, str):
    """
    Wit.ai API yordamida audio faylni matnga o'giradi.
    Uzoq audiolarni bo'laklarga bo'lib, alohida yuboradi.
    """
    if not wit_client:
        return "Xatolik: Wit.ai mijozi sozlanmagan.", "n/a"

    if not os.path.exists(audio_path):
        return f"Xatolik: Audio fayl topilmadi: {audio_path}", "n/a"

    try:
        logger.info(f"'{audio_path}' fayli ochilmoqda va bo'laklarga bo'linmoqda...")
        audio = AudioSegment.from_file(audio_path)
        
        # Timeout xatosini oldini olish uchun bo'lak hajmini kichraytiramiz
        chunk_length_ms = 15 * 1000 
        chunks = make_chunks(audio, chunk_length_ms)
        
        if not chunks:
            return "Audio faylni bo'laklarga bo'lib bo'lmadi.", "n/a"

        logger.info(f"Audio fayl {len(chunks)} ta bo'lakka bo'lindi.")
        
        transcribed_texts = []
        
        for i, chunk in enumerate(chunks):
            base_name = os.path.basename(audio_path).rsplit('.', 1)[0]
            chunk_name = f"downloads/chunk_{base_name}_{i}.mp3"
            
            logger.info(f"{i+1}/{len(chunks)}-bo'lak '{chunk_name}' fayliga saqlanmoqda...")
            chunk.export(chunk_name, format="mp3")
            
            text = await _transcribe_chunk(chunk_name, i)
            if text:
                transcribed_texts.append(text)
            
            try:
                os.remove(chunk_name)
            except OSError as e:
                logger.error(f"Vaqtinchalik faylni o'chirishda xatolik '{chunk_name}': {e}")

        if not transcribed_texts:
            return "Audio fayldan matn aniqlanmadi.", "n/a"

        final_text = " ".join(transcribed_texts)
        logger.info("Yakuniy transkripsiya muvaffaqiyatli yaratildi.")
        return final_text, "wit.ai"

    except Exception as e:
        logger.error(f"Transkripsiya paytida kutilmagan xatolik: {e}", exc_info=True)
        return "Transkripsiya paytida kutilmagan xatolik yuz berdi.", "n/a"
