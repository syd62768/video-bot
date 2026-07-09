import os
import requests
import json
import time
import random
import re
import traceback
import threading
from yt_dlp import YoutubeDL

TG_TOKEN = os.environ.get("TG_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
URL = os.environ.get("URL")
REPLY_TO = os.environ.get("REPLY_TO")
WAIT_MSG_ID = os.environ.get("WAIT_MSG_ID")
ACTION = os.environ.get("ACTION", "info")
QUALITY = os.environ.get("QUALITY", "best")

last_edit_time = 0
stop_fake_progress = False

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
    """ویرایش پیام (پشتیبانی از کپشن یا متن ساده)"""
    res = tg_request("editMessageText", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID), "text": text, "parse_mode": "HTML"})
    if not res.get("ok"):
        tg_request("editMessageCaption", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID), "caption": text, "parse_mode": "HTML"})

def clean_ansi(text):
    if not text: return ""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text).strip()

def fake_progress_bar(text_prefix):
    """نوار لودینگ پویا برای زمان استخراج اطلاعات"""
    global stop_fake_progress
    for i in range(1, 30):
        if stop_fake_progress:
            break
        percent = min(99, i * 3)
        filled = int(percent / 10)
        bar = '█' * filled + '░' * (10 - filled)
        
        edit_ui(f"⏳ <b>{text_prefix}</b>\n\n{bar} {percent}%\n<i>در حال ارتباط با سرورهای پردازش...</i>")
        time.sleep(2)

def download_progress_hook(d):
    """نوار پیشرفت واقعی و جذاب هنگام دانلود"""
    global last_edit_time
    if d['status'] == 'downloading':
        current_time = time.time()
        if current_time - last_edit_time > 3.0:
            percent_str = clean_ansi(d.get('_percent_str', '0%'))
            speed_str = clean_ansi(d.get('_speed_str', 'N/A'))
            
            try:
                p = float(percent_str.replace('%', ''))
            except:
                p = 0
            
            filled = int(p / 10)
            bar = '█' * filled + '░' * (10 - filled)
            
            quality_text = QUALITY if QUALITY != 'best' else 'بهترین'
            if 'mp3' in QUALITY: quality_text = 'صوتی MP3'
            else: quality_text = f"{quality_text}p"
            
            text = (
                f"⏳ <b>در حال پردازش ویدیو...</b>\n\n"
                f"🔹 کیفیت: {quality_text}\n"
                f"🔹 استخراج و آماده‌سازی فایل\n\n"
                f"📥 در حال دانلود در سرور:\n"
                f"{bar} {percent_str}\n"
                f"🚀 سرعت: {speed_str}"
            )
            edit_ui(text)
            last_edit_time = current_time

def setup_cookies():
    cookies = [
        os.environ.get("YT_COOKIE_1"),
        os.environ.get("YT_COOKIE_2"),
        os.environ.get("YT_COOKIE_3"),
        os.environ.get("YT_COOKIE_4")
    ]
    valid_cookies = [c for c in cookies if c and len(c) > 50]
    if valid_cookies:
        selected = valid_cookies[0].replace('\\n', '\n')
        if "# Netscape HTTP Cookie File" not in selected:
            selected = "# Netscape HTTP Cookie File\n" + selected
        with open("cookies.txt", "w", encoding="utf-8") as f:
            f.write(selected)
        return "cookies.txt"
    return None

def get_platform_opts(url, is_audio, quality, is_info_stage=False):
    """تنظیمات کاملا تفکیک شده برای جلوگیری از خطای فرمت"""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'noplaylist': True,
        'ignoreconfig': True,
        'outtmpl': f"video_{int(time.time())}.%(ext)s"
    }

    cookie_file = setup_cookies()
    if cookie_file:
        opts['cookiefile'] = cookie_file

    if is_info_stage:
        # مرحله اول: فقط استخراج بدون هیچ فیلتری
        opts['skip_download'] = True
        opts['extract_flat'] = False
        opts.pop('format', None) 
    else:
        # مرحله دوم: دانلود با تنظیمات پیشرفته و سرعت بالا
        opts['progress_hooks'] = [download_progress_hook]
        
        # ترفند فوق‌العاده برای افزایش سرعت دانلود (مانند IDM)
        opts['concurrent_fragment_downloads'] = 5 
        
        if is_audio:
            abr = '320' if quality == 'mp3320' else '128'
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': abr}]
        else:
            opts['merge_output_format'] = 'mp4'
            if quality == 'best':
                opts['format'] = 'bestvideo+bestaudio/best'
            else:
                # فال‌بک قوی: اول ویدیو با ارتفاع مشخص+صدا، بعد ویدیو+صدا با هم، در نهایت بهترین موجود
                opts['format'] = f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best'

        if "youtube.com" in url or "youtu.be" in url:
            opts['extractor_args'] = {
                'youtube': {
                    'player_client': ['android', 'web']
                }
            }

    return opts

def handle_info():
    global stop_fake_progress
    ydl_opts = get_platform_opts(URL, False, "best", is_info_stage=True)
    
    try:
        stop_fake_progress = False
        t = threading.Thread(target=fake_progress_bar, args=("در حال استخراج اطلاعات...",))
        t.start()
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(URL, download=False)
            
            stop_fake_progress = True
            t.join(timeout=1)
            
            title = info.get('title', 'ویدیو')[:60]
            thumb = info.get('thumbnail')
            video_id = info.get('id')
            
            formats = info.get('formats', [])
            heights_set = set()
            
            for f in formats:
                if f.get('vcodec') != 'none':
                    h = f.get('height')
                    if h and h >= 144:
                        heights_set.add(h)
                        
            sorted_heights = sorted(list(heights_set))
            keyboard = []
            row = []
            
            # چیدمان دکمه ها به صورت دو ستونه
            for h in sorted_heights:
                row.append({"text": f"🎬 {h}p", "callback_data": f"dl|{h}|{video_id}"})
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row: keyboard.append(row)
                
            keyboard.append([
                {"text": "🎵 MP3 (128)", "callback_data": f"dl|mp3|{video_id}"},
                {"text": "🎧 MP3 (320)", "callback_data": f"dl|mp3320|{video_id}"}
            ])
            
            tg_request("deleteMessage", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID)})
            tg_request("sendPhoto", {
                "chat_id": str(CHAT_ID), "photo": thumb,
                "caption": f"🎥 <b>{title}</b>\n\n👇 <i>کیفیت مورد نظر را انتخاب کنید:</i>",
                "parse_mode": "HTML", "reply_to_message_id": str(REPLY_TO), 
                "reply_markup": json.dumps({"inline_keyboard": keyboard})
            })

    except Exception as e:
        stop_fake_progress = True
        print(traceback.format_exc())
        edit_ui("❌ <b>خطا در ارتباط با سرور</b>\nارتباط با منبع ویدیو برقرار نشد.")

def handle_download():
    global stop_fake_progress
    is_audio = QUALITY in ['mp3', 'mp3320']
    
    try:
        # 1. گرفتن نام و اطلاعات کلی به صورت ایمن (بدون فرمت)
        info_opts = get_platform_opts(URL, False, "best", is_info_stage=True)
        with YoutubeDL(info_opts) as ydl_info:
            info = ydl_info.extract_info(URL, download=False)
            title = info.get('title', 'Video')[:50]
            platform = info.get('extractor', 'web').split(':')[0].capitalize()
            caption = f"📥 <b>{title}</b>\n🌐 #{platform}"
            
        # 2. استارت دانلود اختصاصی
        download_opts = get_platform_opts(URL, is_audio, QUALITY, is_info_stage=False)
        with YoutubeDL(download_opts) as ydl_down:
            ydl_down.download([URL])
            
        edit_ui("📤 <b>در حال آپلود به سرورهای تلگرام...</b>\n<i>لطفاً چند لحظه دیگر صبور باشید.</i>")
        
        # 3. پیدا کردن فایل ادغام شده نهایی
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
                tg_request("sendMessage", {"chat_id": str(CHAT_ID), "text": f"❌ خطا در آپلود به تلگرام.", "reply_to_message_id": str(REPLY_TO)})
        else:
            edit_ui("❌ خطا: فایل استخراج نشد.")

    except Exception as e:
        print(traceback.format_exc())
        err = str(e).lower()
        msg = "❌ حجم ویدیو بسیار بالاست." if "filesize" in err else "❌ خطا در دانلود فایل یا این کیفیت موجود نیست."
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
        edit_ui("❌ خطای سرور در ارتباط با گیت‌هاب.")

