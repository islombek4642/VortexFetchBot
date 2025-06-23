import os
import html
from telegram import Update, CallbackQuery
from telegram.ext import ContextTypes

from config import settings, logger
from utils.helpers import _run_yt_dlp_with_progress, find_first_file, add_metadata_to_song
from handlers.general import _generate_stats_message_and_keyboard

async def _handle_stats_pagination(query: CallbackQuery) -> None:
    """Handles the logic for stats pagination."""
    user_id = query.from_user.id
    if user_id != settings.ADMIN_ID:
        await query.answer("Bu buyruq faqat administrator uchun.", show_alert=True)
        return

    try:
        page = int(query.data.split('_')[2])
        message_text, reply_markup = await _generate_stats_message_and_keyboard(page)
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    except (IndexError, ValueError):
        logger.warning(f"Invalid stats page callback data: {query.data}")
        await query.answer("Noto'g'ri so'rov.", show_alert=True)
    except Exception as e:
        logger.error(f"Error handling stats pagination: {e}", exc_info=True)
        await query.answer("Statistikani ko'rsatishda xatolik.", show_alert=True)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and routes to the appropriate handler."""
    query = update.callback_query
    await query.answer()

    if query.data.startswith('dl_song_'):
        await _handle_song_download(query, context)
    elif query.data.startswith('stats_page_'):
        await _handle_stats_pagination(query)
    else:
        logger.warning(f"Unhandled callback query with data: {query.data}")


async def _handle_song_download(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the logic for downloading a song."""
    user_id = query.from_user.id
    song_id = query.data.replace('dl_song_', '')
    song_data = context.bot_data.get(song_id)

    logger.info(f"Download button pressed: song_id={song_id}, song_data={song_data}")

    if not song_data:
        await query.edit_message_text("Bu yuklash havolasining muddati o'tgan yoki xato.")
        return

    youtube_url = song_data.get('youtube_url')
    full_title = song_data.get('full_title', "Noma'lum Qo'shiq")

    if not youtube_url:
        await query.edit_message_text(f"<b>{html.escape(full_title)}</b> uchun yuklab olish havolasi topilmadi.", parse_mode='HTML')
        return

    
    # Determine whether to edit the message text or caption
    text_to_send = f"🎵 <b>{html.escape(full_title)}</b> yuklanmoqda..."
    if query.message.text:
        status_message = await query.edit_message_text(text_to_send, parse_mode='HTML')
    elif query.message.caption:
        status_message = await query.edit_message_caption(caption=text_to_send, parse_mode='HTML')
    else:
        # Fallback for messages without text or caption (should be rare)
        await query.message.delete()
        status_message = await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text_to_send,
            parse_mode='HTML'
        )
    audio_path = None
    try:
        output_template = os.path.join(settings.DOWNLOAD_PATH, f'{user_id}_{song_id}_%(title)s.%(ext)s')
        command = [
            'yt-dlp',
            '--extract-audio', # Extract audio
            '--audio-format', 'mp3',
            '--audio-quality', '0', # Best quality
            '-o', output_template,
            '--max-filesize', f"{settings.MAX_FILE_SIZE_MB}m",
            '--no-playlist',
            '--ignore-errors',
            '--no-check-certificates',
            '--geo-bypass',
            youtube_url
        ]
        
        # Add cookies if specified in settings
        if settings.YOUTUBE_COOKIE_FILE and os.path.exists(settings.YOUTUBE_COOKIE_FILE):
            command.extend(['--cookies', settings.YOUTUBE_COOKIE_FILE])

        return_code, stdout, stderr = await _run_yt_dlp_with_progress(command, query.message, f"🎵 <b>{html.escape(full_title)}</b> yuklanmoqda...")

        if ("Sign in to confirm" in stderr or "Signature extraction failed" in stderr):
            await query.edit_message_text(
                f"❌ <b>{html.escape(full_title)}</b> qo'shig'ini yuklab bo'lmadi. YouTube himoyasi tufayli bu faylga kirish cheklangan.",
                parse_mode='HTML'
            )
            return

        if return_code != 0:
            logger.error(f"Error downloading song {full_title}: {stderr}")
            await query.edit_message_text("❌ Qo'shiqni yuklashda xatolik.", parse_mode='HTML')
            return

        audio_path = find_first_file(settings.DOWNLOAD_PATH, f'{user_id}_{song_id}_')
        if not audio_path:
            await query.edit_message_text("❌ Yuklangan qo'shiq fayli topilmadi.", parse_mode='HTML')
            return

        # Add metadata
        await query.edit_message_text(f"🎵 Metadata qo'shilmoqda...", parse_mode='HTML')
        artist, title = (full_title.split(' - ', 1) + [full_title])[:2]
        await add_metadata_to_song(audio_path, title, artist)

        await query.edit_message_text(f"✅ <b>{html.escape(full_title)}</b> yuklandi! Yuborilmoqda...", parse_mode='HTML')

        with open(audio_path, 'rb') as audio_file:
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=audio_file,
                title=title,
                performer=artist,
                caption=f"#VortexFetchBot | @{context.bot.username}"
            )
        await query.message.delete() # Delete the original status message

    except Exception as e:
        logger.error(f"Error processing song download: {e}", exc_info=True)
        error_message = f"<b>Xatolik:</b>\n<code>{html.escape(str(e))}</code>"
        try:
            if status_message.text:
                await status_message.edit_text(error_message, parse_mode='HTML')
            elif status_message.caption:
                await status_message.edit_caption(caption=error_message, parse_mode='HTML')
        except Exception as inner_e:
            logger.error(f"Failed to send final error message: {inner_e}")
    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
        if song_id in context.bot_data:
            del context.bot_data[song_id]
