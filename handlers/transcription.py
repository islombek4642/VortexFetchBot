import os
import ffmpeg
import functools

from telegram import Update
from telegram.ext import ContextTypes

from config import DOWNLOAD_PATH, logger
from utils.decorators import register_user
from utils.helpers import _run_ffmpeg_async
from transcriber import transcribe_audio_from_file

@register_user
async def handle_media_for_transcription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles audio, video, and voice messages for transcription."""
    message = update.message
    user_id = message.from_user.id
    file_to_download = message.audio or message.video or message.voice

    if not file_to_download:
        await message.reply_text("Iltimos, matnga o'girish uchun audio, video yoki ovozli xabar yuboring.")
        return

    status_message = await message.reply_text("Fayl qabul qilindi. Ovozni matnga o'girish uchun tayyorlanmoqda...")

    downloaded_file_path = None
    output_audio_path = None
    try:
        file_id = file_to_download.file_id
        file = await context.bot.get_file(file_id)
        
        original_filename = file_to_download.file_name or 'media.bin'
        downloaded_file_path = os.path.join(DOWNLOAD_PATH, f"{user_id}_{file_id}_{original_filename}")
        await file.download_to_drive(downloaded_file_path)
        logger.info(f"File downloaded for transcription: {downloaded_file_path}")

        audio_path_to_transcribe = downloaded_file_path

        if message.video:
            await status_message.edit_text("Videodan audio ajratib olinmoqda...")
            output_audio_path = os.path.join(DOWNLOAD_PATH, f"{user_id}_{file_id}_extracted_audio.mp3")
            try:
                await _run_ffmpeg_async(functools.partial(ffmpeg.input(downloaded_file_path).output(output_audio_path, acodec='libmp3lame', ar='16000').run, overwrite_output=True, quiet=True))
                audio_path_to_transcribe = output_audio_path
                logger.info(f"Audio extracted successfully: {output_audio_path}")
            except ffmpeg.Error as e:
                logger.error(f"ffmpeg error: {e.stderr.decode() if e.stderr else 'Unknown error'}")
                await status_message.edit_text("Videodan audioni ajratib olishda xatolik yuz berdi.")
                return

        await status_message.edit_text("Audio tahlil qilinmoqda... Bu biroz vaqt olishi mumkin.")
        language, transcript = await transcribe_audio_from_file(audio_path_to_transcribe)

        if transcript and language and language != 'n/a':
            header = f"✅ Transkripsiya muvaffaqiyatli yakunlandi!\n\n**Aniqlangan til:** `{language.upper()}`\n---\n"
            if len(header) + len(transcript) > 4096:
                await status_message.edit_text(header, parse_mode='Markdown')
                for i in range(0, len(transcript), 4096):
                    await update.message.reply_text(transcript[i:i+4096])
            else:
                await status_message.edit_text(header + transcript, parse_mode='Markdown')
        else:
            await status_message.edit_text(transcript or "Noma'lum xatolik yuz berdi yoki matn aniqlanmadi.")

    except Exception as e:
        logger.error(f"General error in transcription process: {e}", exc_info=True)
        await status_message.edit_text("Kechirasiz, faylni qayta ishlashda kutilmagan xatolik yuz berdi.")
    finally:
        if downloaded_file_path and os.path.exists(downloaded_file_path):
            os.remove(downloaded_file_path)
        if output_audio_path and os.path.exists(output_audio_path):
            os.remove(output_audio_path)
