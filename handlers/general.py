import os
import html
import uuid
import ffmpeg
import asyncio
import functools
import math
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants, Message
from telegram.ext import ContextTypes
from shazamio import Shazam

from config import settings, logger
from utils.decorators import register_user
from utils.helpers import find_first_file, _run_yt_dlp_with_progress, _run_ffmpeg_async
from transcriber import transcribe_audio_from_file
from database import db

from youtubesearchpython import VideosSearch


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

async def search_youtube_link(query: str) -> str | None:
    """YouTube'dan qo‘shiq nomi bo‘yicha birinchi videoni qidiradi."""
    try:
        videos_search = VideosSearch(query, limit=1)
        result = await videos_search.next()
        if result['result']:
            return result['result'][0]['link']
    except Exception as e:
        logger.error(f"YouTube qidiruvda xatolik: {e}", exc_info=True)
    return None


async def _download_video_from_url(url: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Core logic to download a video from a given URL."""
    user_id = update.message.from_user.id
    video_path = None
    status_message = await update.message.reply_text("So'rovingiz qayta ishlanmoqda...")

    output_template = os.path.join(settings.DOWNLOAD_PATH, f'{user_id}_{update.update_id}_%(title)s.%(ext)s')
    command = [
        'yt-dlp',
        '-f', 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best',
        '--merge-output-format', 'mp4',
        '-o', output_template,
        '--max-filesize', '49m',
    ]
    if settings.YOUTUBE_COOKIES:
        command.extend(['--cookies', settings.COOKIE_FILE_PATH])
    command.append(url)

    try:
        logger.info(f"Downloading: {url}")
        await status_message.edit_text("Yuklanmoqda... 0%")
        return_code, stderr = await _run_yt_dlp_with_progress(command, status_message, "Yuklanmoqda...")

        if return_code != 0:
            logger.error(f"yt-dlp error for {url}: {stderr}")
            error_map = {
                "Unsupported URL": "❌ Noto'g'ri yoki qo'llab-quvvatlanmaydigan havola.",
                "Video unavailable": "❌ Video mavjud emas.",
                "File is larger than the maximum": "❌ Video hajmi 50MB dan katta."
            }
            error_message = next((msg for key, msg in error_map.items() if key in stderr), "❌ Videoni yuklashda xatolik.")
            await status_message.edit_text(error_message)
            return

        video_path = find_first_file(settings.DOWNLOAD_PATH, f'{user_id}_{update.update_id}_')
        if not video_path:
            logger.error(f"File not found after download for {url}")
            await status_message.edit_text("❌ Yuklangan video fayli topilmadi.")
            return

        logger.info(f"Downloaded to: {video_path}")
        await status_message.edit_text("Musiqa aniqlanmoqda...")

        inline_markup = await _recognize_and_offer_song_download(context, status_message, video_path, user_id, update.update_id)

        clean_caption = ' '.join(os.path.basename(video_path).split('_')[2:])
        with open(video_path, 'rb') as video_file:
            await update.message.reply_video(video=video_file, caption=clean_caption, reply_markup=inline_markup)

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
        await _run_ffmpeg_async(functools.partial(
            ffmpeg.input(video_filepath).output(
                audio_path,
                format='wav',
                acodec='pcm_s16le',
                ac=1,
                ar='44100'
            ).run,
            overwrite_output=True, quiet=True
        ))

        # Shazam yordamida aniqlash
        shazam = Shazam()
        recognition_result = await asyncio.wait_for(shazam.recognize(audio_path), timeout=30.0)

        track_info = recognition_result.get('track')
        if not track_info:
            await status_message.edit_text("Qo'shiq topilmadi.")
            return None

        subtitle = track_info.get('subtitle', "Noma'lum")
        title = track_info.get('title', "Noma'lum")
        full_title = f"{subtitle} - {title}"

        # Youtube URL olish (Shazamdan yoki qidiruvdan)
        youtube_url = next((
            section.get('youtubeurl')
            for section in track_info.get('sections', [])
            if section.get('youtubeurl')
        ), None)

        # Agar Shazamdan havola topilmasa — YouTube'dan qidiriladi
        if not youtube_url:
            logger.info(f"Shazam'dan YouTube havolasi topilmadi. '{full_title}' uchun qidirilmoqda...")
            youtube_url = await search_youtube_link(full_title)

        logger.info(f"Song recognized: {full_title}")
        await status_message.edit_text(
            f"🎶 Qo'shiq topildi: <b>{html.escape(full_title)}</b>", parse_mode='HTML'
        )

        # Agar havola topilgan bo'lsa, yuklab olish tugmasi ko'rsatiladi
        if youtube_url:
            song_id = str(uuid.uuid4())
            context.bot_data[song_id] = {
                'full_title': full_title,
                'youtube_url': youtube_url
            }
            return InlineKeyboardMarkup([[
                InlineKeyboardButton("🎵 Yuklab olish (Audio)", callback_data=f"dl_song_{song_id}")
            ]])
        else:
            # Agar qidiruvdan keyin ham havola topilmasa
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
    """Core logic to transcribe a media file."""
    message = update.message
    user_id = message.from_user.id
    file_to_download = message.audio or message.video or message.voice

    if not file_to_download:
        await message.reply_text("Transkripsiya uchun media fayl topilmadi.")
        return

    status_message = await message.reply_text("Fayl qabul qilindi. Tayyorlanmoqda...")
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

        await status_message.edit_text("Audio tahlil qilinmoqda...")
        transcript = await transcribe_audio_from_file(audio_path_to_transcribe)

        if any(keyword in transcript for keyword in ["Xatolik:", "Transkripsiya vaqtida", "Matn aniqlanmadi"]):
            await status_message.edit_text(transcript)
        else:
            header = "✅ **Transkripsiya yakunlandi!**\n---\n"
            full_text = header + transcript
            if len(full_text) > 4096:
                await status_message.edit_text(header, parse_mode='Markdown')
                for i in range(0, len(transcript), 4096):
                    await message.reply_text(transcript[i:i+4096])
            else:
                await status_message.edit_text(full_text, parse_mode='Markdown')

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
