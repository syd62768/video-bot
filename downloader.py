import os
import requests
import json
import time
import traceback
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
        print(f"Telegram API Error: {e}")
        return {"ok": False, "description": str(e)}

def edit_status(text):
    tg_request("editMessageText", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID), "text": text, "parse_mode": "HTML"})

def edit_caption(text):
    tg_request("editMessageCaption", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID), "caption": text, "parse_mode": "HTML"})

def get_platform_opts(url, is_audio, quality):
    """تنظیمات اختصاصی yt-dlp بر اساس پلتفرم (شرط 10 تا 16)"""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'outtmpl': f"video_{int(time.time())}.%(ext)s",
        'merge_output_format': 'mp4',
    }

    # تعیین فرمت بر اساس درخواست
    if is_audio:
        abr = '320' if quality == 'mp3320' else '128'
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': abr}]
    elif quality == 'best':
        opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    else:
        opts['format'] = f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}][ext=mp4]/best'

    # کانفیگ اختصاصی پلتفرم ها
    if "youtube.com" in url or "youtu.be" in url:
        opts['extractor_args'] = {'youtube': ['player_client=android,web,ios']}
        if "shorts" in url:
            opts['format'] = 'best[ext=mp4]/best' # شورتس معمولاً فرمت یکپارچه بهتری دارد
    elif "instagram.com" in url:
        opts['http_headers'] = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    elif "tiktok.com" in url:
        opts['format'] = 'best[ext=mp4]/best' # برای تیک تاک فرمت سینگل بهتر است
    elif "reddit.com" in url:
        pass
    elif "twitter.com" in url or "x.com" in url:
        pass
    elif "facebook.com" in url or "fb.watch" in url:
        pass

    return opts

def get_file_size(fmt):
    """بررسی دقیق حجم فایل با هر دو پارامتر (شرط 3)"""
    return fmt.get('filesize') or fmt.get('filesize_approx') or 0

def handle_info():
    """استخراج داینامیک کیفیت ها برای یوتیوب (شرط 2)"""
    ydl_opts = get_platform_opts(URL, False, "best")
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(URL, download=False)
            title = info.get('title', 'ویدیو')[:40] # کوتاه کردن عنوان (شرط 19)
            thumb = info.get('thumbnail')
            video_id = info.get('id')
            
            formats = info.get('formats', [])
            available_heights = set()
            
            # پیدا کردن کیفیت های واقعی و موجود
            for f in formats:
                if f.get('vcodec') != 'none' and f.get('ext') == 'mp4':
                    h = f.get('height')
                    if h and h >= 144:
                        available_heights.add(h)
                        
            sorted_heights = sorted(list(available_heights))
            keyboard = []
            
            # ساخت داینامیک دکمه ها
            row = []
            for h in sorted_heights:
                row.append({"text": f"🎬 {h}p", "callback_data": f"dl|{h}|{video_id}"})
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
                
            keyboard.append([
                {"text": "🎧 mp3 (128)", "callback_data": f"dl|mp3|{video_id}"},
                {"text": "🎧 mp3 (320)", "callback_data": f"dl|mp3320|{video_id}"}
            ])
            
            tg_request("deleteMessage", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID)})
            tg_request("sendPhoto", {
                "chat_id": str(CHAT_ID), "photo": thumb,
                "caption": f"🎥 <b>{title}</b>\n\n👇 <i>لطفا کیفیت را انتخاب کنید:</i>",
                "parse_mode": "HTML", "reply_to_message_id": str(REPLY_TO), 
                "reply_markup": json.dumps({"inline_keyboard": keyboard})
            })

    except Exception as e:
        print(traceback.format_exc()) # ثبت خطا در گیت هاب (شرط 8)
        edit_status("❌ خطا در استخراج اطلاعات از یوتیوب.")

def handle_download():
    """پردازش هوشمند: اول لینک مستقیم، اگر نشد دانلود بدون استخراج مجدد (شرط 5 و 6 و 17)"""
    is_audio = QUALITY in ['mp3', 'mp3320']
    ydl_opts = get_platform_opts(URL, is_audio, QUALITY)
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            if not is_audio:
                edit_caption("🔍 در حال استخراج اطلاعات...") if 'dl|' in QUALITY else edit_status("🔍 در حال استخراج اطلاعات...")
            
            # 1. استخراج اطلاعات بدون دانلود
            info = ydl.extract_info(URL, download=False)
            title = info.get('title', 'Video')[:40]
            platform = info.get('extractor', 'web').split(':')[0].capitalize()
            caption = f"📥 <b>{title}</b>\n🌐 #{platform}"
            
            # یافتن بهترین فرمت انتخاب شده
            target_url = None
            file_size = 0
            
            if 'requested_formats' in info: # فرمت های ویدیو + صدا (مرج شده)
                for f in info['requested_formats']:
                    file_size += get_file_size(f)
            else:
                target_url = info.get('url')
                file_size = get_file_size(info)

            # 2. تلاش برای ارسال با لینک مستقیم (زیر 20 مگابایت)
            if not is_audio and target_url and file_size < (20 * 1024 * 1024):
                res = tg_request("sendVideo", {
                    "chat_id": str(CHAT_ID), "video": target_url,
                    "caption": caption, "parse_mode": "HTML",
                    "reply_to_message_id": str(REPLY_TO)
                })
                if res.get("ok"):
                    tg_request("deleteMessage", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID)})
                    return # پایان موفقیت آمیز با لینک مستقیم
            
            # 3. در صورت شکست لینک مستقیم یا فایل بزرگ (دانلود توسط سرور)
            # نکته کلیدی شرط 5: از ydl.process_ie_result استفاده میکنیم تا دوباره extract نکند
            if not is_audio:
                edit_caption("⬇️ در حال دانلود به سرور...") if 'dl|' in QUALITY else edit_status("⬇️ در حال دانلود به سرور...")
                
            ydl.process_ie_result(info, download=True)
            
            # 4. پیدا کردن فایل و ارسال
            downloaded_file = None
            for f in os.listdir('.'):
                if f.startswith("video_") and (f.endswith('.mp4') or f.endswith('.mp3')):
                    downloaded_file = f
                    break
            
            if downloaded_file:
                if not is_audio:
                     edit_caption("🚀 در حال آپلود به تلگرام...") if 'dl|' in QUALITY else edit_status("🚀 در حال آپلود به تلگرام...")
                     
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
                    tg_request("sendMessage", {"chat_id": str(CHAT_ID), "text": f"❌ خطا در ارسال: {err_msg}", "reply_to_message_id": str(REPLY_TO)})
            else:
                edit_status("❌ خطا: فایل تولید نشد.")

    except Exception as e:
        print(traceback.format_exc()) # ثبت خطا در لاگ گیت هاب
        err = str(e).lower()
        if "filesize" in err:
             msg = "❌ حجم ویدیو بسیار بالاست."
        else:
             msg = "❌ خطا در پردازش یا محدودیت پلتفرم مبدا."
        
        edit_caption(msg) if 'dl|' in QUALITY else edit_status(msg)
        
    finally:
        # پاکسازی تمام فایل های تولید شده (شرط 22)
        for f in os.listdir('.'):
            if f.startswith("video_"):
                try:
                    os.remove(f)
                except:
                    pass

if __name__ == "__main__":
    if ACTION == "info":
        handle_info()
    elif ACTION == "download":
        handle_download()


