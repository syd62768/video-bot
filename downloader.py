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
    """ویرایشگر هوشمند پیام/کپشن تلگرام"""
    res = tg_request("editMessageText", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID), "text": text, "parse_mode": "HTML"})
    if not res.get("ok"):
        tg_request("editMessageCaption", {"chat_id": str(CHAT_ID), "message_id": str(WAIT_MSG_ID), "caption": text, "parse_mode": "HTML"})

def clean_ansi(text):
    if not text: return ""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text).strip()

def fake_progress_bar(text_prefix):
    """نوار پیشرفت سبز رنگ و پویا (ترد بک‌گراند)"""
    global stop_fake_progress
    for i in range(1, 22):
        if stop_fake_progress:
            break
        
        filled = min(10, (i // 2) + 1)
        empty = 10 - filled
        bar = '🟩' * filled + '⬜️' * empty
        percent = min(99, (i * 4) + random.randint(1, 4))
        
        edit_ui(f"⏳ <b>{text_prefix}</b>\n\n{bar} {percent}%\n<i>در حال ارتباط با سرورهای پردازش...</i>")
        time.sleep(3)

def download_progress_hook(d):
    """نوار پیشرفت واقعی برای زمان دانلود فایل"""
    global last_edit_time
    if d['status'] == 'downloading':
        current_time = time.time()
        if current_time - last_edit_time > 3.0:
            percent_str = clean_ansi(d.get('_percent_str', '0%'))
            speed_str = clean_ansi(d.get('_speed_str', 'N/A'))
            eta_str = clean_ansi(d.get('_eta_str', 'N/A'))
            
            try:
                p = float(percent_str.replace('%', ''))
            except:
                p = 0
            
            filled = int(p / 10)
            bar = '🟩' * filled + '⬜️' * (10 - filled)
            
            text = f"⏳ <b>در حال دانلود فایل به سرور ربات...</b>\n\n{bar} {percent_str}\n🚀 سرعت: {speed_str}\n⏱ زمان: {eta_str}"
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
        selected = random.choice(valid_cookies)
        selected = selected.replace('\\n', '\n')
        if "# Netscape HTTP Cookie File" not in selected:
            selected = "# Netscape HTTP Cookie File\n" + selected
            
        with open("cookies.txt", "w", encoding="utf-8") as f:
            f.write(selected)
        return "cookies.txt"
    return None

def get_platform_opts(url, is_audio, quality, is_info_stage=False):
    """تنظیمات هوشمند بر اساس روش تفکیک شده"""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'noplaylist': True,
        'ignoreconfig': True, # تغییر 2: نادیده گرفتن کانفیگ‌های مخفی سرور
        'outtmpl': f"video_{int(time.time())}.%(ext)s"
    }

    # تغییر 1: کوکی فقط در مرحله دانلود ارسال شود
    if not is_info_stage:
        cookie_file = setup_cookies()
        if cookie_file:
            opts['cookiefile'] = cookie_file

    if is_info_stage:
        opts['skip_download'] = True
        opts['extract_flat'] = False
        opts.pop('format', None) 
    else:
        opts['progress_hooks'] = [download_progress_hook]
        if is_audio:
            abr = '320' if quality == 'mp3320' else '128'
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': abr}]
        else:
            opts['merge_output_format'] = 'mp4'
            if quality == 'best':
                opts['format'] = 'bestvideo*+bestaudio/best'
            else:
                opts['format'] = f'bestvideo*[height<={quality}]+bestaudio/b[height<={quality}]/bestvideo*+bestaudio/best'

    # تغییر 3: بازگرداندن extractor_args فقط با کلاینت اندروید
    if "youtube.com" in url or "youtu.be" in url:
        opts['extractor_args'] = {
            'youtube': {
                'player_client': ['android']
            }
        }

    return opts

def handle_info():
    global stop_fake_progress
    ydl_opts = get_platform_opts(URL, False, "best", is_info_stage=True)
    
    try:
        stop_fake_progress = False
        t = threading.Thread(target=fake_progress_bar, args=("در حال جستجو و استخراج کیفیت‌ها...",))
        t.start()
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(URL, download=False)
            
            stop_fake_progress = True
            t.join(timeout=1)
            
            # تغییر 4: لاگ‌های تشخیصی برای گیت‌هاب اکشن
            print("TITLE:", info.get("title"))
            print("FORMATS:", len(info.get("formats", [])))
            
            title = info.get('title', 'ویدیو')[:50]
            thumb = info.get('thumbnail')
            video_id = info.get('id')
            
            formats = info.get('formats', [])
            available_qualities = {}
            
            for f in formats:
                if f.get('vcodec') != 'none':
                    h = f.get('height')
                    size = (
                        f.get('filesize')
                        or f.get('filesize_approx')
                        or f.get('filesize_approx_bytes')
                        or 0
                    )
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
                "caption": f"🎥 <b>{title}</b>\n\n👇 <i>کیفیت مورد نظر را انتخاب کنید:</i>",
                "parse_mode": "HTML", "reply_to_message_id": str(REPLY_TO), 
                "reply_markup": json.dumps({"inline_keyboard": keyboard})
            })

    except Exception as e:
        stop_fake_progress = True
        print(traceback.format_exc())
        edit_ui("❌ <b>خطا در ارتباط با یوتیوب</b>\nویدیو در دسترس نیست یا مسدود شده است.")

def handle_download():
    global stop_fake_progress
    is_audio = QUALITY in ['mp3', 'mp3320']
    
    try:
        stop_fake_progress = False
        t = threading.Thread(target=fake_progress_bar, args=("در حال آماده‌سازی لینک نهایی...",))
        t.start()
        
        # تغییر 5: تفکیک کامل استخراج اولیه و دانلود نهایی
        info_opts = get_platform_opts(URL, False, "best", is_info_stage=True)
        with YoutubeDL(info_opts) as ydl_info:
            info = ydl_info.extract_info(URL, download=False)
            title = info.get('title', 'Video')[:40]
            platform = info.get('extractor', 'web').split(':')[0].capitalize()
            caption = f"📥 <b>{title}</b>\n🌐 #{platform}"
            
        stop_fake_progress = True
        edit_ui("🚀 <b>در حال دانلود فایل به سرور...</b>\n<i>لطفاً صبور باشید.</i>")
        
        download_opts = get_platform_opts(URL, is_audio, QUALITY, is_info_stage=False)
        with YoutubeDL(download_opts) as ydl_down:
            ydl_down.download([URL])
            
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
            edit_ui("❌ خطا: فایل استخراج نشد.")

    except Exception as e:
        stop_fake_progress = True
        print(traceback.format_exc())
        err = str(e).lower()
        msg = "❌ حجم ویدیو بسیار بالاست." if "filesize" in err else "❌ خطا در دانلود فایل."
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


