# Telegram Video Downloader Bot

import logging
import os
import subprocess
import pathlib # For creating file URIs
from typing import Optional
from dotenv import load_dotenv # Added for .env support
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from shazamio import Shazam # For song recognition
import ffmpeg # For audio extraction
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

# Load YouTube cookies from environment variable and write to a file
COOKIE_FILE_PATH = 'cookies.txt'
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
    video_path = None  # Initialize video_path
    process = None     # Initialize process
    """Downloads video from the URL sent by the user."""
    url = update.message.text
    chat_id = update.message.chat_id

    status_message = await update.message.reply_text("So'rovingiz qayta ishlanmoqda... Iltimos kuting.")

    if not url or not (url.startswith('http://') or url.startswith('https://')):
        await status_message.edit_text("Iltimos, to'g'ri video havolasini yuboring.")
        return

    # Create download directory if it doesn't exist
    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)

    # Use yt-dlp to download the video
    # We'll try to get the best quality video that's under a reasonable size limit (e.g., 50MB for Telegram)
    # The filename will be based on the video title
    # Make filename unique to this request to avoid race conditions
    output_template = os.path.join(DOWNLOAD_PATH, f'{update.update_id}_%(title)s.%(ext)s')
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
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if process.returncode == 0:
            # Find the downloaded file
            # yt-dlp might slightly alter the filename (e.g., if title has special chars)
            # We need to find the actual downloaded file.
            # A simple way is to list files in DOWNLOAD_PATH and pick the newest one or one matching the title pattern.
            # For simplicity, let's assume yt-dlp outputs a predictable name or we can parse stdout.
            
            # A more robust way to get the filename is to use --print filename with yt-dlp
            # but that requires another call or more complex parsing.
            # Let's try to find the file based on the output template structure.
            
            # Find the file that was just downloaded for this specific request
            downloaded_files = []
            request_file_prefix = str(update.update_id)
            for f in os.listdir(DOWNLOAD_PATH):
                if f.startswith(request_file_prefix) and f.endswith('.mp4'):
                    downloaded_files.append(os.path.join(DOWNLOAD_PATH, f))
            
            if not downloaded_files:
                logger.error(f"yt-dlp finished but no file found for URL: {url}")
                logger.error(f"yt-dlp stdout: {stdout.decode(errors='ignore')}")
                logger.error(f"yt-dlp stderr: {stderr.decode(errors='ignore')}")
                await update.message.reply_text("Videoni yuklab olishning iloji bo'lmadi yoki hajm chegarasiga to'g'ri keladigan format topilmadi.")
                return

            # Assuming the first (or newest) mp4 file is the one we want.
            # This part needs to be more robust for production.
            video_path = max(downloaded_files, key=os.path.getctime) # Get the newest file
            
            logger.info(f"Successfully downloaded video to: {video_path}")
            await status_message.edit_text(f"Yuklab olish yakunlandi! Video tayyorlanmoqda va musiqa tekshirilmoqda...")

            # Perform song recognition BEFORE sending video
            inline_markup_for_video: Optional[InlineKeyboardMarkup] = None
            # video_path is already confirmed to exist at this point by the outer if condition
            # recognize_and_offer_song_download will send its own "Attempting to identify..." message
            inline_markup_for_video = await recognize_and_offer_song_download(update, context, video_path)

            # Send the video
            logger.info(f"Sending video {video_path} with caption '{os.path.basename(video_path)}' and reply_markup: {inline_markup_for_video is not None}")
            with open(video_path, 'rb') as video_file:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=video_file,
                    caption=os.path.basename(video_path).split('_', 1)[-1] if '_' in os.path.basename(video_path) else os.path.basename(video_path),
                    reply_markup=inline_markup_for_video # Attach button here if available
                )
            logger.info(f"Successfully sent video: {video_path} to chat_id: {chat_id}")

        else:
            error_message = stderr.decode(errors='ignore')
            logger.error(f"yt-dlp failed for URL: {url}. Error: {error_message}")
            reply_text = f"Kechirasiz, videoni yuklab olishda xatolik yuz berdi: {error_message[:1000]}"
            if "File is larger than max-filesize" in error_message:
                reply_text = "Video juda katta hajmli (maksimal 50MB). Kichikroq videoni yuboring yoki boshqa formatda urinib ko'ring."
            elif "Unsupported URL" in error_message:
                reply_text = "Kechirasiz, berilgan havola qo'llab-quvvatlanmaydi."
            await status_message.edit_text(reply_text)

    except Exception as e:
        logger.error(f"An error occurred during video download process for {url}: {e}")
        if status_message:
            await status_message.edit_text(f"Kutilmagan xatolik yuz berdi: {e}")
        else:
            await update.message.reply_text(f"Kutilmagan xatolik yuz berdi: {e}") # Fallback if status_message not set
    finally:
        # Clean up the downloaded file
        if video_path and os.path.exists(video_path): # Check if video_path was assigned and exists
            os.remove(video_path)
            logger.info(f"Cleaned up downloaded file: {video_path}")


async def recognize_and_offer_song_download(update: Update, context: ContextTypes.DEFAULT_TYPE, video_filepath: str) -> Optional[InlineKeyboardMarkup]:
    """Extracts audio, recognizes song, and offers download if found."""
    chat_id = update.message.chat_id
    # Make filename unique to avoid race conditions
    audio_extraction_path = os.path.join(DOWNLOAD_PATH, f'{update.update_id}_extracted_audio.m4a')

    try:
        # 1. Extract audio from the video
        # Ensure input video path is absolute and converted to a file URI
        absolute_video_filepath = os.path.abspath(video_filepath)
        file_uri_for_yt_dlp = pathlib.Path(absolute_video_filepath).as_uri()
        
        # Ensure output path for audio is also absolute
        absolute_audio_extraction_path = os.path.abspath(audio_extraction_path)

        extract_command = [
            'yt-dlp',
            '--quiet',
            '--extract-audio',
            '--audio-format', 'm4a', # m4a is generally good for shazamio
            '--enable-file-urls', # Allow local file processing
            '-o', absolute_audio_extraction_path, # Use absolute path for output
            file_uri_for_yt_dlp # Use file URI for input
        ]
        logger.info(f"Extracting audio with command: {' '.join(extract_command)}")
        extract_process = subprocess.Popen(extract_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, extract_stderr = extract_process.communicate()

        if extract_process.returncode != 0:
            logger.error(f"Failed to extract audio. stderr: {extract_stderr.decode(errors='ignore')}")
            await update.message.reply_text("Musiqani aniqlash uchun audio qismini ajratib bo'lmadi.")
            return
        
        if not os.path.exists(audio_extraction_path):
            logger.error(f"Audio extraction finished but file not found: {audio_extraction_path}")
            await update.message.reply_text("Audio ajratildi, lekin audio fayli topilmadi.")
            return

        # 2. Recognize song using shazamio
        shazam = Shazam()
        # shazamio expects a path string or bytes. Let's pass the path.
        out = await shazam.recognize(audio_extraction_path)

        if os.path.exists(audio_extraction_path):
             os.remove(audio_extraction_path)
             logger.info(f"Cleaned up extracted audio file: {audio_extraction_path}")

        track_info = out.get('track')
        if track_info and track_info.get('title') and track_info.get('subtitle'):
            song_title = track_info['title']
            song_artist = track_info['subtitle']
            logger.info(f"Song recognized: {song_artist} - {song_title}")

            full_song_details = f"{song_artist} - {song_title}"

            # Truncate callback_data payload to fit within Telegram's 64-byte limit
            # "download_song|" is 14 bytes. Max length for song_details_payload is 64 - 14 - 1 (for safety buffer) = 49 bytes.
            # We'll use character length as an approximation, aiming for less than 49 characters.
            max_payload_chars = 48 # Keep it safely under the byte limit for typical characters
            song_details_payload = full_song_details[:max_payload_chars]

            final_callback_data = f"download_song|{song_details_payload}"
            logger.info(f"Creating button with callback_data: {final_callback_data} (length: {len(final_callback_data.encode('utf-8'))} bytes)")

            keyboard = [
                [InlineKeyboardButton("Qo'shiqni yuklab olish", callback_data=final_callback_data)] # Uzbek text for the button
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            return reply_markup # Return the markup to be attached to the video message
        else:
            logger.info("No song recognized by Shazam.")
            return None # No button if no song is recognized

    except Exception as e:
        logger.error(f"Error during song recognition process: {e}") # Clarified log message
        return None # No button if an error occurs during recognition
    finally:
        if os.path.exists(audio_extraction_path):
            try:
                os.remove(audio_extraction_path)
                logger.info(f"Cleaned up extracted audio file (in finally): {audio_extraction_path}")
            except Exception as e_del:
                logger.error(f"Error deleting extracted audio file: {e_del}")

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles button clicks for downloading songs."""
    query = update.callback_query
    await query.answer() # Acknowledge the button press

    try:
        action, song_details_payload = query.data.split('|', 1)
    except ValueError:
        logger.error(f"Invalid callback data format: {query.data}")
        await query.edit_message_text(text="Xato: Noto'g'ri musiqa ma'lumoti.")
        return

    if action == "download_song":
        search_query = song_details_payload # This is already truncated
        logger.info(f"Download song button clicked. Search query: {search_query}")

        # Send a new message to show that we are processing the request
        status_message = await context.bot.send_message(chat_id=query.message.chat_id, text=f"'{search_query}'ni qidiryapman va yuklab olinmoqda...")
        
        # Make filename unique to this request to avoid race conditions
        song_output_template = os.path.join(DOWNLOAD_PATH, f'{update.update_id}_%(title)s_audio.%(ext)s')
        # Use yt-dlp with 'ytsearch1:' to find and download the best audio from the first search result.
        song_download_command = [
            'yt-dlp',
            '--quiet',
            '--no-warnings',
            '--format', 'bestaudio/best', # Eng yaxshi audioni tanlash / topa olmasa eng yaxshi formatni olish
            '--extract-audio',
            '--audio-format', 'mp3',
            '--audio-quality', '0', # Best quality
            '--match-filter', 'duration < 600',  # Limit to 10 minutes
            '-o', song_output_template,
            '--max-filesize', '20m',
            '--no-playlist',
        ]
        if os.path.exists(COOKIE_FILE_PATH):
            song_download_command.extend(['--cookies', COOKIE_FILE_PATH])
        song_download_command.append(f'ytsearch1:{search_query}')

        try:
            logger.info(f"Attempting to download song: {search_query} with command: {' '.join(song_download_command)}")
            process = subprocess.Popen(song_download_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                # Find the song file that was just downloaded for this specific request
                downloaded_songs = []
                request_file_prefix = str(update.update_id)
                for f in os.listdir(DOWNLOAD_PATH):
                    if f.startswith(request_file_prefix) and f.endswith('_audio.mp3'): # Match our output template
                        downloaded_songs.append(os.path.join(DOWNLOAD_PATH, f))
                
                if not downloaded_songs:
                    logger.error(f"yt-dlp song download finished but no file found for query: {search_query}")
                    logger.error(f"Muvaffaqiyatli yuklab olingan bo'lsa-da, '{search_query}' uchun fayl topilmadi.")
                    if status_message:
                        await status_message.edit_text(text="Kechirasiz, qo'shiq yuklandi, lekin uni qayta ishlashda xatolik yuz berdi.")
                    return # Exit after handling error

                song_audio_path = downloaded_songs[0]
                logger.info(f"Found downloaded song: {song_audio_path}")

                if status_message: # Update status message
                    await status_message.edit_text(text="Qo'shiq muvaffaqiyatli yuklandi! Telegramga yuborilmoqda...")
                
                # This try-except block is for SENDING the file, not downloading.
                try:
                    with open(song_audio_path, 'rb') as audio_file:
                        file_name_without_id = os.path.basename(song_audio_path).split('_', 1)[-1] if '_' in os.path.basename(song_audio_path) else os.path.basename(song_audio_path)
                        await context.bot.send_audio(chat_id=query.message.chat_id, audio=audio_file, title=file_name_without_id.replace('_audio.mp3',''), filename=file_name_without_id)
                    logger.info(f"Successfully sent song audio: {song_audio_path} to chat_id: {query.message.chat_id}")
                    if status_message: # Delete the status message after sending audio
                        await status_message.delete()
                except Exception as e:
                    logger.error(f"Failed to send song audio {song_audio_path} to Telegram: {e}")
                    if status_message:
                        await status_message.edit_text(f"Kechirasiz, men qo'shiqni yukladim, lekin uni yuborishda xatolik yuz berdi.")
                finally:
                    if os.path.exists(song_audio_path):
                        os.remove(song_audio_path)
                        logger.info(f"Cleaned up downloaded song audio: {song_audio_path}")
            else:
                error_output = stderr.decode(errors='ignore')
                logger.error(f"yt-dlp failed for song search '{search_query}'. Error: {error_output}")
                error_text = f"Kechirasiz, '{search_query}' nomli qo'shiqni yuklab bo'lmadi. Bu manbadagi vaqtinchalik muammo bo'lishi mumkin."
                if "Requested format is not available" in error_output:
                    error_text = f"Kechirasiz, '{search_query}' uchun mos audio format topilmadi. Boshqa videoni sinab ko'ring."
                
                if status_message:
                    await status_message.edit_text(text=error_text)
                else:
                    # If status_message was not set (e.g. original message deleted or error before status_message)
                    # try to edit the callback query message, or send a new one if that fails.
                    try:
                        await query.edit_message_text(text=error_text)
                    except Exception as edit_error:
                        logger.warning(f"Could not edit callback query message: {edit_error}. Sending new message.")
                        await context.bot.send_message(chat_id=query.message.chat_id, text=error_text)

        except Exception as e:
            logger.error(f"An error occurred during song download process for {search_query}: {e}")
            if status_message:
                await status_message.edit_text(f"An unexpected error occurred while downloading the song: {e}")
            else:
                await context.bot.send_message(chat_id=query.message.chat_id, text=f"An unexpected error occurred while downloading the song: {e}")
    else:
        logger.warning(f"Unknown callback action: {action}")
        # For unknown actions, we can't rely on status_message, so send a new one or edit if possible
        try:
            await query.edit_message_text(text="Error: Unknown action.") # Try editing original if it was a text message
        except Exception:
            await context.bot.send_message(chat_id=query.message.chat_id, text="Error: Unknown action.")


# --- Transcriber Functionality ---

async def handle_media_for_transcription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles audio and video messages for transcription."""
    message = update.message
    file_to_download = message.audio or message.video or message.voice

    if not file_to_download:
        return

    status_message = await message.reply_text(
        "Fayl qabul qilindi. Ovozni matnga o'girish uchun tayyorlanmoqda..."
    )

    try:
        file_id = file_to_download.file_id
        file = await context.bot.get_file(file_id)
        
        # Faylni yuklab olish uchun unikal nom yaratish
        downloaded_file_path = os.path.join(DOWNLOAD_PATH, f"{file_id}_{file_to_download.file_name or 'audio.ogg'}")
        await file.download_to_drive(downloaded_file_path)
        logger.info(f"Fayl transkripsiya uchun yuklab olindi: {downloaded_file_path}")

        audio_path_to_transcribe = downloaded_file_path

        # Agar video bo'lsa, audioni ajratib olish
        if message.video:
            await status_message.edit_text("Videodan audio ajratib olinmoqda...")
            output_audio_path = os.path.join(DOWNLOAD_PATH, f"{file_id}_extracted_audio.mp3")
            try:
                ffmpeg.input(downloaded_file_path).output(output_audio_path, acodec='libmp3lame', ar='16000').run(overwrite_output=True, quiet=True)
                audio_path_to_transcribe = output_audio_path
                logger.info(f"Audio muvaffaqiyatli ajratib olindi: {output_audio_path}")
            except ffmpeg.Error as e:
                error_details = e.stderr.decode() if e.stderr else "Noma'lum xato"
                logger.error(f"ffmpeg xatosi: {error_details}")
                await status_message.edit_text("Videodan audioni ajratib olishda xatolik yuz berdi.")
                return

        # Transkripsiya qilish
        await status_message.edit_text("Audio tahlil qilinmoqda... Bu bir necha daqiqa vaqt olishi mumkin.")
        language, transcript = await transcribe_audio_from_file(audio_path_to_transcribe)

        if transcript and language:
            # Natijani chiroyli formatda yuborish
            header = f"✅ Transkripsiya muvaffaqiyatli yakunlandi!\n\n**Aniqlangan til:** `{language.upper()}`\n---\n"
            await status_message.edit_text(header + transcript, parse_mode='Markdown')
        else:
            # Transkripsiyadan kelgan xatolikni ko'rsatish
            await status_message.edit_text(transcript or "Noma'lum xatolik yuz berdi.")

    except Exception as e:
        logger.error(f"Transkripsiya jarayonida umumiy xatolik: {e}", exc_info=True)
        await status_message.edit_text("Kechirasiz, faylni qayta ishlashda kutilmagan xatolik yuz berdi.")
    finally:
        # Vaqtinchalik fayllarni tozalash
        if 'downloaded_file_path' in locals() and os.path.exists(downloaded_file_path):
            os.remove(downloaded_file_path)
        if 'output_audio_path' in locals() and os.path.exists(output_audio_path):
            os.remove(output_audio_path)


async def main() -> None:
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
