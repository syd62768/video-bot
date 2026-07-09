import os
import requests
import json
import time
from yt_dlp import YoutubeDL

# اطلاعات دریافتی از GitHub Actions
TG_TOKEN = os.environ.get("TG_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
URL = os.environ.get("URL")
REPLY_TO = os.environ.get("REPLY_TO")
WAIT_MSG_ID = os.environ.get("WAIT_MSG_ID")
MODE = os.environ.get("MODE", "info") # info or download
QUALITY = os.environ.get("QUALITY", "best")

# پروکسی ست شده توسط Xray در گیت‌هاب
PROXY = "http://127.0.0.1:10809"

def api_call(method, payload, files=None):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/{method}"
    try:
        if files:
            res = requests.post(url, data=payload, files=files)
        else:
            res = requests.post(url, json=payload)
        return res.json()
    except Exception as e:
        return {"ok": False, "description": str(e)}

def edit_status(text):
    api_call("editMessageText", {"chat_id": CHAT_ID, "message_id": WAIT_MSG_ID, "text": text, "parse_mode": "HTML"})

def generate_youtube_buttons(video_id):
    return json.dumps({
        "inline_keyboard": [
            [{"text": "🎬 دانلود با کیفیت 360p", "callback_data": f"360|{video_id}"}],
            [{"text": "🎬 دانلود با کیفیت 480p", "callback_data": f"480|{video_id}"}],
            [{"text": "🎬 دانلود با کیفیت 720p", "callback_data": f"720|{video_id}"}],
            [{"text": "🎬 دانلود با کیفیت 1080p", "callback_data": f"1080|{video_id}"}],
            [{"text": "🎧 دانلود صوتی (MP3)", "callback_data": f"mp3|{video_id}"}]
        ]
    })

def handle_info():
    """مرحله اول: استخراج اطلاعات و نمایش دکمه‌ها (فقط برای یوتیوب)"""
    # تنظیمات پایه (بدون دانلود فایل)
    ydl_opts = {
        'proxy': PROXY, 
        'quiet': True, 
        'no_warnings': True,
        'nocheckcertificate': True
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(URL, download=False)
            platform = info.get('extractor', '').lower()
            
            # اگر یوتیوب باشد -> دکمه‌های کیفیت بفرست
            if 'youtube' in platform:
                title = info.get('title', 'YouTube Video')
                video_id = info.get('id')
                
                text = f"🎥 <b>{title[:100]}</b>\n\n👇 <i>لطفاً کیفیت مورد نظر را انتخاب کنید:</i>"
                
                # ویرایش پیام "در حال استخراج" به منوی انتخاب کیفیت
                api_call("editMessageText", {
                    "chat_id": CHAT_ID,
                    "message_id": WAIT_MSG_ID,
                    "text": text,
                    "parse_mode": "HTML",
                    "reply_markup": generate_youtube_buttons(video_id)
                })
            else:
                # اگر اینستاگرام یا سایت دیگر است -> مستقیم دانلود کن (بدون دکمه)
                edit_status("⬇️ <b>اطلاعات یافت شد! در حال دانلود مستقیم...</b>")
                handle_download(info, platform, is_direct=True)

    except Exception as e:
        error_msg = str(e).lower()
        if "sign in" in error_msg or "bot" in error_msg:
             edit_status("❌ <b>محدودیت یوتیوب:</b>\nپروکسی موقتا مسدود است.")
        else:
             edit_status(f"❌ <b>خطا در استخراج اطلاعات:</b>\nلینک نامعتبر است یا محتوا خصوصی می‌باشد.")

def handle_download(pre_info=None, platform_name="Youtube", is_direct=False):
    """مرحله دوم: دانلود و ارسال فایل نهایی"""
    file_name = f"video_{int(time.time())}"
    
    # تنظیمات پیشرفته و جلوگیری از گیف شدن فایل
    ydl_opts = {
        'proxy': PROXY,
        'outtmpl': file_name + '.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4', # این خط جلوی گیف شدن اینستا رو میگیره
        'nocheckcertificate': True
    }

    # تعیین فرمت بر اساس کیفیت انتخابی
    if QUALITY == 'mp3':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
        final_ext = "mp3"
    elif QUALITY == 'best' or is_direct:
        ydl_opts['format'] = 'bestvideo[ext=mp4][filesize<=50M]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        final_ext = "mp4"
    else:
        ydl_opts['format'] = f'bestvideo[height<={QUALITY}][ext=mp4]+bestaudio[ext=m4a]/best[height<={QUALITY}][ext=mp4]/best'
        final_ext = "mp4"

    try:
        with YoutubeDL(ydl_opts) as ydl:
            if not is_direct:
                info = ydl.extract_info(URL, download=False)
                title = info.get('title', 'Video')
                platform_name = info.get('extractor', 'web').split(':')[0].capitalize()
            else:
                title = pre_info.get('title', 'Video') if pre_info else 'Video'
                platform_name = platform_name.capitalize()

            ydl.download([URL])
            downloaded_file = f"{file_name}.{final_ext}"
            
            caption = f"📥 <b>{title[:70]}</b>\n🌐 پلتفرم: #{platform_name}\n\n🤖 @ndlVideobot"
            reply_markup = json.dumps({"inline_keyboard": [[{"text": "🔗 لینک اصلی ویدیو", "url": URL}]]})

            # ارسال فایل به تلگرام
            with open(downloaded_file, 'rb') as f:
                if final_ext == "mp3":
                    result = api_call("sendAudio", {
                        "chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML", 
                        "reply_to_message_id": REPLY_TO, "reply_markup": reply_markup
                    }, files={"audio": f})
                else:
                    result = api_call("sendVideo", {
                        "chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML", 
                        "reply_to_message_id": REPLY_TO, "reply_markup": reply_markup,
                        "supports_streaming": True # مهمترین پارامتر برای ویدیو شدن به جای گیف
                    }, files={"video": f})

            if result.get("ok"):
                api_call("deleteMessage", {"chat_id": CHAT_ID, "message_id": WAIT_MSG_ID})
            else:
                err_desc = result.get('description', '')
                if "Too Large" in err_desc or "entity too large" in err_desc.lower():
                     edit_status("❌ <b>خطا:</b> حجم فایل نهایی بیشتر از ۵۰ مگابایت است.")
                else:
                     edit_status(f"❌ <b>خطا در آپلود تلگرام.</b>")

            if os.path.exists(downloaded_file):
                os.remove(downloaded_file)

    except Exception as e:
        err = str(e).lower()
        if "filesize" in err:
            edit_status("❌ <b>خطا:</b> حجم ویدیو از محدودیت تلگرام بیشتر است.")
        else:
            edit_status("❌ <b>خطا در دانلود یا پردازش فایل.</b>")

if __name__ == "__main__":
    if MODE == "info":
        handle_info()
    elif MODE == "download":
        handle_download()

