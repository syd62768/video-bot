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

# متدهای ضد تحریم بسیار قوی برای یوتیوب (فریب سرور)
YDL_OPTS_BASE = {
    'quiet': True,
    'no_warnings': True,
    'nocheckcertificate': True,
    'geo_bypass': True,
    'extractor_args': {
        'youtube': ['player_client=ios,android,web']
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
                    [{"text": "🎬 دانلود با کیفیت 360p", "callback_data": f"dl|360|{video_id}"}],
                    [{"text": "🎬 دانلود با کیفیت 480p", "callback_data": f"dl|480|{video_id}"}],
                    [{"text": "🎬 دانلود با کیفیت 720p", "callback_data": f"dl|720|{video_id}"}],
                    [{"text": "🎬 دانلود با کیفیت 1080p", "callback_data": f"dl|1080|{video_id}"}],
                    [{"text": "🎧 mp3 - (128)", "callback_data": f"dl|mp3|{video_id}"}, {"text": "🎧 mp3 - (320)", "callback_data": f"dl|mp3320|{video_id}"}]
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
             edit_status("❌ <b>محدودیت یوتیوب:</b>\nلینک دارای محدودیت سنی است یا یوتیوب سرور را مسدود کرده است.")
        else:
             edit_status("❌ <b>خطا در استخراج اطلاعات:</b>\nلینک نامعتبر است یا ویدیو خصوصی است.")

def handle_download():
    """مرحله دانلود و پردازش با قابلیت ارسال آنی (Lightning Speed)"""
    ydl_opts = YDL_OPTS_BASE.copy()
    
    file_name = f"video_{int(time.time())}"
    ydl_opts['outtmpl'] = f"{file_name}.%(ext)s"
    ydl_opts['merge_output_format'] = 'mp4'

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
            # فقط اطلاعات رو میگیریم، دانلود نمیکنیم!
            info = ydl.extract_info(URL, download=False)
            
            title = info.get('title', 'Video')
            platform = info.get('extractor', 'web').split(':')[0].capitalize()
            caption = f"📥 <b>{title[:70]}</b>\n🌐 پلتفرم: #{platform}\n\n🤖 @ndlVideobot"
            
            # --- ترفند سرعت نور (URL Pass-through) ---
            # بررسی میکنیم آیا میتونیم مستقیم لینک رو بدیم تلگرام دانلود کنه یا نه
            if not is_audio:
                direct_url = info.get('url')
                # اگر لینک مستقیم نبود (مثل یوتیوب) بهترین فرمت رو پیدا کن
                if not direct_url and 'formats' in info:
                    best_fmt = next((f for f in info['formats'] if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('ext') == 'mp4'), None)
                    if best_fmt:
                        direct_url = best_fmt.get('url')
                
                if direct_url:
                    # ارسال لینک مخفی مستقیم به سرورهای تلگرام (در کسری از ثانیه)
                    res = tg_request("sendVideo", {
                        "chat_id": str(CHAT_ID), "video": direct_url,
                        "caption": caption, "parse_mode": "HTML",
                        "reply_to_message_id": str(REPLY_TO),
                        "supports_streaming": "true" 
                    })
                    if res.get("ok"):
                        # اگر موفق بود، پیام لودینگ رو پاک کن و تمام! (بدون مصرف حجم سرور ما)
                        tg_request("deleteMessage", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID)})
                        return

            # --- دانلود سنتی (اگر ترفند سرعت نور جواب نداد یا درخواست موزیک بود) ---
            if not is_audio:
                edit_status("⏳ <b>در حال بارگیری فایل در سرور...</b>")
                
            ydl.download([URL])
            
            downloaded_file = f"{file_name}.{final_ext}"
            if not os.path.exists(downloaded_file):
                for f in os.listdir('.'):
                    if f.startswith(file_name):
                        downloaded_file = f
                        break
            
            if os.path.exists(downloaded_file):
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
                            "supports_streaming": "true" 
                        }, files={"video": f})
                
                if res.get("ok"):
                    tg_request("deleteMessage", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID)})
                else:
                    err_msg = res.get("description", "")
                    if "too large" in err_msg.lower():
                        tg_request("sendMessage", {"chat_id": str(CHAT_ID), "text": "❌ حجم فایل بیشتر از ۵۰ مگابایت است.", "reply_to_message_id": str(REPLY_TO)})
                    else:
                        tg_request("sendMessage", {"chat_id": str(CHAT_ID), "text": f"❌ خطا در ارسال به تلگرام", "reply_to_message_id": str(REPLY_TO)})
                
                os.remove(downloaded_file)
            else:
                edit_status("❌ خطا: فایل استخراج نشد.")

    except Exception as e:
        err = str(e).lower()
        if "filesize" in err:
            edit_status("❌ <b>خطا:</b> حجم ویدیو از ۵۰ مگابایت بیشتر است.")
        else:
            edit_status("❌ <b>خطا در پردازش فایل:</b>\nلینک مشکل دارد یا دانلود مسدود شده است.")

if __name__ == "__main__":
    if ACTION == "info":
        handle_info()
    elif ACTION == "download":
        handle_download()


