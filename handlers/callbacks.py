import os
import html
from telegram import Update, CallbackQuery
from telegram.ext import ContextTypes

from config import settings, logger
from utils.helpers import _run_yt_dlp_with_progress, find_first_file
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

    if not song_data:
        await query.edit_message_caption(caption="Bu yuklash havolasining muddati o'tgan yoki xato.")
        return

    youtube_url = song_data.get('youtube_url')
    full_title = song_data.get('full_title')

    if not youtube_url:
        await query.edit_message_caption(caption=f"<b>{html.escape(full_title)}</b> uchun yuklab olish havolasi topilmadi.", parse_mode='HTML')
        return

    await query.edit_message_caption(caption=f"🎵 <b>{html.escape(full_title)}</b> yuklanmoqda...", parse_mode='HTML')
    status_message = query.message # We use the original message for sending the audio file
    audio_path = None
    try:
        output_template = os.path.join(settings.DOWNLOAD_PATH, f'{user_id}_{song_id}_%(title)s.%(ext)s')
        command = [
            'yt-dlp', '-x', '--audio-format', 'mp3', '--audio-quality', '0',
            '-o', output_template, '--max-filesize', '49m', youtube_url
        ]
        return_code, stderr = await _run_yt_dlp_with_progress(command, status_message, f"🎵 <b>{html.escape(full_title)}</b> yuklanmoqda...")

        if return_code != 0:
            logger.error(f"Error downloading song {full_title}: {stderr}")
            await status_message.edit_message_text("❌ Qo'shiqni yuklashda xatolik.")
            return

        audio_path = find_first_file(settings.DOWNLOAD_PATH, f'{user_id}_{song_id}_')
        if not audio_path:
            await status_message.edit_message_text("❌ Yuklangan qo'shiq fayli topilmadi.")
            return

        with open(audio_path, 'rb') as audio_file:
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=audio_file,
                title=full_title,
                caption="#VortexFetchBot"
            )
        await status_message.delete()
    except Exception as e:
        logger.error(f"Error processing song download: {e}", exc_info=True)
        await status_message.edit_message_text("Kutilmagan xatolik.")
    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
        if song_id in context.bot_data:
            del context.bot_data[song_id]

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and routes to the appropriate handler."""
    query = update.callback_query
    await query.answer()

    if query.data.startswith('stats_page_'):
        await _handle_stats_pagination(query)
    elif query.data.startswith('dl_song_'):
        await _handle_song_download(query, context)
    else:
        logger.warning(f"Unhandled callback query data: {query.data}")
