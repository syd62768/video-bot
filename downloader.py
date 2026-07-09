import os
import requests
from yt_dlp import YoutubeDL

# دریافت اطلاعات ارسال شده از طرف کلودفلر
TG_TOKEN = os.environ.get("TG_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
URL = os.environ.get("URL")
REPLY_TO = os.environ.get("REPLY_TO")
WAIT_MSG_ID = os.environ.get("WAIT_MSG_ID")

def edit_telegram_message(text):
    requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/editMessageText",
        json={"chat_id": CHAT_ID, "message_id": WAIT_MSG_ID, "text": text, "parse_mode": "HTML"}
    )

def send_telegram_video(file_path, caption):
    with open(file_path, 'rb') as video:
        response = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendVideo",
            data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML", "reply_to_message_id": REPLY_TO},
            files={"video": video}
        )
        return response.json()

if __name__ == "__main__":
    edit_telegram_message("✅ <b>سرور پایتون متصل شد!</b> در حال استخراج ویدیو...")
    
    file_name = "downloaded_video.mp4"
    
    # تنظیمات حرفه‌ای yt-dlp برای تلگرام (حداکثر 50 مگابایت)
    ydl_opts = {
        'format': 'best[ext=mp4][filesize<=50M]/bestvideo[ext=mp4][filesize<=50M]+bestaudio[ext=m4a]/best',
        'outtmpl': file_name,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            # استخراج اطلاعات
            info = ydl.extract_info(URL, download=True)
            title = info.get('title', 'Video')
            platform = info.get('extractor', 'Unknown')
            
            edit_telegram_message("⬆️ <b>ویدیو دریافت شد!</b> در حال آپلود به تلگرام...")
            
            # ارسال ویدیو به کاربر
            caption = f"📥 <b>{title[:60]}...</b>\n🌐 پلتفرم: {platform}\n\n🤖 @ndlVideobot"
            result = send_telegram_video(file_name, caption)
            
            # بررسی موفقیت ارسال
            if result.get("ok"):
                # پاک کردن پیام "لطفا صبر کنید"
                requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/deleteMessage", 
                              json={"chat_id": CHAT_ID, "message_id": WAIT_MSG_ID})
            else:
                edit_telegram_message(f"❌ خطا در آپلود تلگرام: فایل احتمالاً مشکل دارد.")

    except Exception as e:
        error_msg = str(e)
        if "filesize" in error_msg.lower():
            edit_telegram_message("❌ <b>خطا:</b> حجم این ویدیو بیشتر از حد مجاز ربات‌های تلگرام (۵۰ مگابایت) است.")
        else:
            edit_telegram_message("❌ <b>خطا در استخراج ویدیو!</b>\n\nدلایل احتمالی:\n۱. پیج خصوصی (Private) است.\n۲. لینک نامعتبر یا ویدیو حذف شده است.")
    
    finally:
        # پاک کردن فایل از روی سرور گیت‌هاب (تمیزکاری)
        if os.path.exists(file_name):
            os.remove(file_name)


