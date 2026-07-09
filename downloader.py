import os
import requests
import json
import time
import random
import re
import traceback
from yt_dlp import YoutubeDL

TG_TOKEN = os.environ.get("TG_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
URL = os.environ.get("URL")
REPLY_TO = os.environ.get("REPLY_TO")
WAIT_MSG_ID = os.environ.get("WAIT_MSG_ID")
ACTION = os.environ.get("ACTION", "info")
QUALITY = os.environ.get("QUALITY", "best")

last_edit_time = 0

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

def edit_ui(text):
    """ویرایشگر هوشمند: خودش تشخیص می‌دهد پیام عکس است یا متن"""
    # ابتدا سعی میکنیم به عنوان متن ویرایش کنیم
    res = tg_request("editMessageText", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID), "text": text, "parse_mode": "HTML"})
    # اگر ارور داد یعنی پیام ما عکس(شیشه ای) است، پس کپشن را ویرایش میکنیم
    if not res.get("ok"):
        tg_request("editMessageCaption", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID), "caption": text, "parse_mode": "HTML"})

def clean_ansi(text):
    if not text: return ""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text).strip()

def download_progress_hook(d):
    """نوار سبز رنگ و پویای پیشرفت دانلود"""
    global last_edit_time
    if d['status'] == 'downloading':
        current_time = time.time()
        # آپدیت هر 3.5 ثانیه برای جلوگیری از بلاک شدن توسط تلگرام
        if current_time - last_edit_time > 3.5:
            percent_str = clean_ansi(d.get('_percent_str', '0%'))
            speed_str = clean_ansi(d.get('_speed_str', 'N/A'))
            eta_str = clean_ansi(d.get('_eta_str', 'N/A'))
            
            try:
                p = float(percent_str.replace('%', ''))
            except:
                p = 0
            
            filled = int(p / 10)
            bar = '🟩' * filled + '⬜️' * (10 - filled)
            
            text = f"⏳ <b>در حال دانلود به سرور...</b>\n\n{bar} {percent_str}\n🚀 سرعت: {speed_str}\n⏱ زمان باقی‌مانده: {eta_str}"
            edit_ui(text)
            last_edit_time = current_time

def setup_cookies():
    """سیستم ترمیم و مدیریت چرخه کوکی‌ها"""
    cookies = [
        os.environ.get("YT_COOKIE_1"),
        os.environ.get("YT_COOKIE_2"),
        os.environ.get("YT_COOKIE_3"),
        os.environ.get("YT_COOKIE_4")
    ]
    valid_cookies = [c for c in cookies if c and len(c) > 50]
    
    if valid_cookies:
        selected = random.choice(valid_cookies)
        # ترمیم فاصله ها و اینترهای خراب شده در گیت هاب
        selected = selected.replace('\\n', '\n')
        # اطمینان از وجود هدر Netscape
        if "# Netscape HTTP Cookie File" not in selected:
            selected = "# Netscape HTTP Cookie File\n" + selected
            
        with open("cookies.txt", "w", encoding="utf-8") as f:
            f.write(selected)
        return "cookies.txt"
    return None

def get_platform_opts(url, is_audio, quality):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'outtmpl': f"video_{int(time.time())}.%(ext)s",
        'merge_output_format': 'mp4',
        'progress_hooks': [download_progress_hook]
    }

    cookie_file = setup_cookies()
    if cookie_file:
        opts['cookiefile'] = cookie_file

    if is_audio:
        abr = '320' if quality == 'mp3320' else '128'
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': abr}]
    elif quality == 'best':
        opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    else:
        opts['format'] = f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}][ext=mp4]/best'

    if "youtube.com" in url or "youtu.be" in url:
        # استفاده از کلاینت TV برای عبور 100 درصدی از ربات یاب یوتیوب (تغییر مهم!)
        opts['extractor_args'] = {'youtube': ['player_client=tv,web']}
        if "shorts" in url: opts['format'] = 'best[ext=mp4]/best'
    elif "instagram.com" in url:
        opts['http_headers'] = {'User-Agent': 'Mozilla/5.0'}
    
    return opts

def handle_info():
    """پنل شیشه ای کیفیت های یوتیوب"""
    ydl_opts = get_platform_opts(URL, False, "best")
    
    try:
        edit_ui("🔍 در حال استخراج لیست کیفیت‌ها...")
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(URL, download=False)
            title = info.get('title', 'ویدیو')[:50]
            thumb = info.get('thumbnail')
            video_id = info.get('id')
            
            formats = info.get('formats', [])
            available_qualities = {}
            
            for f in formats:
                if f.get('vcodec') != 'none' and f.get('ext') == 'mp4':
                    h = f.get('height')
                    size = f.get('filesize') or f.get('filesize_approx') or 0
                    if h and h >= 144:
                        if h not in available_qualities or size > available_qualities[h]['size']:
                            available_qualities[h] = {'size': size, 'id': f.get('format_id')}
                            
            sorted_heights = sorted(available_qualities.keys())
            keyboard = []
            row = []
            
            for h in sorted_heights:
                size_mb = available_qualities[h]['size'] / (1024*1024)
                size_str = f"({size_mb:.1f}MB)" if size_mb > 0 else ""
                row.append({"text": f"🎬 {h}p {size_str}", "callback_data": f"dl|{h}|{video_id}"})
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row: keyboard.append(row)
                
            keyboard.append([
                {"text": "🎧 صوتی (128)", "callback_data": f"dl|mp3|{video_id}"},
                {"text": "🎵 صوتی (320)", "callback_data": f"dl|mp3320|{video_id}"}
            ])
            
            tg_request("deleteMessage", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID)})
            tg_request("sendPhoto", {
                "chat_id": str(CHAT_ID), "photo": thumb,
                "caption": f"🎥 <b>{title}</b>\n\n👇 <i>لطفاً کیفیت مورد نظر را انتخاب کنید:</i>",
                "parse_mode": "HTML", "reply_to_message_id": str(REPLY_TO), 
                "reply_markup": json.dumps({"inline_keyboard": keyboard})
            })

    except Exception as e:
        print(traceback.format_exc())
        edit_ui("❌ <b>خطا در ارتباط با یوتیوب</b>\nاحتمالاً ویدیو خصوصی است یا کوکی نیاز به آپدیت دارد.")

def handle_download():
    is_audio = QUALITY in ['mp3', 'mp3320']
    ydl_opts = get_platform_opts(URL, is_audio, QUALITY)
    
    try:
        edit_ui("🔍 در حال بررسی لینک...")
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(URL, download=False)
            title = info.get('title', 'Video')[:40]
            platform = info.get('extractor', 'web').split(':')[0].capitalize()
            caption = f"📥 <b>{title}</b>\n🌐 #{platform}"
            
            target_url = info.get('url')
            file_size = info.get('filesize') or info.get('filesize_approx') or 0

            # ارسال لینک مستقیم برای تلگرام (سرعت بالا - فقط زیر 20 مگابایت)
            if not is_audio and target_url and file_size > 0 and file_size < (19 * 1024 * 1024):
                res = tg_request("sendVideo", {
                    "chat_id": str(CHAT_ID), "video": target_url,
                    "caption": caption, "parse_mode": "HTML",
                    "reply_to_message_id": str(REPLY_TO)
                })
                if res.get("ok"):
                    tg_request("deleteMessage", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID)})
                    return
            
            # در صورت نیاز به دانلود (نوار سبز رنگ روشن می‌شود)
            ydl.process_ie_result(info, download=True)
            
            edit_ui("🚀 <b>در حال ارسال به تلگرام شما...</b>\n<i>لطفا کمی صبر کنید.</i>")
            
            downloaded_file = next((f for f in os.listdir('.') if f.startswith("video_") and (f.endswith('.mp4') or f.endswith('.mp3'))), None)
            
            if downloaded_file:
                with open(downloaded_file, 'rb') as f:
                    if is_audio:
                        res = tg_request("sendAudio", {"chat_id": str(CHAT_ID), "caption": caption, "parse_mode": "HTML", "reply_to_message_id": str(REPLY_TO)}, files={"audio": f})
                    else:
                        res = tg_request("sendVideo", {"chat_id": str(CHAT_ID), "caption": caption, "parse_mode": "HTML", "reply_to_message_id": str(REPLY_TO), "supports_streaming": True}, files={"video": f})
                
                if res.get("ok"):
                    tg_request("deleteMessage", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID)})
                else:
                    err_msg = res.get("description", "")
                    tg_request("sendMessage", {"chat_id": str(CHAT_ID), "text": f"❌ خطا در آپلود: {err_msg}", "reply_to_message_id": str(REPLY_TO)})
            else:
                edit_ui("❌ خطا: فایل تولید نشد.")

    except Exception as e:
        print(traceback.format_exc())
        err = str(e).lower()
        msg = "❌ حجم ویدیو بسیار بالاست." if "filesize" in err else "❌ خطا در پردازش یا قطعی موقت."
        edit_ui(msg)
        
    finally:
        for f in os.listdir('.'):
            if f.startswith("video_") or f == "cookies.txt":
                try: os.remove(f)
                except: pass

if __name__ == "__main__":
    try:
        if ACTION == "info":
            handle_info()
        elif ACTION == "download":
            handle_download()
    except Exception as main_e:
        print(traceback.format_exc())
        edit_ui("❌ خطای غیرمنتظره در سرور.")


