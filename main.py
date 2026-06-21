import os
import re
import threading
import requests
import subprocess
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot

# ===================== CONFIG =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
RAPID_API_KEY = os.environ.get("RAPID_API_KEY", "YOUR_RAPIDAPI_KEY_HERE")

bot = telebot.TeleBot(BOT_TOKEN)

YOUTUBE_REGEX = r'(https?://)?(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/[^\s]+'

# ===================== METHOD 1: yt-dlp =====================
def try_ytdlp(youtube_url):
    out_file = f"/tmp/{uuid.uuid4().hex}.mp3"
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "128K",
        "--output", out_file,
        "--no-warnings",
        "--quiet",
        "--socket-timeout", "15",
        youtube_url
    ]
    try:
        result = subprocess.run(cmd, timeout=60, capture_output=True, text=True)
        if result.returncode == 0 and os.path.exists(out_file):
            return out_file
        print(f"[yt-dlp] Failed: {result.stderr[:200]}")
        return None
    except subprocess.TimeoutExpired:
        print("[yt-dlp] Timeout")
        return None
    except FileNotFoundError:
        print("[yt-dlp] Not installed")
        return None
    except Exception as e:
        print(f"[yt-dlp] Error: {e}")
        return None

# ===================== METHOD 2: RapidAPI =====================
def try_rapidapi(youtube_url):
    video_id_match = re.search(r'(?:v=|\/|embed\/|shorts\/)([0-9A-Za-z_-]{11})', youtube_url)
    if not video_id_match:
        return None
    video_id = video_id_match.group(1)

    try:
        headers = {
            "X-RapidAPI-Key": RAPID_API_KEY,
            "X-RapidAPI-Host": "yt-mp3.p.rapidapi.com"
        }
        res = requests.get(
            "https://yt-mp3.p.rapidapi.com/dl",
            params={"id": video_id},
            headers=headers,
            timeout=15
        )
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "ok":
                return data.get("msg")
        print(f"[RapidAPI] Failed: {res.status_code} {res.text[:100]}")
        return None
    except Exception as e:
        print(f"[RapidAPI] Error: {e}")
        return None

# ===================== COMBINED DOWNLOADER =====================
def get_mp3(youtube_url):
    print("[*] Trying yt-dlp...")
    result = try_ytdlp(youtube_url)
    if result:
        return result, "file"

    print("[*] yt-dlp failed, trying RapidAPI...")
    result = try_rapidapi(youtube_url)
    if result:
        return result, "url"

    return None, None

# ===================== HANDLERS =====================
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.reply_to(message,
        "🎵 <b>YouTube MP3 Bot</b>\n\n"
        "যেকোনো YouTube লিংক পাঠাও → MP3 পাবে!\n\n"
        "✅ Supports: youtube.com, youtu.be, music.youtube.com\n"
        "⚡ Render 24/7 Active",
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda message: True)
def handle_link(message):
    match = re.search(YOUTUBE_REGEX, message.text)
    if not match:
        bot.reply_to(message, "❌ YouTube লিংক পাঠাও!")
        return

    url = match.group(0)
    if not url.startswith("http"):
        url = "https://" + url

    msg = bot.reply_to(message, "⏳ Processing...")

    result, result_type = get_mp3(url)

    if not result:
        bot.edit_message_text(
            "❌ Download হয়নি। লিংক check করো বা পরে try করো।",
            message.chat.id, msg.message_id
        )
        return

    try:
        bot.edit_message_text("📤 Sending audio...", message.chat.id, msg.message_id)

        if result_type == "file":
            with open(result, 'rb') as f:
                bot.send_audio(
                    chat_id=message.chat.id,
                    audio=f,
                    reply_to_message_id=message.message_id
                )
            os.remove(result)
        else:
            bot.send_audio(
                chat_id=message.chat.id,
                audio=result,
                reply_to_message_id=message.message_id
            )

        bot.delete_message(message.chat.id, msg.message_id)

    except Exception as e:
        print(f"[Send Error] {e}")
        bot.edit_message_text(
            f"❌ File পাঠাতে সমস্যা: {str(e)[:100]}",
            message.chat.id, msg.message_id
        )
        if result_type == "file" and os.path.exists(result):
            os.remove(result)

# ===================== KEEP ALIVE =====================
class PingServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"YT MP3 Bot - ALIVE!")
    def log_message(self, *args): pass

def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(('0.0.0.0', port), PingServer).serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()

# ===================== RUN =====================
if __name__ == "__main__":
    print("[+] YT MP3 Bot started (yt-dlp → RapidAPI fallback)")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
        
