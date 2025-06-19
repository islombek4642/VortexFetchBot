# VortexFetchBot 🌪️

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-gray?style=for-the-badge&logo=telegram)](https://core.telegram.org/bots/api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

**VortexFetchBot** — bu Telegram uchun yaratilgan ko'p funksiyali media-assistent. U YouTube, Instagram, TikTok kabi mashhur platformalardan videolarni osonlikcha yuklab olish, videodagi musiqani aniqlash va audio/video xabarlarni matnga o'girish imkoniyatini beradi.

---

## 🚀 Asosiy Imkoniyatlar

-   **Video Yuklash:** Har qanday qo'llab-quvvatlanadigan platformadan havolani yuboring va videoni oling.
-   **Musiqa Aniqlash:** Videodagi qo'shiqni bir zumda toping (`Shazam` integratsiyasi).
-   **Transkripsiya:** Audio, video yoki ovozli xabarlarni matnga o'giring (`Whisper` yordamida).
-   **Admin Paneli:** Bot foydalanuvchilari statistikasini kuzatib boring.
-   **Keng Platforma Dastagi:** `yt-dlp` tufayli yuzlab veb-saytlarni qo'llab-quvvatlaydi.

## 🛠️ Texnologiyalar Stеki

-   **Til:** Python 3.8+
-   **Asosiy Freymvork:** `python-telegram-bot`
-   **Video Yuklash:** `yt-dlp`
-   **Musiqa Aniqlash:** `shazamio`
-   **Transkripsiya:** `faster-whisper`
-   **Audio Ishlov:** `ffmpeg-python`
-   **Ma'lumotlar Bazasi:** `SQLite`

## ⚙️ O'rnatish va Ishga Tushirish

Loyihani o'z kompyuteringizda ishga tushirish uchun quyidagi amallarni bajaring:

### 1. Talablar

-   **Python 3.8** yoki undan yuqori versiya.
-   **FFmpeg:** Tizimingizda o'rnatilgan va `PATH`ga qo'shilgan bo'lishi kerak. Bu audio va video fayllarni qayta ishlash uchun zarur.

### 2. Loyihani Klonlash

```bash
git clone https://github.com/islombek4642/VortexFetchBot.git
cd VortexFetchBot
```

### 3. Virtual Muhit Yaratish

Virtual muhit yaratish va faollashtirish har doim tavsiya etiladi:

```bash
# Windows uchun
python -m venv venv
venv\Scripts\activate

# macOS / Linux uchun
python3 -m venv venv
source venv/bin/activate
```

### 4. Bog'liqliklarni O'rnatish

Kerakli barcha kutubxonalarni `requirements.txt` fayli orqali o'rnating:

```bash
pip install -r requirements.txt
```

### 5. Konfiguratsiya (.env fayli)

Loyiha papkasida `.env` nomli fayl yarating va unga quyidagi o'zgaruvchilarni kiriting.

```env
# @BotFather orqali olingan Telegram bot tokeni
TELEGRAM_BOT_TOKEN="SIZNING_TELEGRAM_BOT_TOKENINGIZ"

# Sizning shaxsiy Telegram ID raqamingiz (admin buyruqlari uchun)
ADMIN_ID="SIZNING_TELEGRAM_ID"

# (Ixtiyoriy) YouTube cheklovlarini chetlab o'tish uchun cookie fayli
# Brauzeringizdan cookies.txt fayli tarkibini to'liq nusxalab joylashtiring
YOUTUBE_COOKIES='''
...bu yerga cookie ma'lumotlari joylanadi...
'''
```

### 6. Botni Ishga Tushirish

Barcha sozlamalar tayyor bo'lgach, botni ishga tushiring:

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
