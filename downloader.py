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
            # ارسال فایل نیاز به data دارد نه json
            r = requests.post(url, data=payload, files=files)
        else:
            r = requests.post(url, json=payload)
        return r.json()
    except Exception as e:
        return {"ok": False, "description": str(e)}

def edit_status(text):
    tg_request("editMessageText", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID), "text": text, "parse_mode": "HTML"})

def handle_info():
    """استخراج اطلاعات اولیه: اگر یوتیوب بود دکمه میده، در غیر این صورت مستقیم دانلود میکنه"""
    ydl_opts = {
        'quiet': True, 
        'nocheckcertificate': True,
        'geo_bypass': True
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(URL, download=False)
            extractor = info.get('extractor', '').lower()
            
            if 'youtube' in extractor:
                title = info.get('title', 'ویدیو یوتیوب')
                thumb = info.get('thumbnail')
                video_id = info.get('id')
                
                # کیبورد شیشه ای دقیقاً مشابه تصویر ربات رقیب
                kb = {
                    "inline_keyboard": [
                        [{"text": "🎬 دانلود با کیفیت 360p", "callback_data": f"dl|360|{video_id}"}],
                        [{"text": "🎬 دانلود با کیفیت 480p", "callback_data": f"dl|480|{video_id}"}],
                        [{"text": "🎬 دانلود با کیفیت 720p", "callback_data": f"dl|720|{video_id}"}],
                        [{"text": "🎬 دانلود با کیفیت 1080p", "callback_data": f"dl|1080|{video_id}"}],
                        [{"text": "🎧 mp3 - (128)", "callback_data": f"dl|mp3|{video_id}"}, {"text": "🎧 mp3 - (320)", "callback_data": f"dl|mp3320|{video_id}"}]
                    ]
                }
                
                # حذف پیام متنی قبلی
                tg_request("deleteMessage", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID)})
                
                # ارسال کاور و دکمه ها
                tg_request("sendPhoto", {
                    "chat_id": str(CHAT_ID),
                    "photo": thumb,
                    "caption": f"🎥 <b>{title[:100]}</b>\n\n👇 <i>هنوزم این اسنایپ هارو جای دیگه نمیبینید (انتخاب کیفیت)</i>",
                    "parse_mode": "HTML",
                    "reply_to_message_id": str(REPLY_TO),
                    "reply_markup": json.dumps(kb)
                })
            else:
                edit_status("⬇️ <b>اطلاعات یافت شد! در حال دانلود مستقیم...</b>")
                handle_download(info, is_direct=True)

    except Exception as e:
        edit_status("❌ <b>خطا در استخراج اطلاعات:</b>\nلینک نامعتبر است، ویدیو خصوصی است یا نیاز به لاگین دارد.")

def handle_download(pre_info=None, is_direct=False):
    """دانلود و ارسال ویدیو یا موزیک"""
    file_name = f"video_{int(time.time())}"
    
    ydl_opts = {
        'outtmpl': f"{file_name}.%(ext)s",
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4', # اجبار فرمت به MP4 برای جلوگیری از خطای تلگرام
        'nocheckcertificate': True,
        'geo_bypass': True
    }

    if QUALITY == 'mp3' or QUALITY == 'mp3320':
        abr = '320' if QUALITY == 'mp3320' else '128'
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': abr}]
        final_ext = "mp3"
    elif QUALITY == 'best' or is_direct:
        ydl_opts['format'] = 'bestvideo[ext=mp4][filesize<=50M]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        final_ext = "mp4"
    else:
        ydl_opts['format'] = f'bestvideo[height<={QUALITY}][ext=mp4]+bestaudio[ext=m4a]/best[height<={QUALITY}][ext=mp4]/best'
        final_ext = "mp4"

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = pre_info if is_direct else ydl.extract_info(URL, download=False)
            title = info.get('title', 'Video')
            platform = info.get('extractor', 'web').split(':')[0].capitalize()
            
            ydl.download([URL])
            
            # پیدا کردن فایل خروجی دقیق در سیستم
            downloaded_file = f"{file_name}.{final_ext}"
            if not os.path.exists(downloaded_file):
                for f in os.listdir('.'):
                    if f.startswith(file_name):
                        downloaded_file = f
                        break
            
            if os.path.exists(downloaded_file):
                caption = f"📥 <b>{title[:70]}</b>\n🌐 پلتفرم: #{platform}\n\n🤖 @ndlVideobot"
                kb = {"inline_keyboard": [[{"text": "🔗 لینک اصلی ویدیو", "url": URL}]]}
                
                with open(downloaded_file, 'rb') as f:
                    if final_ext == "mp3":
                        res = tg_request("sendAudio", {
                            "chat_id": str(CHAT_ID), "caption": caption, "parse_mode": "HTML", 
                            "reply_to_message_id": str(REPLY_TO), "reply_markup": json.dumps(kb)
                        }, files={"audio": f})
                    else:
                        # برای ویدیوهای اینستاگرام، supports_streaming: "true" جلوی گیف شدن را کامل میگیرد
                        res = tg_request("sendVideo", {
                            "chat_id": str(CHAT_ID), "caption": caption, "parse_mode": "HTML", 
                            "reply_to_message_id": str(REPLY_TO), "reply_markup": json.dumps(kb),
                            "supports_streaming": "true" 
                        }, files={"video": f})
                
                if res.get("ok"):
                    tg_request("deleteMessage", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID)})
                else:
                    err_msg = res.get("description", "")
                    if "too large" in err_msg.lower():
                        tg_request("sendMessage", {"chat_id": str(CHAT_ID), "text": "❌ حجم فایل بیشتر از ۵۰ مگابایت است.", "reply_to_message_id": str(REPLY_TO)})
                    else:
                        tg_request("sendMessage", {"chat_id": str(CHAT_ID), "text": f"❌ خطا در ارسال به تلگرام: {err_msg}", "reply_to_message_id": str(REPLY_TO)})
                
                os.remove(downloaded_file)
            else:
                edit_status("❌ خطا: فایل از سرور استخراج نشد.")

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


