import logging
from faster_whisper import WhisperModel
import os

logger = logging.getLogger(__name__)

# Aniqlikni oshirish uchun "medium" modelidan foydalanamiz.
# Bu model "base"ga qaraganda ancha aniqroq, lekin ko'proq resurs talab qiladi.
# Birinchi ishga tushganda, bu modelni yuklab oladi.
MODEL_SIZE = "medium"
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
        segments, info = model.transcribe(audio_path, beam_size=5)

        detected_language = info.language
        lang_probability = info.language_probability
        logger.info(f"Aniqlangan til: {detected_language} (ehtimollik: {lang_probability:.2f})")

        # Foydalanuvchi faqat ingliz va rus tillarini so'radi
        if detected_language not in ['en', 'ru']:
            unsupported_lang_message = f"Kechirasiz, faqat ingliz (en) va rus (ru) tillari qo'llab-quvvatlanadi. Bu audioda '{detected_language}' tili aniqlandi."
            logger.warning(f"Qo'llab-quvvatlanmaydigan til aniqlandi: {detected_language}")
            return None, unsupported_lang_message

        formatted_text = format_transcript(segments)
        
        logger.info(f"'{audio_path}' fayli muvaffaqiyatli transkripsiya qilindi.")
        return detected_language, formatted_text

    except Exception as e:
        error_message = f"Transkripsiya jarayonida xatolik yuz berdi: {e}"
        logger.error(error_message, exc_info=True)
        return None, error_message
