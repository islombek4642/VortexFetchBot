import os
import ffmpeg
import html
import uuid
import functools
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes
from shazamio import Shazam

from config import DOWNLOAD_PATH, COOKIE_FILE_PATH, logger
from utils.decorators import register_user
from utils.helpers import find_first_file, _run_yt_dlp_with_progress, _run_ffmpeg_async

@register_user
async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Downloads video from the URL sent by the user."""
    user_id = update.message.from_user.id
    video_path = None
    url = update.message.text

    status_message = await update.message.reply_text("So'rovingiz qayta ishlanmoqda... Iltimos kuting.")

    if not url or not (url.startswith('http://') or url.startswith('https://')):
        await status_message.edit_text("Iltimos, to'g'ri video havolasini yuboring.")
        return

    output_template = os.path.join(DOWNLOAD_PATH, f'{user_id}_{update.update_id}_%(title)s.%(ext)s')
    command = [
        'yt-dlp',
        '-f', 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best',
        '--merge-output-format', 'mp4',
        '-o', output_template,
        '--max-filesize', '49m',
    ]
    if os.path.exists(COOKIE_FILE_PATH):
        command.extend(['--cookies', COOKIE_FILE_PATH])
    command.append(url)

    try:
        logger.info(f"Attempting to download: {url} with command: {' '.join(command)}")
        await status_message.edit_text("Yuklanmoqda... 0%")
        return_code, stderr_output = await _run_yt_dlp_with_progress(command, status_message, "Yuklanmoqda...")
        
        if return_code != 0:
            logger.error(f"yt-dlp error for URL {url}: {stderr_output}")
            error_message = "❌ Videoni yuklashda xatolik yuz berdi."
            if "Unsupported URL" in stderr_output:
                error_message = "❌ Noto'g'ri yoki qo'llab-quvvatlanmaydigan havola."
            elif "Video unavailable" in stderr_output:
                error_message = "❌ Video mavjud emas."
            elif "File is larger than the maximum" in stderr_output:
                error_message = "❌ Video hajmi 50MB dan katta, yuklab bo'lmadi."
            await status_message.edit_text(error_message)
            return

        video_path = find_first_file(DOWNLOAD_PATH, f'{user_id}_{update.update_id}_')
        
        if not video_path:
            logger.error(f"yt-dlp finished but no file found for URL: {url}")
            await status_message.edit_text("❌ Videoni yuklab olishning iloji bo'lmadi yoki fayl topilmadi.")
            return
        
        logger.info(f"Successfully downloaded video to: {video_path}")
        await status_message.edit_text("Yuklab olish yakunlandi! Musiqa aniqlanmoqda...")

        inline_markup = await recognize_and_offer_song_download(context, status_message, video_path, user_id, update.update_id)

        filename_parts = os.path.basename(video_path).split('_')
        clean_caption = " ".join(filename_parts[2:])

        with open(video_path, 'rb') as video_file:
            await update.message.reply_video(
                video=video_file,
                caption=clean_caption,
                reply_markup=inline_markup
            )
        
        await status_message.delete()
        logger.info(f"Successfully sent video and cleaned up for: {video_path}")

    except Exception as e:
        logger.error(f"Video yuklash jarayonida kutilmagan xatolik: {e}", exc_info=True)
        await status_message.edit_text("Kechirasiz, videoni yuklashda kutilmagan xatolik yuz berdi.")
    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)

async def recognize_and_offer_song_download(context: ContextTypes.DEFAULT_TYPE, status_message: Message, video_filepath: str, user_id: int, update_id: int) -> Optional[InlineKeyboardMarkup]:
    """Extracts audio, recognizes song, and offers download if found."""
    logger.info("Attempting to recognize song.")
    audio_path = None
    try:
        audio_path = os.path.join(DOWNLOAD_PATH, f"{user_id}_{update_id}_audio.mp3")
        await _run_ffmpeg_async(functools.partial(ffmpeg.input(video_filepath).output(audio_path, acodec='libmp3lame', ar='16000').run, overwrite_output=True, quiet=True))

        shazam = Shazam()
        recognition_result = await shazam.recognize(audio_path)

        if recognition_result and recognition_result.get('track'):
            track_info = recognition_result['track']
            title = track_info.get('title', 'Noma\'lum')
            artist = track_info.get('subtitle', 'Noma\'lum')
            full_title = f"{artist} - {title}"
            youtube_url = track_info.get('sections', [{}])[0].get('youtubeurl')

            logger.info(f"Song recognized: {full_title}")
            await status_message.edit_text(f"🎶 Qo'shiq topildi: <b>{html.escape(full_title)}</b>", parse_mode='HTML')

            song_id = str(uuid.uuid4())
            context.bot_data[song_id] = {
                'full_title': full_title,
                'youtube_url': youtube_url
            }

            keyboard = [[InlineKeyboardButton("🎵 Yuklab olish (Audio)", callback_data=f"dl_song_{song_id}")]]
            return InlineKeyboardMarkup(keyboard)
        else:
            logger.info("No song found in the video.")
            await status_message.edit_text("✅ Video yuborildi. Unda musiqa topilmadi.")
            return None

    except ffmpeg.Error as e:
        logger.error(f"ffmpeg error during song recognition: {e.stderr.decode() if e.stderr else e}")
        await status_message.edit_text("Audioni ajratib olishda xatolik.")
        return None
    except Exception as e:
        logger.error(f"Error recognizing song: {e}", exc_info=True)
        await status_message.edit_text("Qo'shiqni aniqlashda kutilmagan xatolik.")
        return None
    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
