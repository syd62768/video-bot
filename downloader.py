import os
import requests
import json
import time
from yt_dlp import YoutubeDL

TG_TOKEN = os.environ.get("TG_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
URL = os.environ.get("URL")
REPLY_TO = os.environ.get("REPLY_TO")
WAIT_MSG_ID = os.environ.get("WAIT_MSG_ID")
ACTION = os.environ.get("ACTION", "info")
QUALITY = os.environ.get("QUALITY", "best")

def tg_request(method, payload, files=None):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/{method}"
    try:
        if files:
            r = requests.post(url, data=payload, files=files)
        else:
            r = requests.post(url, json=payload)
        return r.json()
    except Exception as e:
        return {"ok": False, "description": str(e)}

def edit_status(text):
    tg_request("editMessageText", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID), "text": text, "parse_mode": "HTML"})

# تنظیمات فوق پیشرفته برای دور زدن تحریم یوتیوب و سرعت بالا
YDL_OPTS_BASE = {
    'quiet': True,
    'no_warnings': True,
    'nocheckcertificate': True,
    'geo_bypass': True,
    # کلید اصلی برای دور زدن یوتیوب: استفاده نکردن از web
    'extractor_args': {
        'youtube': ['player_client=android,tv,ios']
    },
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
}

def handle_info():
    """مرحله استخراج کیفیت ها مخصوص یوتیوب"""
    ydl_opts = YDL_OPTS_BASE.copy()
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(URL, download=False)
            
            title = info.get('title', 'ویدیو یوتیوب')
            thumb = info.get('thumbnail')
            video_id = info.get('id')
            
            kb = {
                "inline_keyboard": [
                    [{"text": "🎬 360p", "callback_data": f"dl|360|{video_id}"}, {"text": "🎬 480p", "callback_data": f"dl|480|{video_id}"}],
                    [{"text": "🎬 720p", "callback_data": f"dl|720|{video_id}"}, {"text": "🎬 1080p", "callback_data": f"dl|1080|{video_id}"}],
                    [{"text": "🎧 mp3 (128)", "callback_data": f"dl|mp3|{video_id}"}, {"text": "🎧 mp3 (320)", "callback_data": f"dl|mp3320|{video_id}"}]
                ]
            }
            
            tg_request("deleteMessage", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID)})
            tg_request("sendPhoto", {
                "chat_id": str(CHAT_ID), "photo": thumb,
                "caption": f"🎥 <b>{title[:100]}</b>\n\n👇 <i>لطفا کیفیت مورد نظر را انتخاب کنید:</i>",
                "parse_mode": "HTML", "reply_to_message_id": str(REPLY_TO), "reply_markup": json.dumps(kb)
            })

    except Exception as e:
        error_txt = str(e).lower()
        if "sign in" in error_txt or "bot" in error_txt:
             edit_status("❌ <b>محدودیت یوتیوب:</b>\nلینک محدودیت سنی دارد یا سرور موقتاً بلاک شده است.")
        else:
             edit_status("❌ <b>خطا در استخراج اطلاعات:</b>\nلینک نامعتبر است.")

def get_direct_url(info):
    """جستجوی هوشمندانه برای یافتن لینک مستقیم (زیر 20 مگابایت برای تلگرام)"""
    url = info.get('url')
    if url:
        return url
        
    formats = info.get('formats', [])
    # پیدا کردن فرمت‌هایی که هم صدا و هم تصویر دارند
    valid_formats = [f for f in formats if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('ext') == 'mp4']
    
    if valid_formats:
        # مرتب‌سازی بر اساس سایز یا کیفیت
        valid_formats.sort(key=lambda x: x.get('filesize') or x.get('height') or 0, reverse=True)
        for fmt in valid_formats:
            # تلگرام فقط لینک های زیر 20 مگابایت را مستقیم آپلود می کند
            size = fmt.get('filesize') or 0
            if 0 < size < 20000000:
                return fmt.get('url')
        return valid_formats[0].get('url')
    return None

def handle_download():
    """پردازش و دانلود سریع ویدیو"""
    ydl_opts = YDL_OPTS_BASE.copy()
    
    file_name = f"video_{int(time.time())}"
    ydl_opts['outtmpl'] = f"{file_name}.%(ext)s"
    ydl_opts['merge_output_format'] = 'mp4'
    
    # استفاده از دانلودر موازی فوق سریع برای زمانی که لینک مستقیم جواب ندهد
    ydl_opts['external_downloader'] = 'aria2c'
    ydl_opts['external_downloader_args'] = ['-x', '16', '-s', '16', '-k', '1M']

    is_audio = QUALITY in ['mp3', 'mp3320']
    
    if is_audio:
        abr = '320' if QUALITY == 'mp3320' else '128'
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': abr}]
        final_ext = "mp3"
    elif QUALITY == 'best':
        ydl_opts['format'] = 'bestvideo[ext=mp4][filesize<=50M]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        final_ext = "mp4"
    else:
        ydl_opts['format'] = f'bestvideo[height<={QUALITY}][ext=mp4]+bestaudio[ext=m4a]/best[height<={QUALITY}][ext=mp4]/best'
        final_ext = "mp4"

    try:
        with YoutubeDL(ydl_opts) as ydl:
            # فقط استخراج لینک
            info = ydl.extract_info(URL, download=False)
            
            title = info.get('title', 'Video')
            platform = info.get('extractor', 'web').split(':')[0].capitalize()
            caption = f"📥 <b>{title[:70]}</b>\n🌐 پلتفرم: #{platform}\n\n🤖 @ndlVideobot"
            
            direct_url = get_direct_url(info)

            # تلاش برای ترفند سرعت نور (ارسال لینک مستقیم به سرورهای تلگرام)
            if not is_audio and direct_url:
                res = tg_request("sendVideo", {
                    "chat_id": str(CHAT_ID), "video": direct_url,
                    "caption": caption, "parse_mode": "HTML",
                    "reply_to_message_id": str(REPLY_TO)
                })
                
                if res.get("ok"):
                    # موفقیت در ارسال مستقیم!
                    tg_request("deleteMessage", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID)})
                    return
                else:
                    # اگر تلگرام لینک را نپذیرفت (مثلا بلاک بودن سرورهای IG یا حجم بالا)
                    edit_status("⚡ <b>لینک مستقیم پذیرفته نشد، در حال دانلود پرسرعت (Aria2)...</b>")

            # --- دانلود سنتی و پرسرعت روی سرور گیت هاب ---
            if not is_audio and (not direct_url or not res.get("ok")):
                edit_status("⏳ <b>در حال بارگیری سریع در سرور...</b>")
                
            ydl.download([URL])
            
            downloaded_file = f"{file_name}.{final_ext}"
            if not os.path.exists(downloaded_file):
                for f in os.listdir('.'):
                    if f.startswith(file_name):
                        downloaded_file = f
                        break
            
            if os.path.exists(downloaded_file):
                edit_status("🚀 <b>در حال آپلود فایل به تلگرام...</b>")
                with open(downloaded_file, 'rb') as f:
                    if is_audio:
                        res = tg_request("sendAudio", {
                            "chat_id": str(CHAT_ID), "caption": caption, "parse_mode": "HTML", 
                            "reply_to_message_id": str(REPLY_TO)
                        }, files={"audio": f})
                    else:
                        res = tg_request("sendVideo", {
                            "chat_id": str(CHAT_ID), "caption": caption, "parse_mode": "HTML", 
                            "reply_to_message_id": str(REPLY_TO),
                            "supports_streaming": True 
                        }, files={"video": f})
                
                if res.get("ok"):
                    tg_request("deleteMessage", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID)})
                else:
                    err_msg = res.get("description", "")
                    if "too large" in err_msg.lower():
                        tg_request("sendMessage", {"chat_id": str(CHAT_ID), "text": "❌ حجم فایل بیشتر از ۵۰ مگابایت است.", "reply_to_message_id": str(REPLY_TO)})
                    else:
                        tg_request("sendMessage", {"chat_id": str(CHAT_ID), "text": f"❌ خطا در ارسال: {err_msg}", "reply_to_message_id": str(REPLY_TO)})
                
                os.remove(downloaded_file)
            else:
                edit_status("❌ خطا: فایل استخراج نشد.")

    except Exception as e:
        err = str(e).lower()
        if "filesize" in err:
            edit_status("❌ <b>خطا:</b> حجم ویدیو بسیار بالاست.")
        else:
            edit_status("❌ <b>خطا در پردازش فایل:</b>\nلینک مشکل دارد، خصوصی است یا دسترسی مسدود شده است.")

if __name__ == "__main__":
    if ACTION == "info":
        handle_info()
    elif ACTION == "download":
        handle_download()

