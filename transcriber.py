import logging
import asyncio
from typing import AsyncGenerator
from faster_whisper import WhisperModel

# Logging sozlamalari
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Modelni yuklash (birinchi marta yuklash uchun vaqt talab qilishi mumkin)
MODEL_SIZE = "base"
model = None
try:
    logger.info(f"'{MODEL_SIZE}' modelini yuklash boshlandi...")
    # Modeli "cpu" da va "int8" hisoblash turi bilan ishga tushirish resurslarni tejaydi
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    logger.info(f"'{MODEL_SIZE}' modeli muvaffaqiyatli yuklandi.")
except Exception as e:
    logger.error(f"Whisper modelini yuklashda xatolik: {e}")

async def transcribe_audio_from_file(audio_path: str) -> AsyncGenerator[str, None]:
    """
    faster-whisper yordamida audioni matnga o'giradi va natijalarni qismlarga bo'lib (yield) qaytaradi.
    """
    if not model:
        logger.error("Transkripsiya uchun model yuklanmagan.")
        return

    try:
        loop = asyncio.get_event_loop()
        
        def sync_transcribe():
            # model.transcribe asinxron emas, shuning uchun executor'da ishlatamiz
            segments, info = model.transcribe(audio_path, beam_size=5)
            logger.info(f"Aniqlangan til: {info.language} ({info.language_probability*100:.2f}% ehtimollik bilan)")
            logger.info(f"Audio davomiyligi: {info.duration:.2f} soniya")
            return segments

        logger.info(f"'{audio_path}' faylini transkripsiya qilish boshlandi...")
        segments_iterator = await loop.run_in_executor(None, sync_transcribe)

        for segment in segments_iterator:
            text_chunk = segment.text.strip()
            if text_chunk:
                yield text_chunk
        
        logger.info("Transkripsiya muvaffaqiyatli yakunlandi.")

    except Exception as e:
        logger.error(f"Transkripsiya paytida kutilmagan xatolik: {e}", exc_info=True)
