import os
import re
import time
import asyncio
from typing import Optional
import functools
from telegram import Message
from config import logger

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
            
            match = re.search(r"\[download\]\\s+([0-9\\.]+)%", output)
            if match:
                try:
                    percentage = int(float(match.group(1)))
                    current_time = time.time()
                    
                    if percentage > last_percentage and (percentage % 5 == 0 or current_time - last_update_time > 2):
                        new_text = f"{progress_text_prefix} {percentage}%"
                        if new_text != status_message.text:
                            await status_message.edit_text(new_text)
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


async def _run_ffmpeg_async(func):
    """Runs a blocking ffmpeg function in a separate thread to avoid blocking the asyncio event loop."""
    loop = asyncio.get_running_loop()
    # functools.partial is used to pass the function with its arguments
    await loop.run_in_executor(None, func)
