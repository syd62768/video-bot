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

# این تنظیمات باعث میشه یوتیوب فکر کنه درخواست از گوشی موبایل اومده نه سرور گیت‌هاب (ضد بلاک)
YDL_ANTI_BLOCK_OPTS = {
    'extractor_args': {'youtube': ['player_client=android,web_creator']},
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36'
    }
}

def handle_info():
    """مخصوص یوتیوب: استخراج سریع اطلاعات و ارسال دکمه‌های کیفیت"""
    ydl_opts = {
        'quiet': True, 
        'nocheckcertificate': True,
    }
    ydl_opts.update(YDL_ANTI_BLOCK_OPTS) # اعمال کدهای ضد بلاک یوتیوب
    
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
                "chat_id": str(CHAT_ID),
                "photo": thumb,
                "caption": f"🎥 <b>{title[:100]}</b>\n\n👇 <i>لطفا کیفیت مورد نظر را انتخاب کنید:</i>",
                "parse_mode": "HTML",
                "reply_to_message_id": str(REPLY_TO),
                "reply_markup": json.dumps(kb)
            })

    except Exception as e:
        error_txt = str(e).lower()
        if "sign in" in error_txt or "bot" in error_txt:
             edit_status("❌ <b>محدودیت یوتیوب:</b>\nلینک دارای محدودیت سنی است یا یوتیوب سرور را موقتا مسدود کرده است.")
        else:
             edit_status("❌ <b>خطا در استخراج اطلاعات:</b>\nلینک نامعتبر است یا ویدیو خصوصی است.")

def handle_download():
    """مرحله دانلود و ارسال نهایی (اینستاگرام مستقیما وارد این مرحله میشود)"""
    file_name = f"video_{int(time.time())}"
    
    ydl_opts = {
        'outtmpl': f"{file_name}.%(ext)s",
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
        'nocheckcertificate': True
    }
    ydl_opts.update(YDL_ANTI_BLOCK_OPTS) # اعمال کدهای ضد بلاک

    if QUALITY == 'mp3' or QUALITY == 'mp3320':
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
            # اینجا برای اینستاگرام سرعت دوبرابر میشه چون همزمان هم اطلاعات میگیره هم دانلود میکنه
            info = ydl.extract_info(URL, download=True)
            
            title = info.get('title', 'Video')
            platform = info.get('extractor', 'web').split(':')[0].capitalize()
            
            downloaded_file = f"{file_name}.{final_ext}"
            if not os.path.exists(downloaded_file):
                for f in os.listdir('.'):
                    if f.startswith(file_name):
                        downloaded_file = f
                        break
            
            if os.path.exists(downloaded_file):
                caption = f"📥 <b>{title[:70]}</b>\n🌐 پلتفرم: #{platform}\n\n🤖 @ndlVideobot"
                
                # ارسال فایل به تلگرام (بدون کیبورد شیشه‌ای زیر ویدیو)
                with open(downloaded_file, 'rb') as f:
                    if final_ext == "mp3":
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
            edit_status("❌ <b>خطا در پردازش فایل:</b>\nلینک مشکل دارد، خصوصی است یا یوتیوب مسدود کرده است.")

if __name__ == "__main__":
    if ACTION == "info":
        handle_info()
    elif ACTION == "download":
        handle_download()


