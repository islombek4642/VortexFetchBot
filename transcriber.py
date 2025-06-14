import os
import logging
import asyncio
from faster_whisper import WhisperModel

# Logging sozlamalari
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Modelni sozlash
MODEL_SIZE = "base"

try:
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    logger.info(f"Faster-Whisper modeli '{MODEL_SIZE}' muvaffaqiyatli yuklandi.")
except Exception as e:
    logger.error(f"Faster-Whisper modelini yuklashda xatolik: {e}", exc_info=True)
    model = None

async def transcribe_audio_from_file(audio_path: str) -> tuple[str, str]:
    """
    Faster-Whisper yordamida audio faylni asinxron ravishda matnga o'giradi.
    """
    if not model:
        return "n/a", "Xatolik: Transkripsiya modeli yuklanmagan."

    if not os.path.exists(audio_path):
        logger.error(f"Audio fayl topilmadi: {audio_path}")
        return "n/a", f"Xatolik: Audio fayl topilmadi: {audio_path}"

    def sync_transcribe():
        """Sinxron transkripsiya funksiyasi, alohida thread'da ishga tushirish uchun."""
        segments, info = model.transcribe(audio_path, beam_size=5)
        logger.info(f"Aniqlangan til: {info.language} ({info.language_probability:.2f} ehtimollik bilan)")
        transcript_parts = [segment.text for segment in segments]
        return info.language, " ".join(transcript_parts)

    try:
        loop = asyncio.get_event_loop()
        language, transcript = await loop.run_in_executor(None, sync_transcribe)
        
        if not transcript.strip():
             logger.warning(f"'{audio_path}' faylidan matn aniqlanmadi.")
             return language, "Matn aniqlanmadi."
             
        return language, transcript
        
    except Exception as e:
        logger.error(f"Transkripsiya vaqtida kutilmagan xatolik: {e}", exc_info=True)
        return "n/a", "Transkripsiya vaqtida kutilmagan xatolik yuz berdi."
