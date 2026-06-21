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
# বিভিন্ন একটিভ Cobalt মিরর সার্ভারের লিস্ট (একটা ডাউন থাকলে আরেকটা কাজ করবে)
COBALT_INSTANCES = [
    "https://api.cobalt.tools/api/json",
    "https://co.wuk.sh/api/json",
    "https://cobalt.api.v0.pw/api/json",
    "https://api.cobalt.club/api/json"
]

def fetch_mp3_link(youtube_url):
    """মাল্টিপল এপিআই মিরর চেক করে যেকোনো একটি থেকে MP3 লিংক বের করবে"""
    payload = {
        "url": youtube_url,
        "isAudioOnly": True,
        "audioFormat": "mp3",
        "vQuality": "720"
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # লিস্টের প্রতিটি সার্ভার একে একে ট্রাই করবে
    for idx, api_url in enumerate(COBALT_INSTANCES):
        try:
            print(f"[+] Trying Cobalt Instance {idx}: {api_url}")
            response = requests.post(api_url, json=payload, headers=headers, timeout=12)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "stream":
                    print(f"✅ Success with Instance {idx}")
                    return data.get("url")  # লিংক পেলে লুপ এখানেই শেষ
                    
            print(f"[-] Instance {idx} failed with status: {response.status_code}")
            continue  # ব্যর্থ হলে পরের সার্ভারে যাবে
            
        except Exception as e:
            print(f"[-] Instance {idx} Request Error: {e}")
            continue  # এরর আসলে পরের সার্ভারে যাবে
            
    return None  # সব সার্ভার ফেইল করলেই কেবল None রিটার্ন হবে

# ===================== TELEGRAM HANDLER =====================
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.reply_to(message, "👋 Hey! আমাকে যেকোনো ইউটিউব ভিডিওর লিংক পাঠাও।\n"
                          "আমি স্বয়ংক্রিয়ভাবে সেটিকে উচ্চমানের MP3 তে কনভার্ট করে পাঠিয়ে দেব।\n\n"
                          "✨ সম্পূর্ণ বিজ্ঞাপন মুক্ত এবং আনলিমিটেড।")

@bot.message_handler(func=lambda message: True)
def handle_youtube_link(message):
    # টেক্সটের ভেতরে কোনো ইউটিউব লিংক আছে কিনা চেক করা হচ্ছে
    match = re.search(YOUTUBE_REGEX, message.text)
    
    if match:
        extracted_url = match.group(0)
        msg = bot.reply_to(message, "⏳ ইউটিউব লিংক পাওয়া গেছে। অডিও প্রসেস করছি, একটু অপেক্ষা করো...")
        
        # Cobalt API থেকে অডিও লিংক নেওয়া হচ্ছে (ব্যাকআপ সিস্টেমসহ)
        mp3_direct_url = fetch_mp3_link(extracted_url)
        
        if mp3_direct_url:
            try:
                bot.edit_message_text("📤 কনভার্ট সম্পন্ন! টেলিগ্রামে আপলোড হচ্ছে...", message.chat.id, msg.message_id)
                
                # সরাসরি URL পাস করা হচ্ছে, সার্ভারের ডিস্ক বা র‍্যাম ব্যবহার হবে না
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
            bot.edit_message_text("❌ দুঃখিত, এই মুহূর্তে সবকটি ব্যাকআপ সার্ভার ব্যস্ত আছে। দয়া করে কিছুক্ষণ পর আবার চেষ্টা করো।", message.chat.id, msg.message_id)

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
    print("[+] YouTube MP3 Bot Started Successfully...")
    bot.infinity_polling()
            
