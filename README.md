# Universal Video Downloader Telegram Bot

A Telegram bot that downloads videos from various platforms using `yt-dlp`.

## Features

-   Download videos by sending a URL to the bot.
-   Supports a wide range of websites (thanks to `yt-dlp`).
-   Attempts to download videos in MP4 format, up to 720p, and under 50MB (Telegram's bot API limit for sending files).

## Prerequisites

-   Python 3.8+
-   `yt-dlp` installed and accessible in your system's PATH (or specify the path if needed).
    -   You can install `yt-dlp` via pip: `pip install yt-dlp`
    -   Alternatively, download the executable from [yt-dlp GitHub releases](https://github.com/yt-dlp/yt-dlp/releases) and ensure it's in your PATH.
-   A Telegram Bot Token.

## Setup

1.  **Clone the repository (or create the files as provided):**
    ```bash
    # If you had a git repo, you'd clone it here.
    # For now, ensure bot.py, requirements.txt are in a directory.
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

    This will install `python-telegram-bot`, `yt-dlp`, and `python-dotenv`.
    ```

4.  **Set the Telegram Bot Token:**
    Create a file named `.env` in the project's root directory (`d:\VIDEO_DOWNLOADER`).
    Add the following line to the `.env` file, replacing `YOUR_TELEGRAM_BOT_TOKEN` with your actual token:
    ```
    TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
    ```
    The bot will load this token automatically.

5.  **Ensure `yt-dlp` is installed and in PATH:**
    The bot calls `yt-dlp` as a command-line tool. If it's not in your PATH, the video download will fail. You can test by typing `yt-dlp --version` in your terminal.

## Running the Bot

```bash
python bot.py
```

## How to Use

1.  Start a chat with your bot on Telegram.
2.  Send `/start` to see the welcome message.
3.  Send a video URL (e.g., a YouTube link).
4.  The bot will attempt to download the video and send it back to you.

## Limitations

-   **File Size:** Telegram Bot API has a limit of 50MB for files sent by bots. The bot tries to download videos under this limit. Very long or high-quality videos might exceed this.
-   **Processing Time:** Downloading and processing can take time, especially for larger videos or slower connections.
-   **`yt-dlp` Dependency:** Relies on `yt-dlp` for all download functionalities. If `yt-dlp` cannot download a video from a specific URL, this bot won't be able to either.
-   **Error Handling:** Basic error handling is in place, but complex `yt-dlp` errors might not be gracefully handled.
-   **Resource Usage:** Downloading videos can be resource-intensive (CPU, network, disk space for temporary files).

## TODO / Potential Improvements

-   More robust filename handling after download.
-   Option for users to select video quality/format.
-   Queue system for handling multiple requests.
-   More detailed feedback to the user during download process.
-   Dockerization for easier deployment.
