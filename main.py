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

# ===================== Y2MATE BACKEND SCRAPER =====================
def fetch_mp3_link(youtube_url):
    """Y2Mate ব্যাকএন্ড স্ক্র্যাপ করে সরাসরি হাই-স্পিড MP3 ডাউনলোড লিংক বের করবে"""
    # ১১ অক্ষরের ভিডিও আইডি এক্সট্রাক্ট করা হচ্ছে
    video_id_match = re.search(r'(?:v=|\/|embed\/|shorts\/)([0-9A-Za-z_-]{11})', youtube_url)
    if not video_id_match:
        return None
    video_id = video_id_match.group(1)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.y2mate.com/"
    }
    
    try:
        # স্টেপ ১: ভিডিও অ্যানালাইসিস করে টোকেন নেওয়া
        analyze_url = "https://www.y2mate.com/mates/enMates/analyzeV2/ajax"
        payload = {
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "q_auto": 0,
            "ajax": 1
        }
        
        res = requests.post(analyze_url, data=payload, headers=headers, timeout=12)
        if res.status_code == 200:
            data = res.json()
            links = data.get("links", {})
            mp3_data = links.get("mp3", {}) or links.get("audio", {})
            
            if mp3_data:
                # প্রথম উপলব্ধ অডিও কোয়ালিটির (যেমন ১২৮kbps) 'k' টোকেন নেওয়া হচ্ছে
                first_key = list(mp3_data.keys())[0]
                k_token = mp3_data[first_key].get("k")
                
                # স্টেপ ২: টোকেন ব্যবহার করে ডিরেক্ট ডাউনলোড লিংক জেনারেট করা
                convert_url = "https://www.y2mate.com/mates/enMates/convertV2/ajax"
                convert_payload = {
                    "vid": video_id,
                    "k": k_token
                }
                
                res_conv = requests.post(convert_url, data=convert_payload, headers=headers, timeout=12)
                if res_conv.status_code == 200:
                    conv_data = res_conv.json()
                    if conv_data.get("status") == "ok":
                        return conv_data.get("dlink") # ডিরেক্ট ডাউনলোড ইউআরএল
                        
    except Exception as e:
        print(f"[-] Scraper Error: {e}")
        
    return None

# ===================== TELEGRAM HANDLER =====================
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.reply_to(message, "👋 হ্যালো! আমাকে যেকোনো ইউটিউব বা ইউটিউব মিউজিকের লিংক পাঠাও।\n"
                          "আমি সরাসরি হাই-স্পিড সার্ভার থেকে সেটিকে MP3 তে কনভার্ট করে পাঠিয়ে দেব।\n\n"
                          "✨ রেন্ডার ২৪/৭ মোডে সম্পূর্ণ বিজ্ঞাপন মুক্ত সেবা।")

@bot.message_handler(func=lambda message: True)
def handle_youtube_link(message):
    match = re.search(YOUTUBE_REGEX, message.text)
    
    if match:
        extracted_url = match.group(0)
        msg = bot.reply_to(message, "⏳ লিংক প্রসেস করা হচ্ছে... একটু অপেক্ষা করো।")
        
        # স্ক্র্যাপার রান করা হচ্ছে
        mp3_direct_url = fetch_mp3_link(extracted_url)
        
        if mp3_direct_url:
            try:
                bot.edit_message_text("📤 কনভার্ট সম্পন্ন! টেলিগ্রামে অডিও পাঠানো হচ্ছে...", message.chat.id, msg.message_id)
                
                # সরাসরি অডিও ইউআরএল টেলিগ্রামে সেন্ড (সার্ভার লোড ০%)
                bot.send_audio(
                    chat_id=message.chat.id, 
                    audio=mp3_direct_url, 
                    title="Audio Tracks", 
                    performer="Cloud High-Speed Downloader",
                    reply_to_message_id=message.message_id
                )
                bot.delete_message(message.chat.id, msg.message_id)
                
            except Exception as e:
                print(f"Telegram Upload Error: {e}")
                bot.edit_message_text("❌ ফাইলটি টেলিগ্রামে পাঠাতে সমস্যা হয়েছে। ভিডিওর সাইজ বা ডিউরেশন অতিরিক্ত বড় হতে পারে।", message.chat.id, msg.message_id)
        else:
            bot.edit_message_text("❌ অডিও লিংক জেনারেট করা যায়নি। দয়া করে লিংকটি আবার চেক করো বা অন্য কোনো লিংক ট্রাই করো।", message.chat.id, msg.message_id)

# ===================== KEEP ALIVE SERVER =====================
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"24/7 Render Stream Active!")

def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(('0.0.0.0', port), DummyServer).serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()

# ===================== RUN =====================
if __name__ == "__main__":
    print("[+] Scraper-Based YT MP3 Bot Started for Render 24/7...")
    bot.infinity_polling()
    
