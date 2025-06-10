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
    # For now, we'll let it proceed but the bot won't work.

DOWNLOAD_PATH = 'downloads'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! Send me a video link and I'll try to download it for you.",
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message when the /help command is issued."""
    await update.message.reply_text(
        "Send me a link to a video from a supported platform (like YouTube, Vimeo, etc.), "
        "and I will try to download it and send it back to you.\n\n"
        "Supported sites are numerous, thanks to yt-dlp. "
        "Large videos might take time or fail due to Telegram's file size limits."
    )

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    video_path = None  # Initialize video_path
    process = None     # Initialize process
    """Downloads video from the URL sent by the user."""
    url = update.message.text
    chat_id = update.message.chat_id

    status_message = await update.message.reply_text("Processing your request... Please wait.")

    if not url or not (url.startswith('http://') or url.startswith('https://')):
        await status_message.edit_text("Please send a valid video URL.")
        return

    # Create download directory if it doesn't exist
    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)

    # Use yt-dlp to download the video
    # We'll try to get the best quality video that's under a reasonable size limit (e.g., 50MB for Telegram)
    # The filename will be based on the video title
    output_template = os.path.join(DOWNLOAD_PATH, '%(title)s.%(ext)s')
    command = [
        'yt-dlp',
        '-f', 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best',
        '--merge-output-format', 'mp4',
        '-o', output_template,
        '--max-filesize', '49m', # Telegram bot API limit is 50MB for sending files
        url
    ]

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
            
            downloaded_files = []
            for f in os.listdir(DOWNLOAD_PATH):
                # This is a heuristic. A better way would be to get the exact filename from yt-dlp output.
                if f.endswith('.mp4'): # Assuming mp4 output
                    downloaded_files.append(os.path.join(DOWNLOAD_PATH, f))
            
            if not downloaded_files:
                logger.error(f"yt-dlp finished but no file found for URL: {url}")
                logger.error(f"yt-dlp stdout: {stdout.decode(errors='ignore')}")
                logger.error(f"yt-dlp stderr: {stderr.decode(errors='ignore')}")
                await update.message.reply_text("Sorry, I couldn't download the video or no suitable format was found within size limits.")
                return

            # Assuming the first (or newest) mp4 file is the one we want.
            # This part needs to be more robust for production.
            video_path = max(downloaded_files, key=os.path.getctime) # Get the newest file
            
            logger.info(f"Successfully downloaded video to: {video_path}")
            await status_message.edit_text(f"Download complete! Preparing video and checking for music...")

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
                    caption=os.path.basename(video_path),
                    reply_markup=inline_markup_for_video # Attach button here if available
                )
            logger.info(f"Successfully sent video: {video_path} to chat_id: {chat_id}")

        else:
            error_message = stderr.decode(errors='ignore')
            logger.error(f"yt-dlp failed for URL: {url}. Error: {error_message}")
            reply_text = f"Sorry, I couldn't download the video. Error from downloader: {error_message[:1000]}"
            if "File is larger than max-filesize" in error_message:
                reply_text = "The video is too large to download within the set limits (max 50MB for Telegram)."
            elif "Unsupported URL" in error_message:
                reply_text = "The provided URL is not supported."
            await status_message.edit_text(reply_text)

    except Exception as e:
        logger.error(f"An error occurred during video download process for {url}: {e}")
        if status_message:
            await status_message.edit_text(f"An unexpected error occurred: {e}")
        else:
            await update.message.reply_text(f"An unexpected error occurred: {e}") # Fallback if status_message not set
    finally:
        # Clean up the downloaded file
        if video_path and os.path.exists(video_path): # Check if video_path was assigned and exists
            os.remove(video_path)
            logger.info(f"Cleaned up downloaded file: {video_path}")


async def recognize_and_offer_song_download(update: Update, context: ContextTypes.DEFAULT_TYPE, video_filepath: str) -> Optional[InlineKeyboardMarkup]:
    """Extracts audio, recognizes song, and offers download if found."""
    chat_id = update.message.chat_id
    audio_extraction_path = os.path.join(DOWNLOAD_PATH, 'extracted_audio.m4a') # yt-dlp prefers m4a for audio usually

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
            await update.message.reply_text("Could not extract audio to identify music.")
            return
        
        if not os.path.exists(audio_extraction_path):
            logger.error(f"Audio extraction finished but file not found: {audio_extraction_path}")
            await update.message.reply_text("Audio extraction seemed to work, but the audio file is missing.")
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
        await query.edit_message_text(text="Error: Invalid request data.")
        return

    if action == "download_song":
        search_query = song_details_payload # This is already truncated
        logger.info(f"Download song button clicked. Search query: {search_query}")

        # Send a new message to show that we are processing the request
        status_message = await context.bot.send_message(chat_id=query.message.chat_id, text=f"Searching for '{search_query}' to download...")
        
        song_output_template = os.path.join(DOWNLOAD_PATH, '%(title)s_audio.%(ext)s')
        # Use yt-dlp to search and download the best audio
        # ytsearch: will search on youtube (default) / youtube music
        # -x for extract audio, --audio-format mp3 for mp3 output
        # --default-search "ytsearch1:" to pick the first result
        song_download_command = [
            'yt-dlp',
            '--quiet',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            '--extract-audio',
            '--audio-format', 'mp3',
            '--default-search', f'ytsearch:{search_query}', # Search and pick first result
            '-o', song_output_template,
            '--max-filesize', '20m', # Limit song download size too
            search_query
        ]

        try:
            logger.info(f"Attempting to download song: {search_query} with command: {' '.join(song_download_command)}")
            process = subprocess.Popen(song_download_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                downloaded_songs = []
                for f in os.listdir(DOWNLOAD_PATH):
                    if f.endswith('_audio.mp3'): # Match our output template
                        downloaded_songs.append(os.path.join(DOWNLOAD_PATH, f))
                
                if not downloaded_songs:
                    logger.error(f"yt-dlp song download finished but no file found for query: {search_query}")
                    if status_message:
                        await status_message.edit_text("Sorry, I couldn't download the song audio or no suitable format was found.")
                    else:
                        await context.bot.send_message(chat_id=query.message.chat_id, text="Sorry, I couldn't download the song audio or no suitable format was found.")
                    return

                song_audio_path = max(downloaded_songs, key=os.path.getctime) # Get the newest file
                logger.info(f"Successfully downloaded song audio to: {song_audio_path}")
                if status_message:
                    await status_message.edit_text("Song download complete! Uploading to Telegram...")
                else:
                    # Fallback if status_message wasn't sent for some reason
                    await context.bot.send_message(chat_id=query.message.chat_id, text="Song download complete! Uploading to Telegram...")
                
                try:
                    with open(song_audio_path, 'rb') as audio_file:
                        await context.bot.send_audio(chat_id=query.message.chat_id, audio=audio_file, title=os.path.basename(song_audio_path).replace('_audio.mp3',''))
                    logger.info(f"Successfully sent song audio: {song_audio_path} to chat_id: {query.message.chat_id}")
                    if status_message: # Delete the status message after sending audio
                        await status_message.delete()
                        logger.info(f"Deleted status message (ID: {status_message.message_id}) after sending audio.")
                except Exception as e:
                    logger.error(f"Failed to send song audio {song_audio_path} to Telegram: {e}")
                    if status_message:
                        await status_message.edit_text(f"Sorry, I downloaded the song but failed to send it. Error: {e}")
                    else:
                        await context.bot.send_message(chat_id=query.message.chat_id, text=f"Sorry, I downloaded the song but failed to send it. Error: {e}")
                finally:
                    if os.path.exists(song_audio_path):
                        os.remove(song_audio_path)
                        logger.info(f"Cleaned up downloaded song audio: {song_audio_path}")
            else:
                error_message = stderr.decode(errors='ignore')
                logger.error(f"yt-dlp failed for song query: {search_query}. Error: {error_message}")
                user_friendly_error = "Sorry, I was unable to download the song. This might be a temporary issue with the source. Please try again later."
                if status_message:
                    await status_message.edit_text(user_friendly_error)
                else:
                    await context.bot.send_message(chat_id=query.message.chat_id, text=user_friendly_error)

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




def main() -> None:
    """Start the bot."""
    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set. Bot cannot start.")
        return

    # Create the Application and pass it your bot's token.
    application = ApplicationBuilder().token(TOKEN).read_timeout(30).connect_timeout(30).write_timeout(60).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))
    application.add_handler(CallbackQueryHandler(button_callback_handler)) # Add handler for button clicks

    logger.info("Bot starting...")
    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == '__main__':
    main()
