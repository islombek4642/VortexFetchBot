import os
import logging
import asyncio
import math
from wit import Wit
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

# Logging sozlamalari
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Wit.ai klientini sozlash
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

async def _transcribe_chunk(chunk_path: str) -> str | None:
    """Bir audio bo'lagini Wit.ai yordamida alohida thread'da matnga o'giradi."""
    if not client:
        return None

    def sync_transcribe():
        try:
            with open(chunk_path, 'rb') as audio_file:
                # Matnni aniqlash sifatini oshirish uchun WAV formatidan foydalanamiz
                resp = client.speech(audio_file, {'Content-Type': 'audio/wav'})
                transcript = resp.get('text')
                if not transcript and isinstance(resp, list) and resp:
                    transcript = resp[-1].get('text')
                return transcript
        except Exception as e:
            logger.error(f"Wit.ai API so'rovida xatolik ({os.path.basename(chunk_path)}): {e}", exc_info=False)
            return None

    try:
        loop = asyncio.get_event_loop()
        transcript = await loop.run_in_executor(None, sync_transcribe)
        return transcript
    except Exception as e:
        logger.error(f"Executor xatoligi ({os.path.basename(chunk_path)}): {e}", exc_info=True)
        return None

async def transcribe_audio_from_file(audio_path: str) -> str:
    """Audioni bo'laklarga bo'lib, Wit.ai yordamida matnga o'giradi."""
    if not client:
        return "Xatolik: Transkripsiya xizmati sozlanmagan (WIT_AI_TOKEN topilmadi)."

    if not os.path.exists(audio_path):
        return f"Xatolik: Audio fayl topilmadi: {audio_path}"

    try:
        audio = AudioSegment.from_file(audio_path)
    except CouldntDecodeError:
        logger.error(f"Pydub audio faylni o'qiy olmadi: {audio_path}")
        return "Audio faylni o'qishda xatolik. Fayl formati noto'g'ri bo'lishi mumkin."
    except Exception as e:
        logger.error(f"Audio faylni yuklashda xatolik {audio_path}: {e}", exc_info=True)
        return "Audio faylni yuklashda kutilmagan xatolik."

    chunk_length_ms = 15 * 1000  # 15 soniya
    num_chunks = math.ceil(len(audio) / chunk_length_ms)
    temp_dir = os.path.dirname(audio_path)
    full_transcript = []
    
    logger.info(f"{os.path.basename(audio_path)} audiosini {num_chunks} ta bo'lakka bo'lish boshlandi.")

    for i in range(num_chunks):
        start_ms = i * chunk_length_ms
        end_ms = start_ms + chunk_length_ms
        audio_chunk = audio[start_ms:end_ms]
        # Vaqtinchalik fayl uchun .wav kengaytmasidan foydalanamiz
        chunk_path = os.path.join(temp_dir, f"temp_chunk_{i}_{os.path.basename(audio_path)}.wav")

        try:
            # Matnni aniqlash sifatini oshirish uchun audioni maxsus formatlangan WAV ga o'tkazamiz
            audio_chunk.export(
                chunk_path, 
                format="wav", 
                parameters=["-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le"]
            )
            transcript_part = await _transcribe_chunk(chunk_path)
            if transcript_part:
                full_transcript.append(transcript_part)
                logger.info(f"Bo'lak {i+1}/{num_chunks} muvaffaqiyatli matnga o'girildi.")
            else:
                logger.warning(f"Bo'lak {i+1}/{num_chunks} dan matn topilmadi.")
        except Exception as e:
            logger.error(f"Bo'lakni qayta ishlashda xatolik {i+1}/{num_chunks}: {e}", exc_info=True)
        finally:
            if os.path.exists(chunk_path):
                os.remove(chunk_path)

    if not full_transcript:
        logger.warning(f"{os.path.basename(audio_path)} faylidan matn aniqlanmadi.")
        return "Matn aniqlanmadi."

    final_text = " ".join(full_transcript)
    logger.info(f"{os.path.basename(audio_path)} fayli muvaffaqiyatli matnga o'girildi.")
    return final_text
