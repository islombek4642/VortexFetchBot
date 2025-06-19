import os
import html
import uuid
import ffmpeg
import asyncio
import functools
import math
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants, Message, error as telegram_error
from telegram.ext import ContextTypes
from shazamio import Shazam
from urllib.parse import urlparse, parse_qs
from youtubesearchpython import VideosSearch

from config import settings, logger
from utils.decorators import register_user
from utils.helpers import find_first_file, _run_yt_dlp_with_progress, _run_ffmpeg_async
from transcriber_whisper import transcribe_whisper_sync, transcribe_whisper_stream, transcribe_whisper_full
from database import db


# --- Command Handlers ---

@register_user
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Assalomu alaykum, {user.mention_html()}! Botimizga xush kelibsiz!",
        reply_markup=None,
    )

@register_user
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a detailed help message with all available commands and features."""
    help_text = """
👋 <b>Salom! Men VortexFetch Botiman.</b>

Sizga video yuklash, qo'shiqni aniqlash va ovozni matnga o'girishda yordam beraman.

1️⃣ <b>Video Yuklash:</b>
   - TikTok, Instagram, YouTube kabi platformalardan video havolasini yuboring.
   - Men videoni yuklab, sizga yuboraman.

2️⃣ <b>Qo'shiqni Aniqlash:</b>
   - Video yuborganingizda, agar unda musiqa bo'lsa, uni avtomatik tarzda aniqlayman.
   - Qo'shiqni audio formatda yuklab olishingiz uchun tugma yuboraman.

3️⃣ <b>Ovozni Matnga O'girish (Transkripsiya):</b>
   - Menga audio, video yoki ovozli xabar yuboring.
   - Men uni tahlil qilib, matn shaklida qaytaraman.

<b>Asosiy Buyruqlar:</b>
• /start - Botni qayta ishga tushirish
• /help - Yordam menyusini ko'rsatish

Savol va takliflar bo'lsa, bemalol murojaat qiling! 😊
"""
    await update.message.reply_text(help_text, parse_mode='HTML')

@register_user
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays bot usage statistics. Admin-only command."""
    user = update.effective_user
    if not user or user.id != settings.ADMIN_ID:
        await update.message.reply_text("Bu buyruq faqat administrator uchun mavjud.")
        logger.warning(f"Unauthorized stats access attempt by user {user.id if user else 'Unknown'}.")
        return

    try:
        message_text, reply_markup = await _generate_stats_message_and_keyboard(page=0)
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Failed to generate stats: {e}", exc_info=True)
        await update.message.reply_text("Statistikani ko'rsatishda xatolik yuz berdi.")

# --- Message Handlers ---

@register_user
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming text messages, routing to video downloader if it's a link."""
    if update.message and update.message.text:
        url = update.message.text
        if url.startswith('http://') or url.startswith('https://'):
            await _download_video_from_url(url, update, context)
        else:
            await update.message.reply_text(
                "Iltimos, video yuklash uchun to'g'ri havolani (URL) yuboring yoki ovozni matnga o'girish uchun media fayl yuboring."
            )

@register_user
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles audio, video, and voice messages for transcription."""
    await _transcribe_media(update, context)

# --- Helper Functions (Business Logic) ---

async def search_youtube_link(query: str):
    try:
        videos_search = VideosSearch(query, limit=3)
        result = await asyncio.to_thread(videos_search.next)
        if result and result.get('result'):
            # Try to find the most relevant result
            for video in result['result']:
                title = video.get('title', '').lower()
                channel = video.get('channel', {}).get('name', '').lower()
                if any(word in title for word in ['official', 'audio', 'topic']) or any(word in channel for word in ['official', 'audio', 'topic']):
                    return video['link']
            # If no good match, return the first result
            return result['result'][0]['link']
    except Exception as e:
        logger.error(f"YouTube search failed: {e}")
    return None


async def _download_video_from_url(url: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Core logic to download a video from a given URL."""
    user_id = update.message.from_user.id
    status_message = await update.message.reply_text("Yuklanmoqda...")
    video_path = None
    try:
        output_template = os.path.join(settings.DOWNLOAD_PATH, f'{user_id}_{update.message.message_id}_%(title)s.%(ext)s')
        command = [
            'yt-dlp',
            # Let yt-dlp choose the best quality by not specifying format
            '--max-filesize', '1.8G',
            '--merge-output-format', 'mp4',  # Ensure final output is mp4
            '-o', output_template, url
        ]

        # Instagram cookies
        if 'instagram.com' in url and settings.INSTAGRAM_COOKIE_FILE and os.path.exists(settings.INSTAGRAM_COOKIE_FILE):
            command.extend(['--cookies', settings.INSTAGRAM_COOKIE_FILE])
            logger.info(f"Using Instagram cookie file: {settings.INSTAGRAM_COOKIE_FILE}")

        # YouTube cookies
        elif ('youtube.com' in url or 'youtu.be' in url) and settings.YOUTUBE_COOKIE_FILE and os.path.exists(settings.YOUTUBE_COOKIE_FILE):
            command.extend(['--cookies', settings.YOUTUBE_COOKIE_FILE])
            logger.info(f"Using YouTube cookie file: {settings.YOUTUBE_COOKIE_FILE}")

        return_code, stdout, stderr = await _run_yt_dlp_with_progress(command, status_message, "Yuklanmoqda...")

        # First, check if yt-dlp reported an error
        if return_code != 0:
            error_message = stderr or stdout or "Noma'lum xato"
            # Try to extract a title from the URL if clean_caption is not available
            try:
                # Try to extract from the URL (for YouTube links)
                parsed_url = urlparse(url)
                if 'youtube.com' in url or 'youtu.be' in url:
                    qs = parse_qs(parsed_url.query)
                    video_title = qs.get('v', [os.path.basename(parsed_url.path)])[0]
                else:
                    video_title = os.path.basename(parsed_url.path)
            except Exception:
                video_title = url

            if "Sign in to confirm" in error_message or "Signature extraction failed" in error_message:
                error_text = (
                    f"❌ <b>{html.escape(video_title)}</b> videoni yuklab bo'lmadi. "
                    "YouTube bu faylni faqat ro'yxatdan o'tgan foydalanuvchilarga ko'rsatmoqda yoki himoya o'rnatilgan."
                )
            else:
                error_text = (
                    f"❌ <b>{html.escape(video_title)}</b> videoni yuklab bo'lmadi.\n"
                    f"Sabab: {html.escape(error_message[:1000])}"
                )
            await status_message.edit_text(error_text, parse_mode='HTML')
            return

        # After download, find the file using the correct prefix
        file_prefix = f"{user_id}_{update.message.message_id}"
        video_path = find_first_file(settings.DOWNLOAD_PATH, file_prefix)

        # Check if a file was actually downloaded
        if not video_path:
            logger.error(f"File not found after download for {url}, despite yt-dlp exiting with code 0.")
            logger.error(f"yt-dlp stdout: {stdout}")
            logger.error(f"yt-dlp stderr: {stderr}")
            await status_message.edit_text(
                "❌ Xatolik: Video fayl topilmadi. Bu shaxsiy (private) video bo'lishi, "
                "havola noto'g'ri bo'lishi yoki cookie faylingiz eskirgan bo'lishi mumkin."
            )
            return

        logger.info(f"Downloaded to: {video_path}")

        await status_message.edit_text("✅ Video muvaffaqiyatli yuklandi!")

        # --- Recognize Song ---
        inline_markup = await _recognize_and_offer_song_download(context, status_message, video_path, user_id, update.update_id)

        # --- Send Video to User ---
        await status_message.edit_text("Video yuborilmoqda...")
        clean_caption = ' '.join(os.path.basename(video_path).split('_')[2:])
        
        # Retry logic for Telegram API timeout
        max_retries = 3
        retry_delay = 2  # seconds
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                with open(video_path, 'rb') as video_file:
                    # Use read() to get file object instead of passing path directly
                    await update.message.reply_video(
                        video=video_file,
                        caption=clean_caption,
                        reply_markup=inline_markup,
                        read_timeout=300,  # 5 minutes timeout for large files
                        write_timeout=300,
                        connect_timeout=60,
                        pool_timeout=60
                    )
                break  # Success, break out of retry loop
            except telegram_error.TimedOut as e:
                last_exception = e
                if attempt == max_retries - 1:
                    logger.error(f"Failed to upload video after {max_retries} attempts")
                    await status_message.edit_text("❌ Xatolik: Video hajmi juda katta yoki internet tezligi sekin.")
                    return
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                logger.warning(f"Upload attempt {attempt + 1} failed, retrying...")
            except Exception as e:
                logger.error(f"Unexpected error during video upload: {e}", exc_info=True)
                await status_message.edit_text("❌ Xatolik: Videoni yuklashda kutilmagan xato yuz berdi.")
                return

        if not inline_markup:
            await status_message.edit_text("✅ Video yuborildi. Unda musiqa topilmadi.")
        else:
            await status_message.delete()

    except Exception as e:
        logger.error(f"Unexpected error during video download: {e}", exc_info=True)
        await status_message.edit_text("Kechirasiz, kutilmagan xatolik yuz berdi.")
    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)

async def _recognize_and_offer_song_download(
    context: ContextTypes.DEFAULT_TYPE,
    status_message: Message,
    video_filepath: str,
    user_id: int,
    update_id: int
) -> InlineKeyboardMarkup | None:
    """Extracts audio, recognizes a song, and offers a download if found."""
    logger.info("Recognizing song...")
    audio_path = None
    try:
        # Audio ajratiladi
        audio_path = os.path.join(settings.DOWNLOAD_PATH, f"{user_id}_{update_id}_shazam.wav")
        # Try stereo and higher bitrate for better Shazam results
        await _run_ffmpeg_async(functools.partial(
            ffmpeg.input(video_filepath).output(
                audio_path,
                format='wav',
                acodec='pcm_s16le',
                ac=2,  # stereo
                ar='44100',
                audio_bitrate='192k'
            ).run,
            overwrite_output=True, quiet=True
        ))
        logger.info(f"Audio extracted for Shazam: {audio_path}")
        # Send the extracted audio to the user for debugging
        try:
            with open(audio_path, 'rb') as audio_file:
                await status_message.reply_audio(audio=audio_file, caption="Ajratilgan audio (Shazam uchun)")
        except Exception as e:
            logger.warning(f"Could not send extracted audio: {e}")

        # Shazam yordamida aniqlash
        shazam = Shazam()
        try:
            recognition_result = await asyncio.wait_for(shazam.recognize(audio_path), timeout=45.0)
        except Exception as e:
            logger.error(f"Shazam recognize error: {e}")
            await status_message.edit_text("Shazam aniqlashda xatolik yoki timeout. Ajratilgan audio fayl downloads/ papkasida saqlanadi.")
            return None

        track_info = recognition_result.get('track')
        if not track_info:
            await status_message.edit_text("Qo'shiq topilmadi. Ajratilgan audio fayl downloads/ papkasida saqlanadi.")
            logger.warning(f"No track found by Shazam for {audio_path}")
            # Do not delete the audio file for debugging
            return None

        # Youtube URL olish (Shazamdan yoki qidiruvdan)
        youtube_url = next((
            section.get('youtubeurl')
            for section in track_info.get('sections', [])
            if section.get('youtubeurl')
        ), None)

        # Professional message logic
        subtitle = track_info.get('subtitle', "Noma'lum")
        title = track_info.get('title', "Noma'lum")
        full_title = f"{subtitle} - {title}"
        youtube_source = None

        if youtube_url:
            youtube_source = "Shazam orqali topildi"
        else:
            logger.info(f"Shazam'dan YouTube havolasi topilmadi. '{full_title}' uchun YouTube'da qidirilmoqda...")
            youtube_url = await search_youtube_link(full_title)
            if youtube_url:
                youtube_source = "YouTube qidiruvi orqali topildi"

        logger.info(f"Song recognized: {full_title}")
        if youtube_url:
            await status_message.edit_text(
                f"🎶 Qo'shiq topildi: <b>{html.escape(full_title)}</b>\n<i>{youtube_source}</i>", parse_mode='HTML'
            )
            song_id = str(uuid.uuid4())
            context.bot_data[song_id] = {
                'full_title': full_title,
                'youtube_url': youtube_url
            }
            return InlineKeyboardMarkup([[ 
                InlineKeyboardButton("🎵 Yuklab olish (Audio)", callback_data=f"dl_song_{song_id}")
            ]])
        else:
            logger.warning(f"'{full_title}' uchun YouTube'dan havola topilmadi.")
            await status_message.reply_text(
                f"<b>{html.escape(full_title)}</b> aniqlandi, ammo yuklab olish uchun mos havola topilmadi.",
                parse_mode='HTML'
            )
            return None

    except ffmpeg.Error as e:
        logger.error(f"ffmpeg error: {e.stderr.decode() if e.stderr else e}")
        await status_message.edit_text("Audioni ajratib olishda xatolik.")
    except asyncio.TimeoutError:
        logger.warning(f"Shazam recognition timed out for {video_filepath}")
        await status_message.edit_text("Qo'shiqni aniqlash vaqti tugadi.")
    except Exception as e:
        logger.error(f"Error recognizing song: {e}", exc_info=True)
        await status_message.edit_text("Qo'shiqni aniqlashda xatolik.")
    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
    return None


async def _transcribe_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Core logic to transcribe a media file using Whisper only, with language auto-detection and chunking."""
    message = update.message
    user_id = message.from_user.id
    file_to_download = message.audio or message.video or message.voice

    if not file_to_download:
        await message.reply_text("Transkripsiya uchun media fayl topilmadi.")
        return

    status_message = await message.reply_text("Fayl qabul qilindi. Whisper modelida tahlil qilinmoqda...")
    downloaded_file_path, output_audio_path = None, None
    try:
        file_id = file_to_download.file_id
        file = await context.bot.get_file(file_id)
        original_filename = getattr(file_to_download, 'file_name', f'{file_id}.ogg')
        downloaded_file_path = os.path.join(settings.DOWNLOAD_PATH, f"{user_id}_{file_id}_{original_filename}")
        await file.download_to_drive(downloaded_file_path)
        logger.info(f"File downloaded for transcription: {downloaded_file_path}")

        audio_path_to_transcribe = downloaded_file_path
        if message.video:
            await status_message.edit_text("Videodan audio ajratib olinmoqda...")
            output_audio_path = os.path.join(settings.DOWNLOAD_PATH, f"{user_id}_{file_id}_extracted.mp3")
            await _run_ffmpeg_async(functools.partial(
                ffmpeg.input(downloaded_file_path).output(output_audio_path, acodec='libmp3lame', ar='16000').run,
                overwrite_output=True, quiet=True
            ))
            audio_path_to_transcribe = output_audio_path

        await status_message.edit_text("Audio tahlil qilinmoqda (Whisper)...")
        loop = asyncio.get_event_loop()
        transcript, detected_lang = await loop.run_in_executor(None, transcribe_whisper_full, audio_path_to_transcribe)
        if transcript and transcript.strip():
            lang_text = f"\U0001F310 Aniqlangan til: <b>{detected_lang}</b>\n"
            chunks = [transcript[i:i+4096] for i in range(0, len(transcript), 4096)]
            await status_message.edit_text(lang_text + "\u2705 <b>Transkripsiya yakunlandi!</b>\n---\n" + chunks[0], parse_mode='HTML')
            for chunk in chunks[1:]:
                await update.message.reply_text(chunk, parse_mode='HTML')
        else:
            await status_message.edit_text("\u274C Transkripsiya natijasi topilmadi.")
    except ffmpeg.Error as e:
        error_details = e.stderr.decode() if e.stderr else "Noma'lum xato"
        logger.error(f"ffmpeg error during audio extraction: {error_details}")
        await status_message.edit_text(f"Videodan audioni ajratib olishda xatolik: {error_details[:100]}")
    except Exception as e:
        logger.error(f"Error in transcription process: {e}", exc_info=True)
        await status_message.edit_text("Faylni qayta ishlashda kutilmagan xatolik.")
    finally:
        for path in [downloaded_file_path, output_audio_path]:
            if path and os.path.exists(path):
                os.remove(path)

STATS_PAGE_LIMIT = 10

async def _generate_stats_message_and_keyboard(page: int) -> tuple[str, InlineKeyboardMarkup | None]:
    """Generates the statistics message and pagination keyboard for a given page."""
    total_users = db.get_total_user_count()
    if total_users == 0:
        return "Foydalanuvchilar hali mavjud emas.", None

    users = db.get_users_paginated(page=page + 1, limit=STATS_PAGE_LIMIT)
    if not users:
        return "Bu sahifada foydalanuvchilar topilmadi.", None

    message_text = f"📊 <b>Bot Statistikasi</b> 📊\n\nJami foydalanuvchilar: <b>{total_users}</b>\n\n"
    message_text += "<b>Oxirgi kirgan foydalanuvchilar:</b>\n"
    for user in users:
        display_name = user['first_name'] or user['username'] or str(user['user_id'])
        last_seen = user['last_seen']
        message_text += f"- <a href='tg://user?id={user['user_id']}'>{display_name}</a> (So'nggi faollik: {last_seen})\n"

    total_pages = math.ceil(total_users / STATS_PAGE_LIMIT)
    message_text += f"\nSahifa: {page + 1}/{total_pages}"

    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"stats_page_{page - 1}"))
    if page < total_pages - 1:
        navigation_buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"stats_page_{page + 1}"))

    keyboard = [navigation_buttons] if navigation_buttons else None
    return message_text, InlineKeyboardMarkup(keyboard) if keyboard else None
