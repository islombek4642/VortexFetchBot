import os
import re
import time
import asyncio
from typing import Optional
import functools
import ffmpeg
from telegram import Message
from config import logger


async def add_metadata_to_song(audio_path: str, title: str, artist: str):
    """Adds title and artist metadata to an audio file using ffmpeg."""
    logger.info(f"Adding metadata to {audio_path}: Title='{title}', Artist='{artist}'")
    try:
        temp_output_path = audio_path + '.temp.mp3'
        await _run_ffmpeg_async(functools.partial(
            ffmpeg.input(audio_path)
            .output(temp_output_path, metadata=[f'title={title}', f'artist={artist}'], codec='copy')
            .run,
            overwrite_output=True, quiet=True
        ))
        os.replace(temp_output_path, audio_path)
        logger.info(f"Successfully added metadata to {audio_path}")
    except ffmpeg.Error as e:
        logger.error(f"ffmpeg error while adding metadata to {audio_path}: {e.stderr.decode() if e.stderr else e}")
    except Exception as e:
        logger.error(f"Unexpected error adding metadata to {audio_path}: {e}", exc_info=True)

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
    """Runs yt-dlp, captures output, and reports progress."""
    logger.debug(f"Running command: {' '.join(command)}")
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    async def stream_reader(stream, stream_name):
        lines = []
        while True:
            line = await stream.readline()
            if not line:
                break
            line_str = line.decode('utf-8', errors='ignore').strip()
            lines.append(line_str)
            logger.debug(f"yt-dlp {stream_name}: {line_str}")
        return "\n".join(lines)

    # Concurrently read stdout and stderr
    stdout_task = asyncio.create_task(stream_reader(process.stdout, 'stdout'))
    stderr_task = asyncio.create_task(stream_reader(process.stderr, 'stderr'))

    # Wait for the process to complete
    await process.wait()

    # Get the results from the stream readers
    stdout = await stdout_task
    stderr = await stderr_task

    return process.returncode, stdout, stderr


async def _run_ffmpeg_async(func):
    """Runs a blocking ffmpeg function in a separate thread to avoid blocking the asyncio event loop."""
    loop = asyncio.get_running_loop()
    # functools.partial is used to pass the function with its arguments
    await loop.run_in_executor(None, func)
