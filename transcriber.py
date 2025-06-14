import logging
from faster_whisper import WhisperModel
import os
import asyncio

logger = logging.getLogger(__name__)

# "base" modeli - eng tez va eng kam resurs talab qiladigan model.
# Aniqligi pastroq, lekin tezkor transkripsiya uchun mos.
# Birinchi ishga tushganda, bu modelni yuklab oladi.
MODEL_SIZE = "base"
COMPUTE_TYPE = "int8" # CPU uchun optimizatsiya

try:
    logger.info(f"'{MODEL_SIZE}' modelini yuklash...")
    # device="cpu" va compute_type="int8" CPU optimizatsiyasi uchun
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type=COMPUTE_TYPE)
    logger.info("Model muvaffaqiyatli yuklandi.")
except Exception as e:
    logger.error(f"Whisper modelini yuklashda xatolik: {e}")
    model = None

def format_transcript(segments):
    """Transkripsiya segmentlarini vaqt belgilari bilan o'qiladigan matnga formatlaydi."""
    transcript = ""
    for segment in segments:
        start_time = round(segment.start)
        end_time = round(segment.end)
        # Vaqt belgisini formatlash: `[00:05 -> 00:10]`
        # Markdown'da to'g'ri ko'rinishi uchun backtick (`) belgilari qo'shildi.
        timestamp = f"`[{start_time//60:02d}:{start_time%60:02d} -> {end_time//60:02d}:{end_time%60:02d}]`"
        transcript += f"{timestamp} {segment.text.strip()}\n"
    return transcript

async def transcribe_audio_from_file(audio_path: str) -> (str, str):
    """
    Whisper modeli yordamida audio faylni transkripsiya qiladi.
    Aniqlangan til va formatlangan transkriptni qaytaradi.
    """
    if not model:
        error_message = "Transkripsiya modeli yuklanmagan. Iltimos, loglarni tekshiring."
        logger.error(error_message)
        return None, error_message

    if not os.path.exists(audio_path):
        error_message = f"Audio fayl topilmadi: {audio_path}"
        logger.error(error_message)
        return None, error_message
    
    try:
        logger.info(f"'{audio_path}' faylini transkripsiya qilish boshlandi...")
        loop = asyncio.get_running_loop()
        # Run the blocking transcribe function in a separate thread
        segments, info = await loop.run_in_executor(
            None,  # Use the default thread pool executor
            lambda: model.transcribe(audio_path, beam_size=5)
        )

        detected_language = info.language
        lang_probability = info.language_probability
        logger.info(f"Aniqlangan til: {detected_language} (ehtimollik: {lang_probability:.2f})")



        formatted_text = format_transcript(segments)
        
        logger.info(f"'{audio_path}' fayli muvaffaqiyatli transkripsiya qilindi.")
        return detected_language, formatted_text

    except Exception as e:
        error_message = f"Transkripsiya jarayonida xatolik yuz berdi: {e}"
        logger.error(error_message, exc_info=True)
        return None, error_message
