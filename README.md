# Universal Video Yuklovchi Telegram Bot

`yt-dlp` yordamida turli platformalardan videolarni yuklab beruvchi Telegram boti.

## Imkoniyatlar

-   Botga URL yuborish orqali videolarni yuklab olish.
-   Keng ko'lamli veb-saytlarni qo'llab-quvvatlaydi (`yt-dlp` tufayli).
-   Videolarni MP4 formatida, maksimal 720p sifatida va 50MB dan oshmasligiga harakat qiladi (Telegram bot API chegarasi).

## Talablar

-   Python 3.8+ kerak bo'ladi
-   Tizimingizda `yt-dlp` o'rnatilgan va PATH'da mavjud bo'lishi kerak:
    -   `yt-dlp` ni pip orqali o'rnatish: `pip install yt-dlp`
    -   Yoki [yt-dlp GitHub releases](https://github.com/yt-dlp/yt-dlp/releases) dan yuklab oling va PATH'ga qo'shing.
-   Telegram Bot Tokeni kerak bo'ladi.

## O'rnatish

1.  **Repozitoriyani klonlang yoki fayllarni yarating:**
    ```bash
    # Git repozitoriyangiz bo'lsa, shu yerda klon qilishingiz mumkin.
    # Hozircha bot.py, requirements.txt fayllari papkada ekanligiga ishonch hosil qiling.
    ```

2.  **Virtual muhit yarating (tavsiya etiladi):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windowsda: venv\Scripts\activate
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
