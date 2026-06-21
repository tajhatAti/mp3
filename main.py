import os
import re
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot

# ===================== CONFIG =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
bot = telebot.TeleBot(BOT_TOKEN)

# ইউটিউব লিংক ডিটেক্ট করার জন্য Regex
YOUTUBE_REGEX = r'(https?://)?(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/[^\s]+'

# ===================== MULTI-API COBALT LOGIC =====================
COBALT_INSTANCES = [
    "https://api.cobalt.tools/api/json",
    "https://co.wuk.sh/api/json",
    "https://cobalt.api.v0.pw/api/json",
    "https://api.cobalt.club/api/json"
]

def fetch_mp3_link(youtube_url):
    """নতুন ও পুরোনো দুই ফরম্যাটের প্যারামিটার টেস্ট করে নিশ্চিত অডিও লিংক বের করবে"""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    for idx, api_url in enumerate(COBALT_INSTANCES):
        # ১. নতুন Cobalt v7 ফরম্যাট (downloadMode)
        payload_new = {
            "url": youtube_url,
            "downloadMode": "audio",
            "audioFormat": "mp3"
        }
        try:
            print(f"[+] Trying New API Format on Instance {idx}")
            response = requests.post(api_url, json=payload_new, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "url" in data:
                    print(f"✅ Success with New Format on Instance {idx}")
                    return data.get("url")
        except Exception as e:
            print(f"[-] New Format Error on Instance {idx}: {e}")
            
        # ২. ব্যাকআপ: যদি কোনো সার্ভার এখনও পুরোনো ভার্সনে চলে (isAudioOnly)
        payload_old = {
            "url": youtube_url,
            "isAudioOnly": True,
            "audioFormat": "mp3"
        }
        try:
            print(f"[+] Trying Old API Format on Instance {idx}")
            response = requests.post(api_url, json=payload_old, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "url" in data:
                    print(f"✅ Success with Old Format on Instance {idx}")
                    return data.get("url")
        except Exception as e:
            print(f"[-] Old Format Error on Instance {idx}: {e}")
            
    return None

# ===================== TELEGRAM HANDLER =====================
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.reply_to(message, "👋 হ্যালো! আমাকে যেকোনো ইউটিউব ভিডিওর লিংক পাঠাও।\n"
                          "আমি স্বয়ংক্রিয়ভাবে সেটিকে উচ্চমানের MP3 তেকনভার্ট করে পাঠিয়ে দেব।\n\n"
                          "✨ সম্পূর্ণ বিজ্ঞাপন মুক্ত এবং আনলিমিটেড।")

@bot.message_handler(func=lambda message: True)
def handle_youtube_link(message):
    match = re.search(YOUTUBE_REGEX, message.text)
    
    if match:
        extracted_url = match.group(0)
        msg = bot.reply_to(message, "⏳ ইউটিউব লিংক পাওয়া গেছে। অডিও প্রসেস করছি, একটু অপেক্ষা করো...")
        
        # এপিআই ফেচিং
        mp3_direct_url = fetch_mp3_link(extracted_url)
        
        if mp3_direct_url:
            try:
                bot.edit_message_text("📤 কনভার্ট সম্পন্ন! টেলিগ্রামে আপলোড হচ্ছে...", message.chat.id, msg.message_id)
                
                # সরাসরি অডিও ইউআরএল টেলিগ্রামে সেন্ড
                bot.send_audio(
                    chat_id=message.chat.id, 
                    audio=mp3_direct_url, 
                    title="Audio Tracks", 
                    performer="YouTube Downloader Bot",
                    reply_to_message_id=message.message_id
                )
                bot.delete_message(message.chat.id, msg.message_id)
                
            except Exception as e:
                print(f"Telegram Upload Error: {e}")
                bot.edit_message_text("❌ ফাইলটি টেলিগ্রামে পাঠাতে সমস্যা হয়েছে। ফাইল সাইজ অনেক বড় হতে পারে।", message.chat.id, msg.message_id)
        else:
            bot.edit_message_text("❌ অডিও লিংক জেনারেট করা যায়নি। লিংকটি আবার চেক করো অথবা অন্য কোনো ভিডিও ট্রাই করো।", message.chat.id, msg.message_id)

# ===================== KEEP ALIVE SERVER =====================
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"YT MP3 Bot is Running!")

def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(('0.0.0.0', port), DummyServer).serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()

# ===================== RUN =====================
if __name__ == "__main__":
    print("[+] YouTube MP3 Bot Started with Dual-Payload Support...")
    bot.infinity_polling()
