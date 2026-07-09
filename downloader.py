
import os
import requests
import json
from yt_dlp import YoutubeDL

# دریافت اطلاعات از Worker
TG_TOKEN = os.environ.get("TG_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
URL = os.environ.get("URL")
REPLY_TO = os.environ.get("REPLY_TO")
WAIT_MSG_ID = os.environ.get("WAIT_MSG_ID")
ACTION_TYPE = os.environ.get("ACTION_TYPE", "info")
QUALITY = os.environ.get("QUALITY", "best")

# پروکسی ست شده توسط گیت‌هاب (Xray) خوانده میشود
PROXY = "http://127.0.0.1:10809"

def api_call(method, payload, files=None):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/{method}"
    if files:
        res = requests.post(url, data=payload, files=files)
    else:
        res = requests.post(url, json=payload)
    return res.json()

def edit_status(text):
    api_call("editMessageText", {"chat_id": CHAT_ID, "message_id": WAIT_MSG_ID, "text": text, "parse_mode": "HTML"})

def generate_youtube_buttons(video_id):
    # ساخت دکمه‌های شیشه‌ای دقیقا مشابه نمونه شما
    return json.dumps({
        "inline_keyboard": [
            [{"text": "🎬 دانلود با کیفیت 360p", "callback_data": f"dl|360|{video_id}"}],
            [{"text": "🎬 دانلود با کیفیت 480p", "callback_data": f"dl|480|{video_id}"}],
            [{"text": "🎬 دانلود با کیفیت 720p", "callback_data": f"dl|720|{video_id}"}],
            [{"text": "🎬 دانلود با کیفیت 1080p", "callback_data": f"dl|1080|{video_id}"}],
            [{"text": "🎧 دانلود صوتی (MP3)", "callback_data": f"dl|mp3|{video_id}"}]
        ]
    })

def process_info():
    """استخراج اطلاعات و نمایش کاور + دکمه (فقط برای یوتیوب) یا دانلود مستقیم (اینستاگرام)"""
    ydl_opts = {'proxy': PROXY, 'quiet': True, 'nocheckcertificate': True}
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(URL, download=False)
            platform = info.get('extractor', '').lower()
            
            # اگر یوتیوب باشد، پنل انتخاب کیفیت بفرست
            if 'youtube' in platform:
                title = info.get('title', 'ویدیو یوتیوب')
                thumb = info.get('thumbnail')
                video_id = info.get('id')
                
                caption = f"🎥 <b>{title[:100]}</b>\n\n👇 <i>لطفاً کیفیت مورد نظر خود را انتخاب کنید:</i>"
                
                # پاک کردن پیام لودینگ متنی
                api_call("deleteMessage", {"chat_id": CHAT_ID, "message_id": WAIT_MSG_ID})
                
                # ارسال عکس کاور با دکمه ها
                api_call("sendPhoto", {
                    "chat_id": CHAT_ID,
                    "photo": thumb,
                    "caption": caption,
                    "parse_mode": "HTML",
                    "reply_to_message_id": REPLY_TO,
                    "reply_markup": generate_youtube_buttons(video_id)
                })
            else:
                # اگر اینستاگرام یا پلتفرم دیگر بود، مستقیم بدون دکمه دانلود کن
                edit_status("⬇️ <b>اطلاعات یافت شد! در حال دانلود مستقیم...</b>")
                process_download(info.get('title', 'Video'), platform_name=platform.capitalize(), is_direct=True)

    except Exception as e:
        edit_status("❌ <b>خطا در دریافت اطلاعات:</b>\nلینک نامعتبر است یا ویدیو خصوصی می‌باشد.")

def process_download(title_override=None, platform_name="Youtube", is_direct=False):
    """دانلود ویدیو یا صوت با کیفیت انتخاب شده"""
    file_name = "media_file"
    
    ydl_opts = {
        'proxy': PROXY,
        'outtmpl': file_name + '.%(ext)s',
        'quiet': True,
        'nocheckcertificate': True,
        'merge_output_format': 'mp4' # برای جلوگیری از مشکل گیف شدن در تلگرام
    }

    # منطق انتخاب کیفیت
    if QUALITY == 'mp3':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
        final_ext = "mp3"
    elif QUALITY == 'best': # برای اینستاگرام و بقیه
        ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'
        final_ext = "mp4"
    else: # برای کیفیت‌های انتخابی یوتیوب (720, 1080 و ...)
        ydl_opts['format'] = f'bestvideo[height<={QUALITY}][ext=mp4]+bestaudio[ext=m4a]/best[height<={QUALITY}][ext=mp4]/best'
        final_ext = "mp4"

    try:
        with YoutubeDL(ydl_opts) as ydl:
            if not is_direct:
                info = ydl.extract_info(URL, download=False)
                title = info.get('title', 'ویدیو')
                platform_name = info.get('extractor', 'web').split(':')[0].capitalize()
            else:
                title = title_override

            ydl.download([URL])
            
            # پیدا کردن فایل خروجی دقیق
            downloaded_file = f"{file_name}.{final_ext}"
            
            caption = f"📥 <b>{title[:70]}</b>\n🌐 پلتفرم: #{platform_name}\n\n🤖 @ndlVideobot"
            reply_markup = json.dumps({"inline_keyboard": [[{"text": "🔗 لینک اصلی ویدیو", "url": URL}]]})

            with open(downloaded_file, 'rb') as f:
                if final_ext == "mp3":
                    api_call("sendAudio", {
                        "chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML", 
                        "reply_to_message_id": REPLY_TO, "reply_markup": reply_markup
                    }, files={"audio": f})
                else:
                    api_call("sendVideo", {
                        "chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML", 
                        "reply_to_message_id": REPLY_TO, "reply_markup": reply_markup,
                        "supports_streaming": True # <--- این خط جلوی گیف شدن ویدیو اینستا رو میگیره!
                    }, files={"video": f})

            # پاک کردن پیامِ لودینگ (یا عکس کاور) بعد از ارسال موفق
            api_call("deleteMessage", {"chat_id": CHAT_ID, "message_id": WAIT_MSG_ID})

            if os.path.exists(downloaded_file):
                os.remove(downloaded_file)

    except Exception as e:
        err = str(e).lower()
        if "filesize" in err or "too large" in err:
            api_call("sendMessage", {"chat_id": CHAT_ID, "text": "❌ حجم فایل بیشتر از ۵۰ مگابایت (محدودیت تلگرام) است.", "reply_to_message_id": REPLY_TO})
        else:
            api_call("sendMessage", {"chat_id": CHAT_ID, "text": f"❌ خطا در دانلود.", "reply_to_message_id": REPLY_TO})

if __name__ == "__main__":
    if ACTION_TYPE == "info":
        process_info()
    elif ACTION_TYPE == "download":
        process_download()

