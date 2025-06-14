# Telegram Video Downloader Bot

import logging
import os
import re
import time
import asyncio
import pathlib # For creating file URIs
from typing import Optional
from dotenv import load_dotenv # Added for .env support
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message
from shazamio import Shazam # For song recognition
import ffmpeg # For audio extraction
import functools # To use functools.partial
from transcriber import transcribe_audio_from_file # Import our new function

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Get Telegram Bot Token from environment variable
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
    # You should exit or raise an error here if the token is critical for startup

# Create download directory if it doesn't exist
DOWNLOAD_PATH = 'downloads'
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# Load YouTube cookies from environment variable and write to a file
COOKIE_FILE_PATH = "cookies.txt"

YOUTUBE_COOKIES = os.getenv('YOUTUBE_COOKIES')
if YOUTUBE_COOKIES:
    try:
        with open(COOKIE_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(YOUTUBE_COOKIES)
        logger.info("YouTube cookie fayli muhit o'zgaruvchisidan muvaffaqiyatli yaratildi.")
    except Exception as e:
        logger.error(f"Cookie faylini yozishda xatolik: {e}")
else:
    logger.warning("YOUTUBE_COOKIES muhit o'zgaruvchisi o'rnatilmagan. Yuklashlarda muammo bo'lishi mumkin.")
    # For now, we'll let it proceed but the bot won't work.

DOWNLOAD_PATH = 'downloads'

def find_first_file(directory: str, prefix: str) -> Optional[str]:
    """Finds the first file in a directory that starts with a given prefix."""
    try:
        for f in os.listdir(directory):
            if f.startswith(prefix):
                return os.path.join(directory, f)
    except FileNotFoundError:
        logger.error(f"Directory not found for searching prefix '{prefix}': {directory}")
    return None


async def _run_yt_dlp_with_progress(command: list, status_message: Message, progress_text_prefix: str):
    """Runs a yt-dlp command, captures its output, and reports progress by editing a Telegram message."""
    logger.debug(f"Running command: {' '.join(command)}")
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    last_update_time = time.time()
    last_percentage = -1

    while process.returncode is None:
        try:
            line = await asyncio.wait_for(process.stdout.readline(), timeout=1.0)
            if not line:
                await asyncio.sleep(0.1)
                continue
            
            output = line.decode('utf-8', errors='ignore').strip()
            logger.debug(f"yt-dlp stdout: {output}")
            
            match = re.search(r"\[download\]\s+([0-9\.]+)%", output)
            if match:
                try:
                    percentage = int(float(match.group(1)))
                    current_time = time.time()
                    
                    if percentage > last_percentage and (percentage % 5 == 0 or current_time - last_update_time > 2):
                        await status_message.edit_text(f"{progress_text_prefix} {percentage}%")
                        last_percentage = percentage
                        last_update_time = current_time
                except (ValueError, IndexError):
                    pass # Ignore parsing errors
                except Exception as e:
                    logger.warning(f"Could not edit progress message: {e}")

        except asyncio.TimeoutError:
            pass # No output, just check process status again
        
        if process.returncode is not None:
            break
    
    stderr_bytes = await process.stderr.read()
    return process.returncode, stderr_bytes.decode('utf-8', errors='ignore')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start komandasi yuborilganda xush kelibsiz xabarini yuboradi."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Salom {user.mention_html()}! Menga video havolasini yuboring va men uni siz uchun yuklab beraman.",
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help komandasi yuborilganda yordam xabarini yuboradi."""
    await update.message.reply_text(
        "Menga qo'llab-quvvatlanadigan platformalardan (masalan, YouTube, Instagram, TikTok, va boshqalar) "
        "video havolasini yuboring, men uni yuklab, sizga yuboraman.\n\n"
        "Yuklab olish uchun yt-dlp kutubxonasidan foydalaniladi. "
        "Katta hajmli videolar yuklab olinmaganligi yoki vaqt talab qilishi mumkin."
    )

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Downloads video from the URL sent by the user."""
    user_id = update.message.from_user.id
    video_path = None
    process = None
    url = update.message.text
    chat_id = update.message.chat_id

    status_message = await update.message.reply_text("So'rovingiz qayta ishlanmoqda... Iltimos kuting.")

    if not url or not (url.startswith('http://') or url.startswith('https://')):
        await status_message.edit_text("Iltimos, to'g'ri video havolasini yuboring.")
        return

    # Make filename unique to this user and request to avoid conflicts
    output_template = os.path.join(DOWNLOAD_PATH, f'{user_id}_{update.update_id}_%(title)s.%(ext)s')
    command = [
        'yt-dlp',
        '-f', 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best',
        '--merge-output-format', 'mp4',
        '-o', output_template,
        '--max-filesize', '49m', # Telegram bot API limit is 50MB for sending files
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
            if "Unsupported URL" in stderr_output:
                await status_message.edit_text("❌ Noto'g'ri yoki qo'llab-quvvatlanmaydigan havola.")
            elif "Video unavailable" in stderr_output:
                await status_message.edit_text("❌ Video mavjud emas.")
            elif "File is larger than the maximum" in stderr_output:
                await status_message.edit_text("❌ Video hajmi 50MB dan katta, yuklab bo'lmadi.")
            else:
                await status_message.edit_text("❌ Videoni yuklashda xatolik yuz berdi.")
            return

        # Find the downloaded file
        # yt-dlp might slightly alter the filename (e.g., if title has special chars)
        # We need to find the actual downloaded file.
        # A simple way is to list files in DOWNLOAD_PATH and pick the newest one or one matching the title pattern.
        # For simplicity, let's assume yt-dlp outputs a predictable name or we can parse stdout.
        
        # A more robust way to get the filename is to use --print filename with yt-dlp
        # but that requires another call or more complex parsing.
        # Let's try to find the file based on the output template structure.
        
        # Find the downloaded file using the helper function
        video_path = find_first_file(DOWNLOAD_PATH, f'{user_id}_{update.update_id}_')
        
        if not video_path:
            logger.error(f"yt-dlp finished but no file found for URL: {url} with prefix {user_id}_{update.update_id}_")
            logger.error(f"yt-dlp stderr: {stderr_output}")
            await status_message.edit_text("❌ Videoni yuklab olishning iloji bo'lmadi yoki fayl topilmadi.")
            return
        
        logger.info(f"Successfully downloaded video to: {video_path}")
        await status_message.edit_text("Yuklab olish yakunlandi! Musiqa aniqlanmoqda...")

        # Perform song recognition directly and wait for the result.
        # Pass the status_message for it to edit.
        inline_markup_for_video = await recognize_and_offer_song_download(status_message, video_path, user_id, update.update_id)

        # The recognition function will handle its own status updates.
        # Now, send the video with the resulting keyboard.
        logger.info(f"Sending video {video_path} with caption '{os.path.basename(video_path)}' and reply_markup: {inline_markup_for_video is not None}")
        with open(video_path, 'rb') as video_file:
            # We send the video as a reply to the original user message
            # Extract a clean caption from the filename, removing the user/update IDs
            filename_parts = os.path.basename(video_path).split('_')
            # The original title might contain underscores, so we join all parts after the IDs
            clean_caption = " ".join(filename_parts[2:])

            await update.message.reply_video(
                video=video_file,
                caption=clean_caption,
                reply_markup=inline_markup_for_video # This will have the button if a song was found
            )
        
        # Delete the status message as we are done with the main flow.
        # The recognition function might have edited it to show the final status.
        await status_message.delete()
        logger.info(f"Successfully sent video and cleaned up status message for: {video_path}")

    except asyncio.CancelledError:
        logger.warning("Yuklash bekor qilindi.")
        if process:
            process.kill()
        await status_message.edit_text("Yuklash bekor qilindi.")
    except Exception as e:
        logger.error(f"Video yuklash jarayonida kutilmagan xatolik: {e}", exc_info=True)
        await status_message.edit_text("Kechirasiz, videoni yuklashda kutilmagan xatolik yuz berdi.")
    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)


async def _run_ffmpeg_async(func):
    """Runs a blocking ffmpeg function in a separate thread to avoid blocking the asyncio event loop."""
    loop = asyncio.get_running_loop()
    # Use functools.partial to pass the function and its arguments
    return await loop.run_in_executor(None, func)

async def recognize_and_offer_song_download(status_message: Message, video_filepath: str, user_id: int, update_id: int) -> Optional[InlineKeyboardMarkup]:
    """Extracts audio, recognizes song, and offers download if found. Edits the provided status message."""
    logger.info("Attempting to recognize song.")
    audio_extraction_path = os.path.join(DOWNLOAD_PATH, f"{user_id}_{update_id}_extracted_audio.m4a")
    
    try:
        await status_message.edit_text("🎶 Videodan audio ajratib olinmoqda...")
        logger.info(f"Extracting audio from {video_filepath} to {audio_extraction_path}.")
        
        stream = ffmpeg.input(video_filepath)
        stream = ffmpeg.output(stream, audio_extraction_path, acodec='aac', ar='44100', ab='192k')
        await _run_ffmpeg_async(functools.partial(stream.run, overwrite_output=True, quiet=True))

        logger.info(f"Audio extracted successfully to {audio_extraction_path}")

        await status_message.edit_text("🎤 Shazam yordamida musiqa aniqlanmoqda...")
        shazam = Shazam()
        recognition_result = await shazam.recognize(audio_extraction_path)
        
        if recognition_result and recognition_result.get('track'):
            track_info = recognition_result['track']
            song_title = track_info.get('title', 'Noma\'lum nom')
            song_artist = track_info.get('subtitle', 'Noma\'lum ijrochi')
            logger.info(f"Shazam found a match: {song_artist} - {song_title}")

            song_details_payload = f"{song_title} - {song_artist}"
            keyboard = [
                [InlineKeyboardButton(f"🎵 Yuklash: {song_artist} - {song_title}", callback_data=f'download_song|{song_details_payload}')]
            ]
            return InlineKeyboardMarkup(keyboard)
        else:
            logger.warning("Shazam could not identify the song.")
            await status_message.edit_text("Afsuski, bu videodagi musiqani aniqlab bo'lmadi.")
            return None

    except ffmpeg.Error as e:
        error_details = e.stderr.decode('utf-8', errors='ignore') if e.stderr else "No details"
        logger.error(f"ffmpeg error during audio extraction: {error_details}")
        await status_message.edit_text("❌ Audio ajratib olishda xatolik.")
        return None
    except Exception as e:
        logger.error(f"Error in recognize_and_offer_song_download: {e}", exc_info=True)
        await status_message.edit_text("❌ Musiqani aniqlashda kutilmagan xatolik.")
        return None
    finally:
        if os.path.exists(audio_extraction_path):
            os.remove(audio_extraction_path)


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles button clicks for downloading songs."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    song_audio_path = None

    try:
        action, song_details_payload = query.data.split('|', 1)
        
        if action == 'download_song':
            song_title, song_artist = song_details_payload.split(' - ', 1)
            search_query = f"{song_artist} - {song_title}"
            
            status_message = await context.bot.send_message(chat_id=query.message.chat_id, text=f"'{search_query}' yuklanmoqda... 0%")
            
            # Use query.id for a unique ID in callbacks
            song_output_template = os.path.join(DOWNLOAD_PATH, f'{user_id}_{query.id}_%(title)s_audio.%(ext)s')
            
            song_download_command = [
                'yt-dlp',
                '--extract-audio', '--audio-format', 'mp3', '--audio-quality', '0',
                '--output', song_output_template,
                '--max-filesize', '20m',
                f'ytsearch1:{search_query}'
            ]
            if YOUTUBE_COOKIES:
                song_download_command.extend(['--cookies', COOKIE_FILE_PATH])

            return_code, stderr_output = await _run_yt_dlp_with_progress(song_download_command, status_message, f"'{search_query}' yuklanmoqda...")

            if return_code == 0:
                song_audio_path = find_first_file(DOWNLOAD_PATH, f'{user_id}_{query.id}_')
                
                if song_audio_path:
                    try:
                        with open(song_audio_path, 'rb') as audio_file:
                            await context.bot.send_audio(
                                chat_id=query.message.chat_id,
                                audio=audio_file,
                                title=song_title,
                                performer=song_artist,
                                filename=f"{song_artist} - {song_title}.mp3"
                            )
                        await status_message.delete()
                    except Exception as e:
                        logger.error(f"Error sending downloaded song: {e}")
                        await status_message.edit_text("Yuklab olingan qo'shiqni yuborishda xatolik yuz berdi.")
                else:
                    logger.error("Song downloaded but file not found.")
                    await status_message.edit_text("Qo'shiq yuklandi, lekin faylni topishda muammo bo'ldi.")
            else:
                logger.error(f"Song download failed (yt-dlp): {stderr_output}")
                await status_message.edit_text("Afsuski, qo'shiqni yuklab bo'lmadi. Boshqa manba bilan harakat qilib ko'ring.")

    except Exception as e:
        logger.error(f"Tugma bosishni qayta ishlashda xatolik: {e}", exc_info=True)
        try:
            await query.message.reply_text("Kechirasiz, so'rovingizni qayta ishlashda kutilmagan xatolik yuz berdi.")
        except Exception as reply_e:
            logger.error(f"Xatolik haqida xabar yuborishda xatolik: {reply_e}")
    finally:
        if song_audio_path and os.path.exists(song_audio_path):
            os.remove(song_audio_path)


# --- Transcriber Functionality ---

async def handle_media_for_transcription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles audio and video messages for transcription."""
    message = update.message
    user_id = message.from_user.id
    file_to_download = message.audio or message.video or message.voice
    downloaded_file_path = None
    output_audio_path = None

    if not file_to_download:
        return

    status_message = await message.reply_text(
        "Fayl qabul qilindi. Ovozni matnga o'girish uchun tayyorlanmoqda..."
    )

    try:
        file_id = file_to_download.file_id
        file = await context.bot.get_file(file_id)
        
        # Create a unique filename to avoid conflicts
        original_filename = file_to_download.file_name or 'media.bin'
        downloaded_file_path = os.path.join(DOWNLOAD_PATH, f"{user_id}_{file_id}_{original_filename}")
        await file.download_to_drive(downloaded_file_path)
        logger.info(f"File downloaded for transcription: {downloaded_file_path}")

        audio_path_to_transcribe = downloaded_file_path

        # If it's a video, extract audio
        if message.video:
            await status_message.edit_text("Videodan audio ajratib olinmoqda...")
            output_audio_path = os.path.join(DOWNLOAD_PATH, f"{user_id}_{file_id}_extracted_audio.mp3")
            try:
                # Run ffmpeg non-blocking
                await _run_ffmpeg_async(functools.partial(ffmpeg.input(downloaded_file_path).output(output_audio_path, acodec='libmp3lame', ar='16000').run, overwrite_output=True, quiet=True))
                audio_path_to_transcribe = output_audio_path
                logger.info(f"Audio extracted successfully: {output_audio_path}")
            except ffmpeg.Error as e:
                error_details = e.stderr.decode() if e.stderr else "Unknown error"
                logger.error(f"ffmpeg error: {error_details}")
                await status_message.edit_text("Videodan audioni ajratib olishda xatolik yuz berdi.")
                return

        # Transcribe the audio
        await status_message.edit_text("Audio tahlil qilinmoqda... Bu bir necha daqiqa vaqt olishi mumkin.")
        language, transcript = await transcribe_audio_from_file(audio_path_to_transcribe)

        if transcript and language:
            header = f"✅ Transkripsiya muvaffaqiyatli yakunlandi!\n\n**Aniqlangan til:** `{language.upper()}`\n---\n"
            await status_message.edit_text(header + transcript, parse_mode='Markdown')
        else:
            await status_message.edit_text(transcript or "Noma'lum xatolik yuz berdi.")

    except Exception as e:
        logger.error(f"General error in transcription process: {e}", exc_info=True)
        await status_message.edit_text("Kechirasiz, faylni qayta ishlashda kutilmagan xatolik yuz berdi.")
    finally:
        # Clean up temporary files
        if downloaded_file_path and os.path.exists(downloaded_file_path):
            os.remove(downloaded_file_path)
        if output_audio_path and os.path.exists(output_audio_path):
            os.remove(output_audio_path)


def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = ApplicationBuilder().token(TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # on non command i.e message - download the video from the message.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))

    # Add a handler for button clicks (for downloading songs)
    application.add_handler(CallbackQueryHandler(button_callback_handler))

    # Yangi transkripsiya funksiyasi uchun handler
    application.add_handler(MessageHandler(filters.AUDIO | filters.VIDEO | filters.VOICE, handle_media_for_transcription))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == '__main__':
    main()
