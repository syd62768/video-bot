import os
import requests
import json
from yt_dlp import YoutubeDL

# اطلاعات دریافتی
TG_TOKEN = os.environ.get("TG_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
URL = os.environ.get("URL")
REPLY_TO = os.environ.get("REPLY_TO")
WAIT_MSG_ID = os.environ.get("WAIT_MSG_ID")

def edit_status(text):
    requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/editMessageText",
        json={"chat_id": CHAT_ID, "message_id": WAIT_MSG_ID, "text": text, "parse_mode": "HTML"}
    )

def send_video(file_path, title, platform):
    caption = f"📥 <b>{title[:70]}</b>\n🌐 پلتفرم: #{platform}\n\n🤖 @ndlVideobot"
    
    # دکمه شیشه‌ای زیر ویدیو
    reply_markup = json.dumps({
        "inline_keyboard": [
            [{"text": "🔗 لینک اصلی ویدیو", "url": URL}]
        ]
    })
    
    with open(file_path, 'rb') as video:
        response = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendVideo",
            data={
                "chat_id": CHAT_ID, 
                "caption": caption, 
                "parse_mode": "HTML", 
                "reply_to_message_id": REPLY_TO,
                "reply_markup": reply_markup
            },
            files={"video": video}
        )
        return response.json()

if __name__ == "__main__":
    edit_status("🔍 [۲/۴] <b>سرور متصل شد! در حال استخراج اطلاعات ویدیو...</b>")
    
    file_name = "video.mp4"
    
    # تنظیمات پیشرفته برای دور زدن محدودیت‌های یوتیوب و انتخاب کیفیت مناسب تلگرام
    ydl_opts = {
        'format': 'best[ext=mp4][filesize<=50M]/bestvideo[ext=mp4][filesize<=50M]+bestaudio[ext=m4a]/best',
        'outtmpl': file_name,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
        'nocheckcertificate': True,
        'socket_timeout': 30,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            # گرفتن اطلاعات (بدون دانلود)
            info = ydl.extract_info(URL, download=False)
            title = info.get('title', 'ویدیو')
            platform_name = info.get('extractor', 'web').split(':')[0].capitalize()
            
            edit_status(f"⬇️ [۳/۴] <b>اطلاعات یافت شد! در حال دانلود از {platform_name}...</b>\n<i>(بسته به حجم ویدیو ممکن است طول بکشد)</i>")
            
            # دانلود واقعی
            ydl.download([URL])
            
            edit_status("⬆️ [۴/۴] <b>دانلود تکمیل شد! در حال ارسال به تلگرام...</b>")
            
            # ارسال به تلگرام
            result = send_video(file_name, title, platform_name)
            
            if result.get("ok"):
                # پاک کردن پیام لودینگ پس از ارسال موفق
                requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/deleteMessage", 
                              json={"chat_id": CHAT_ID, "message_id": WAIT_MSG_ID})
            else:
                edit_status(f"❌ <b>خطا در آپلود:</b>\nحجم فایل نهایی بیشتر از ۵۰ مگابایت است یا فرمت پشتیبانی نمی‌شود.")

    except Exception as e:
        error_msg = str(e).lower()
        if "filesize" in error_msg:
            edit_status("❌ <b>خطا:</b> حجم ویدیو از محدودیت تلگرام (۵۰ مگابایت) بیشتر است.")
        elif "sign in" in error_msg or "bot" in error_msg:
            edit_status("❌ <b>محدودیت پلتفرم:</b>\nیوتیوب موقتاً آی‌پی سرور را مسدود کرده است. لینک دیگری امتحان کنید.")
        else:
            edit_status("❌ <b>خطا در استخراج!</b>\n\n- پیج/ویدیو خصوصی است.\n- ویدیو حذف شده است.\n- لینک نامعتبر است.")
    
    finally:
        # پاکسازی صد در صدی فایل از رم سرور مجازی
        if os.path.exists(file_name):
            os.remove(file_name)


