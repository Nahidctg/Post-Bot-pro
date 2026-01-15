# -*- coding: utf-8 -*-

import os
import io
import re
import json
import time
import asyncio
import logging
import random
import string
import base64
import datetime
import aiohttp
import requests 
import urllib3 
import numpy as np 
import cv2 
from threading import Thread

# --- Third-party Library Imports ---
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, Message,
    CallbackQuery
)
from flask import Flask
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient 

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# SSL Warnings বন্ধ করা
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables
load_dotenv()

# ---- CONFIGURATION ----
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# 🔥 ADMIN & DB CONFIG
MONGO_URL = os.getenv("MONGO_URL") 
OWNER_ID = int(os.getenv("OWNER_ID", 0)) 
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "admin") 
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 0))

# Check Variables
if not all([BOT_TOKEN, API_ID, API_HASH, TMDB_API_KEY, MONGO_URL]):
    logger.critical("❌ FATAL ERROR: Variables missing in .env file!")
    exit(1)

# ====================================================================
# 🔥 DATABASE CONNECTION (MONGODB)
# ====================================================================
try:
    mongo_client = AsyncIOMotorClient(MONGO_URL)
    db = mongo_client["movie_bot_db"]
    users_col = db["users"]
    settings_col = db["settings"]
    user_settings_col = db["user_settings"]
    posts_col = db["posts"] 
    logger.info("✅ MongoDB Connected Successfully!")
except Exception as e:
    logger.critical(f"❌ MongoDB Connection Failed: {e}")
    exit(1)

# ---- DEFAULT SETTINGS ----
DEFAULT_OWNER_AD_LINKS = [
    "https://www.effectivegatecpm.com/c90zejmfrg?key=45a67d2f1523ee6b3988c4cc8f764a35",
    "https://www.effectivegatecpm.com/q5cpmxwy44?key=075b9f116b4174922cadfae2d3291743",
    "https://www.effectivegatecpm.com/p4bm30ss3?key=8bb102e9258871570c79a9a90fa3cf9f"
]
DEFAULT_USER_AD_LINKS = ["https://www.google.com", "https://www.bing.com"] 

user_conversations = {}

# ---- DATABASE FUNCTIONS ----
async def add_user(user_id, name):
    if not await users_col.find_one({"_id": user_id}):
        await users_col.insert_one({
            "_id": user_id, 
            "name": name,
            "authorized": False, 
            "banned": False,
            "joined_date": datetime.datetime.now()
        })

async def is_authorized(user_id):
    if user_id == OWNER_ID: return True
    user = await users_col.find_one({"_id": user_id})
    if not user: return False
    return user.get("authorized", False) and not user.get("banned", False)

async def is_banned(user_id):
    user = await users_col.find_one({"_id": user_id})
    return user and user.get("banned", False)

async def get_owner_ads():
    data = await settings_col.find_one({"_id": "main_config"})
    return data.get("owner_ads", DEFAULT_OWNER_AD_LINKS) if data else DEFAULT_OWNER_AD_LINKS

async def set_owner_ads_db(links):
    await settings_col.update_one(
        {"_id": "main_config"}, 
        {"$set": {"owner_ads": links}}, 
        upsert=True
    )

async def get_user_ads(user_id):
    data = await user_settings_col.find_one({"_id": user_id})
    return data.get("ad_links", DEFAULT_USER_AD_LINKS) if data else DEFAULT_USER_AD_LINKS

async def save_user_ads(user_id, links):
    await user_settings_col.update_one(
        {"_id": user_id}, 
        {"$set": {"ad_links": links}}, 
        upsert=True
    )

async def get_all_users_count():
    return await users_col.count_documents({})

# 🔥 Generate Short ID
def generate_short_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# 🔥 Save Post Logic
async def save_post_to_db(post_data, links):
    pid = post_data.get("post_id")
    if not pid:
        pid = generate_short_id()
        post_data["post_id"] = pid
    
    save_data = {
        "_id": pid,
        "details": post_data,
        "links": links,
        "updated_at": datetime.datetime.now()
    }
    await posts_col.replace_one({"_id": pid}, save_data, upsert=True)
    return pid

# ---- RESOURCES URLS ----
URL_FONT = "https://raw.githubusercontent.com/mahabub81/bangla-fonts/master/Kalpurush.ttf"
URL_MODEL = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"

# ---- ASYNC HTTP SESSION ----
async def fetch_url(url, method="GET", data=None, headers=None, json_data=None):
    async with aiohttp.ClientSession() as session:
        try:
            if method == "GET":
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        return await resp.json() if "application/json" in resp.headers.get("Content-Type", "") else await resp.read()
            elif method == "POST":
                async with session.post(url, data=data, json=json_data, headers=headers, ssl=False, timeout=15) as resp:
                    return await resp.text()
        except Exception as e:
            logger.error(f"HTTP Error: {e}")
            return None
    return None

# ---- FLASK KEEP-ALIVE ----
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 v40 Bot Running (Fixed Edit Crash)"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive_pinger():
    while True:
        try:
            requests.get("http://localhost:8080")
            time.sleep(600) 
        except:
            time.sleep(600)

# ============================================================================
# 🔥 AUTOMATIC RESOURCE DOWNLOADER
# ============================================================================
def setup_resources():
    font_name = "kalpurush.ttf"
    if not os.path.exists(font_name):
        logger.info("⬇️ Downloading Bengali Font...")
        try:
            r = requests.get(URL_FONT)
            with open(font_name, "wb") as f:
                f.write(r.content)
        except Exception as e: logger.error(f"❌ Font Download Failed: {e}")

    model_name = "haarcascade_frontalface_default.xml"
    if not os.path.exists(model_name):
        logger.info("⬇️ Downloading Face Model...")
        try:
            r = requests.get(URL_MODEL)
            with open(model_name, "wb") as f:
                f.write(r.content)
        except Exception as e: logger.error(f"❌ Model Download Failed: {e}")

setup_resources()

# ---- FONT HELPER FUNCTION ----
def get_font(size=60, bold=False):
    try:
        if os.path.exists("kalpurush.ttf"):
            return ImageFont.truetype("kalpurush.ttf", size)
        font_file = "Poppins-Bold.ttf" if bold else "Poppins-Regular.ttf"
        if os.path.exists(font_file):
             return ImageFont.truetype(font_file, size)
        return ImageFont.load_default()
    except Exception as e:
        return ImageFont.load_default()

# ====================================================================
# 🔥 UPLOAD FUNCTION (Permanent Only)
# ====================================================================
def upload_image_core(file_content):
    try:
        url = "https://catbox.moe/user/api.php"
        data = {"reqtype": "fileupload", "userhash": ""}
        files = {"fileToUpload": ("image.png", file_content, "image/png")}
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.post(url, data=data, files=files, headers=headers, timeout=10, verify=False)
        if response.status_code == 200: return response.text.strip()
    except: pass

    try:
        url = "https://graph.org/upload"
        files = {'file': ('image.jpg', file_content, 'image/jpeg')}
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.post(url, files=files, headers=headers, timeout=8, verify=False)
        if response.status_code == 200:
            json_data = response.json()
            return "https://graph.org" + json_data[0]["src"]
    except: pass

    logger.error("❌ ALL PERMANENT UPLOAD SERVERS FAILED.")
    return None

def upload_to_catbox_bytes(img_bytes):
    try:
        if hasattr(img_bytes, 'read'):
            img_bytes.seek(0)
            data = img_bytes.read()
        else:
            data = img_bytes
        return upload_image_core(data)
    except: return None

def upload_to_catbox(file_path):
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        return upload_image_core(data)
    except: return None

# ---- TMDB & LINK EXTRACTION ----
def extract_tmdb_id(text):
    tmdb_match = re.search(r'themoviedb\.org/(movie|tv)/(\d+)', text)
    if tmdb_match:
        return tmdb_match.group(1), tmdb_match.group(2)
    imdb_url_match = re.search(r'imdb\.com/title/(tt\d+)', text)
    if imdb_url_match:
        return "imdb", imdb_url_match.group(1)
    imdb_id_match = re.search(r'(tt\d{6,})', text)
    if imdb_id_match:
        return "imdb", imdb_id_match.group(1)
    return None, None

async def search_tmdb(query):
    try:
        match = re.search(r'(.+?)\s*\(?(\d{4})\)?$', query)
        name = match.group(1).strip() if match else query.strip()
        year = match.group(2) if match else None
        
        url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={name}&include_adult=true"
        if year: url += f"&year={year}"
        
        data = await fetch_url(url)
        if not data: return []
        return [r for r in data.get("results", []) if r.get("media_type") in ["movie", "tv"]][:15]
    except: return []

async def get_tmdb_details(media_type, media_id):
    url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={TMDB_API_KEY}&append_to_response=credits,similar,images&include_image_language=en,null"
    return await fetch_url(url)

# ---- DPASTE FUNCTION ----
async def create_paste_link(content):
    if not content: return None
    url = "https://dpaste.com/api/"
    data = {"content": content, "syntax": "html", "expiry_days": 14, "title": "Movie Post Code"}
    headers = {'User-Agent': 'Mozilla/5.0'}
    link = await fetch_url(url, method="POST", data=data, headers=headers)
    if link and "dpaste.com" in link:
        return link.strip()
    return None

# ============================================================================
# 🔥 FACE DETECTION & SMART BADGE
# ============================================================================
def get_smart_badge_position(pil_img):
    try:
        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        cascade_path = "haarcascade_frontalface_default.xml"
        if not os.path.exists(cascade_path): return int(pil_img.height * 0.40) 

        face_cascade = cv2.CascadeClassifier(cascade_path)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) > 0:
            lowest_y = 0
            for (x, y, w, h) in faces:
                bottom_of_face = y + h
                if bottom_of_face > lowest_y: lowest_y = bottom_of_face
            target_y = lowest_y + 40 
            if target_y > (pil_img.height - 130): return 80 
            return target_y
        else: return int(pil_img.height * 0.40) 
    except: return 200

def apply_badge_to_poster(poster_bytes, text):
    try:
        base_img = Image.open(io.BytesIO(poster_bytes)).convert("RGBA")
        width, height = base_img.size
        font = get_font(size=70) 
        pos_y = get_smart_badge_position(base_img)
        draw = ImageDraw.Draw(base_img)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        padding_x, padding_y = 40, 20
        box_w = text_w + (padding_x * 2)
        box_h = text_h + (padding_y * 2)
        pos_x = (width - box_w) // 2
        
        overlay = Image.new('RGBA', base_img.size, (0,0,0,0))
        ImageDraw.Draw(overlay).rectangle([pos_x, pos_y, pos_x + box_w, pos_y + box_h], fill=(0, 0, 0, 220))
        base_img = Image.alpha_composite(base_img, overlay)
        draw = ImageDraw.Draw(base_img)
        cx = pos_x + padding_x
        cy = pos_y + padding_y - 12
        colors = ["#FFEB3B", "#FF5722"]
        words = text.split()
        if len(words) >= 2:
            draw.text((cx, cy), words[0], font=font, fill=colors[0])
            w1 = draw.textlength(words[0], font=font)
            draw.text((cx + w1 + 15, cy), " ".join(words[1:]), font=font, fill=colors[1])
        else:
            draw.text((cx, cy), text, font=font, fill=colors[0])

        img_buffer = io.BytesIO()
        base_img.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        return img_buffer
    except: return io.BytesIO(poster_bytes)

# ============================================================================
# 🔥 HTML GENERATOR
# ============================================================================
def generate_html_code(data, links, user_ad_links_list, owner_ad_links_list):
    title = data.get("title") or data.get("name")
    overview = data.get("overview", "")
    poster = data.get('manual_poster_url') or f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}"
    is_adult = data.get('adult', False) or data.get('force_adult', False)
    BTN_TELEGRAM = "https://i.ibb.co/kVfJvhzS/photo-2025-12-23-12-38-56-7587031987190235140.jpg"

    lang_str = data.get('custom_language', 'Dual Audio').strip()
    if data.get('is_manual'): genres_str = "Movie / Unknown" 
    else:
        genres_list = [g['name'] for g in data.get('genres', [])]
        genres_str = ", ".join(genres_list) if genres_list else "Movie"

    meta_html = f"""
    <!-- HIDDEN METADATA -->
    <div style="display:none;" id="meta-genre">{genres_str}</div>
    <div style="display:none;" id="meta-language">{lang_str}</div>
    """

    ss_html = ""
    if data.get('manual_screenshots'):
        for ss_url in data['manual_screenshots']:
            blur_class = "blur-content" if is_adult else ""
            ss_html += f'<div class="ss-wrapper"><img src="{ss_url}" class="neon-ss {blur_class}" onclick="toggleBlur(this)" alt="Screenshot"></div>'
    elif not data.get('is_manual') and data.get("images"):
        backdrops = data["images"].get("backdrops", [])
        count = 0
        for bd in backdrops:
            if count >= 4: break
            if bd.get('aspect_ratio', 1.7) > 1.2: 
                ss_url = f"https://image.tmdb.org/t/p/w780{bd['file_path']}"
                blur_class = "blur-content" if is_adult else ""
                ss_html += f'<div class="ss-wrapper"><img src="{ss_url}" class="neon-ss {blur_class}" onclick="toggleBlur(this)" alt="Screenshot"></div>'
                count += 1
    
    ss_section = ""
    if ss_html:
        ss_section = f"""<div class="ss-container"><h3 style="color: #ff00de; text-transform: uppercase; margin-bottom: 15px; border-bottom: 2px solid #ff00de; display: inline-block;">📸 SCREENSHOTS</h3>{ss_html}</div>"""

    links_html = ""
    for idx, link in enumerate(links):
        encoded_url = base64.b64encode(link['url'].encode('utf-8')).decode('utf-8')
        links_html += f"""
        <div class="dl-item">
            <span class="dl-link-label">📂 {link['label']}</span>
            <div id="area-{idx}"><button class="rgb-btn" onclick="secureLink(this, '{encoded_url}', 'area-{idx}')">🔒 SECURE DOWNLOAD</button></div>
        </div>"""

    final_ad_list = list(user_ad_links_list)
    if owner_ad_links_list: final_ad_list.extend(owner_ad_links_list)
    random.shuffle(final_ad_list) 
    if not final_ad_list: final_ad_list = ["https://google.com"]

    style_html = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');
        body { margin: 0; padding: 10px; background-color: #050505; font-family: 'Poppins', sans-serif; color: #fff; }
        .main-card { max-width: 600px; margin: 0 auto; background: #121212; border: 1px solid #333; border-radius: 15px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.8); text-align: center; }
        .blur-content { filter: blur(20px); transition: filter 0.4s ease; cursor: pointer; }
        .blur-content:hover { filter: blur(10px); }
        .blur-content.blur-active { filter: none !important; }
        .poster-wrapper { position: relative; display: inline-block; width: 100%; max-width: 250px; }
        .reveal-btn { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.8); color: #FF5252; padding: 10px 20px; border: 2px solid #FF5252; font-weight: bold; border-radius: 5px; cursor: pointer; display: none; z-index: 10; pointer-events: none; }
        .is-blurred .reveal-btn { display: block; }
        .poster-img { width: 100%; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.7); margin-bottom: 15px; border: 2px solid #333; }
        h2 { color: #00d2ff; margin: 10px 0; font-size: 22px; font-weight: 700; }
        p { text-align: justify; color: #ccc; font-size: 13px; margin-bottom: 20px; line-height: 1.6; }
        .ss-container { margin: 25px 0; }
        .neon-ss { width: 100%; border-radius: 8px; margin-bottom: 12px; border: 2px solid #ff00de; box-shadow: 0 0 15px rgba(255, 0, 222, 0.3); }
        .dl-item { background: #1f1f1f; padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #333; }
        .dl-link-label { display: block; font-size: 16px; color: #ffeb3b; margin-bottom: 10px; font-weight: 600; text-transform: uppercase; }
        .rgb-btn { width: 100%; padding: 14px; font-size: 18px; font-weight: bold; color: white; border: none; border-radius: 8px; cursor: pointer; background: linear-gradient(45deg, #FF512F, #DD2476); display: flex; align-items: center; justify-content: center; gap: 10px; }
        .disclaimer { font-size: 10px; color: #555; margin-top: 30px; border-top: 1px solid #222; padding-top: 10px; }
    </style>
    """

    script_html = f"""
    <script>
    const AD_LINKS = {json.dumps(final_ad_list)};
    function toggleBlur(el) {{
        el.classList.toggle('blur-active');
        let wrapper = el.parentElement;
        if(wrapper.classList.contains('poster-wrapper')) {{ wrapper.classList.remove('is-blurred'); }}
    }}
    function secureLink(btn, b64Url, areaId) {{
        let realUrl = atob(b64Url);
        let randomAd = AD_LINKS[Math.floor(Math.random() * AD_LINKS.length)];
        window.open(randomAd, '_blank');
        let timeLeft = 5;
        btn.disabled = true;
        btn.style.background = "#444";
        let timer = setInterval(function() {{
            btn.innerHTML = "⏳ Wait... " + timeLeft + "s";
            timeLeft--;
            if (timeLeft < 0) {{
                clearInterval(timer);
                btn.innerHTML = "🚀 Opening...";
                btn.style.background = "#00C853";
                window.location.href = realUrl;
            }}
        }}, 1000); 
    }}
    </script>
    """
    
    poster_wrapper_class = "is-blurred" if is_adult else ""
    poster_img_class = "poster-img blur-content" if is_adult else "poster-img"
    reveal_html = '<div class="reveal-btn">🔞 Click to Reveal</div>' if is_adult else ""

    return f"""
    <!-- Auto Redirect Code (v40) -->
    {style_html}
    <div class="main-card">
        <div class="poster-wrapper {poster_wrapper_class}">
            <img src="{poster}" class="{poster_img_class}" onclick="toggleBlur(this)">
            {reveal_html}
        </div>
        <h2>{title}</h2>
        <p>{overview[:350]}...</p>
        {ss_section}
        <div class="instruction-box">ℹ️ <b>Safe Download:</b> Click button > Ad opens > Wait 5s > <b>Auto Redirect</b></div>
        <div class="dl-container-area">{links_html}</div>
        <div style="margin-top: 20px; border-top: 1px solid #333; padding-top: 15px;">
            <a href="https://t.me/+6hvCoblt6CxhZjhl" target="_blank"><img src="{BTN_TELEGRAM}" style="width: 100%; max-width: 300px; border-radius: 50px; border: 2px solid #333;"></a>
        </div>
        <div class="disclaimer">⚖️ <b>Disclaimer:</b> We do not host any files. Links are provided by third-party users. Protected by DMCA. Content may contain 18+ themes.</div>
    </div>
    {meta_html}
    {script_html}
    """

# ---- IMAGE & CAPTION GENERATOR ----
def generate_formatted_caption(data, pid=None):
    title = data.get("title") or data.get("name") or "N/A"
    is_adult = data.get('adult', False) or data.get('force_adult', False)
    
    if data.get('is_manual'):
        year = "Custom"
        rating = "⭐ N/A"
        genres = "Custom"
        language = "N/A"
    else:
        year = (data.get("release_date") or data.get("first_air_date") or "----")[:4]
        rating = f"⭐ {data.get('vote_average', 0):.1f}/10"
        genres = ", ".join([g["name"] for g in data.get("genres", [])] or ["N/A"])
        language = data.get('custom_language', '').title()
    
    overview = data.get("overview", "No plot available.")
    caption = f"🎬 **{title} ({year})**\n"
    if pid: caption += f"🆔 **ID:** `{pid}` (Use to Edit)\n\n"
    
    if is_adult:
        caption += "⚠️ **WARNING: 18+ Content.**\n_Suitable for mature audiences only._\n\n"
    if not data.get('is_manual'):
        caption += f"**🎭 Genres:** {genres}\n**🗣️ Language:** {language}\n**⭐ Rating:** {rating}\n\n"
    caption += f"**📝 Plot:** _{overview[:300]}..._\n\n⚠️ _Disclaimer: Informational post only._"
    return caption

def generate_image(data):
    try:
        if data.get('manual_poster_url'): poster_url = data.get('manual_poster_url')
        else: poster_url = f"https://image.tmdb.org/t/p/w500{data['poster_path']}" if data.get('poster_path') else None
        
        if not poster_url: return None, None
        poster_bytes = requests.get(poster_url, timeout=10, verify=False).content
        is_adult = data.get('adult', False) or data.get('force_adult', False)
        
        if data.get('badge_text'):
            badge_io = apply_badge_to_poster(poster_bytes, data['badge_text'])
            poster_bytes = badge_io.getvalue()

        poster_img = Image.open(io.BytesIO(poster_bytes)).convert("RGBA").resize((400, 600))
        if is_adult: poster_img = poster_img.filter(ImageFilter.GaussianBlur(20))

        bg_img = Image.new('RGBA', (1280, 720), (10, 10, 20))
        backdrop = None
        if data.get('backdrop_path') and not data.get('is_manual'):
            try:
                bd_url = f"https://image.tmdb.org/t/p/w1280{data['backdrop_path']}"
                bd_bytes = requests.get(bd_url, timeout=10, verify=False).content
                backdrop = Image.open(io.BytesIO(bd_bytes)).convert("RGBA").resize((1280, 720))
            except: pass
        
        if not backdrop: backdrop = poster_img.resize((1280, 720))
        backdrop = backdrop.filter(ImageFilter.GaussianBlur(10))
        bg_img = Image.alpha_composite(backdrop, Image.new('RGBA', (1280, 720), (0, 0, 0, 150))) 
        bg_img.paste(poster_img, (50, 60), poster_img)
        draw = ImageDraw.Draw(bg_img)
        f_bold = get_font(size=36, bold=True)
        f_reg = get_font(size=24, bold=False)

        title = data.get("title") or data.get("name")
        year = (data.get("release_date") or data.get("first_air_date") or "----")[:4]
        if data.get('is_manual'): year = ""
        if is_adult: title += " (18+)"

        draw.text((480, 80), f"{title} {year}", font=f_bold, fill="white", stroke_width=1, stroke_fill="black")
        if not data.get('is_manual'):
            draw.text((480, 140), f"⭐ {data.get('vote_average', 0):.1f}/10", font=f_reg, fill="#00e676")
            if is_adult: draw.text((480, 180), "⚠️ RESTRICTED CONTENT", font=get_font(18), fill="#FF5252")
            else: draw.text((480, 180), " | ".join([g["name"] for g in data.get("genres", [])]), font=get_font(18), fill="#00bcd4")
        
        overview = data.get("overview", "")
        lines = [overview[i:i+80] for i in range(0, len(overview), 80)][:6]
        y_text = 250
        for line in lines:
            draw.text((480, y_text), line, font=f_reg, fill="#E0E0E0")
            y_text += 30
            
        img_buffer = io.BytesIO()
        img_buffer.name = "poster.png"
        bg_img.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        return img_buffer, poster_bytes 
    except Exception as e:
        logger.error(f"Img Gen Error: {e}")
        return None, None

# ---- BOT INIT ----
try:
    bot = Client("moviebot", api_id=int(API_ID), api_hash=API_HASH, bot_token=BOT_TOKEN)
except Exception as e:
    logger.critical(f"Bot Init Error: {e}")
    exit(1)

# ---- BOT COMMANDS ----
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    uid = message.from_user.id
    name = message.from_user.first_name
    await add_user(uid, name) 
    
    user_conversations.pop(uid, None)
    
    # 🔥 Check Auth
    if not await is_authorized(uid):
        # 🔥 Added Contact Button
        btn = [[InlineKeyboardButton("💬 Contact Admin", url=f"https://t.me/{OWNER_USERNAME}")]]
        return await message.reply_text(
            "⚠️ **ACCESS DENIED**\n\nYou need admin approval to use this bot.\nContact Owner.",
            reply_markup=InlineKeyboardMarkup(btn)
        )

    await message.reply_text("🎬 **Movie & Series Bot (v40 Stable)**\n✨ **Status:** Authorized User ✅\n\n⚡ `/post <Link or Name>` - Auto Post\n✍️ `/manual` - Custom Post\n🔄 `/edit <Name/ID>` - Edit by Name!\n📜 `/history` - View your posts")

@bot.on_message(filters.command("auth") & filters.user(OWNER_ID))
async def auth_user(client, message):
    try:
        target_id = int(message.command[1])
        await users_col.update_one({"_id": target_id}, {"$set": {"authorized": True, "banned": False}}, upsert=True)
        await message.reply_text(f"✅ User {target_id} is now **AUTHORIZED**.")
        await client.send_message(target_id, "✅ **Congratulations!** You have been authorized to use the bot.")
    except: await message.reply_text("❌ Usage: `/auth 123456789`")

@bot.on_message(filters.command("ban") & filters.user(OWNER_ID))
async def ban_user(client, message):
    try:
        target_id = int(message.command[1])
        await users_col.update_one({"_id": target_id}, {"$set": {"banned": True}})
        await message.reply_text(f"🚫 User {target_id} has been **BANNED**.")
    except: await message.reply_text("❌ Usage: `/ban 123456789`")

@bot.on_message(filters.command("stats") & filters.user(OWNER_ID))
async def bot_stats(client, message):
    total = await get_all_users_count()
    total_posts = await posts_col.count_documents({})
    await message.reply_text(f"📊 **BOT STATISTICS**\n\n👥 **Total Users:** {total}\n📂 **Total Posts Saved:** {total_posts}\n✅ **System:** Online\n🚀 **Version:** v40")

@bot.on_message(filters.command("setownerads") & filters.user(OWNER_ID))
async def set_owner_ads_cmd(client, message):
    if len(message.command) > 1:
        links = message.text.split(None, 1)[1].split()
        valid = [l for l in links if l.startswith("http")]
        if valid:
            await set_owner_ads_db(valid)
            await message.reply_text(f"✅ **Owner Ads Updated!** ({len(valid)} links)")
        else: await message.reply_text("❌ Invalid Links.")
    else: await message.reply_text("⚠️ Usage: `/setownerads link1 link2`")

@bot.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_msg(client, message):
    if not message.reply_to_message: return await message.reply_text("⚠️ Reply to a message to broadcast.")
    msg = await message.reply_text("⏳ Broadcasting...")
    count = 0
    async for user in users_col.find({}):
        try:
            await message.reply_to_message.copy(user["_id"])
            count += 1
            await asyncio.sleep(0.1) 
        except: pass
    await msg.edit_text(f"✅ Broadcast Sent to **{count}** users.")

# ---- USER COMMANDS ----
@bot.on_message(filters.command("mysettings") & filters.private)
async def mysettings_cmd(client, message):
    uid = message.from_user.id
    if not await is_authorized(uid): return
    my_links = await get_user_ads(uid)
    links_str = "\n".join([f"{i+1}. {l}" for i, l in enumerate(my_links)])
    await message.reply_text(f"⚙️ **MY SETTINGS**\n\n🔗 **Your Ad Links:**\n{links_str}", disable_web_page_preview=True)

@bot.on_message(filters.command("setadlink") & filters.private)
async def set_ad(client, message):
    uid = message.from_user.id
    if not await is_authorized(uid): return
    if len(message.command) > 1:
        raw_links = message.text.split(None, 1)[1].split()
        valid_links = [l for l in raw_links if l.startswith("http")]
        if valid_links:
            await save_user_ads(uid, valid_links)
            links_str = "\n".join([f"{i+1}. {l}" for i, l in enumerate(valid_links)])
            await message.reply_text(f"✅ **Ad Links Saved!**\n\n{links_str}")
        else: await message.reply_text("⚠️ Invalid Links.")
    else: await message.reply_text("⚠️ Usage Example:\n`/setadlink https://site1.com https://site2.com`")

@bot.on_message(filters.command("manual") & filters.private)
async def manual_post_cmd(client, message):
    uid = message.from_user.id
    if not await is_authorized(uid): return await message.reply_text("🚫 Not Authorized.")
    user_conversations[uid] = { "details": {"is_manual": True, "manual_screenshots": []}, "links": [], "state": "manual_title" }
    await message.reply_text("✍️ **Manual Post Started**\n\nপ্রথমে **টাইটেল (Title)** লিখুন:")

# 🔥 NEW: HISTORY COMMAND
@bot.on_message(filters.command("history") & filters.private)
async def history_cmd(client, message):
    uid = message.from_user.id
    if not await is_authorized(uid): return

    cursor = posts_col.find({}).sort("updated_at", -1).limit(10)
    posts = await cursor.to_list(length=10)
    
    if not posts: return await message.reply_text("❌ No history found.")
    
    text = "📜 **Your Last 10 Posts:**\n\n"
    for p in posts:
        title = p["details"].get("title") or p["details"].get("name") or "Unknown"
        pid = p["_id"]
        text += f"🎬 **{title}**\n🆔 `{pid}`\n\n"
    
    await message.reply_text(text)

# 🔥 UPDATED: SMART EDIT COMMAND (Fixes Search & Reply)
@bot.on_message(filters.command("edit") & filters.private)
async def edit_post_cmd(client, message):
    uid = message.from_user.id
    if not await is_authorized(uid): return
    
    if len(message.command) < 2:
        return await message.reply_text("⚠️ Usage: `/edit <Name OR ID>`\nExample: `/edit Avatar`")
    
    query = message.text.split(" ", 1)[1].strip()
    msg = await message.reply_text(f"🔍 Searching for `{query}`...")
    
    try:
        # 1. Try Exact ID Match
        post = await posts_col.find_one({"_id": query})
        
        # 2. Try Title Search (Case Insensitive)
        if not post:
            cursor = posts_col.find({"details.title": {"$regex": query, "$options": "i"}})
            results = await cursor.to_list(length=10)
            
            # Try "name" for Series
            if not results:
                cursor = posts_col.find({"details.name": {"$regex": query, "$options": "i"}})
                results = await cursor.to_list(length=10)
                
            if not results: 
                return await msg.edit_text("❌ No posts found with that name/ID.\nMake sure you have saved it at least once.")
            
            if len(results) > 1:
                btns = []
                for r in results:
                    title = r["details"].get("title") or r["details"].get("name")
                    pid = r["_id"]
                    btns.append([InlineKeyboardButton(f"{title} ({pid})", callback_data=f"forcedit_{pid}_{uid}")])
                return await msg.edit_text("👇 **Select Post to Edit:**", reply_markup=InlineKeyboardMarkup(btns))
            
            post = results[0] # Exact one match

        # Start Edit Session
        await msg.delete() # Delete searching message
        await start_edit_session(uid, post, message)
        
    except Exception as e:
        logger.error(f"Search Error: {e}")
        await msg.edit_text("❌ An error occurred while searching.")

async def start_edit_session(uid, post, message):
    details = post.get("details")
    current_links = post.get("links", [])
    pid = post.get("_id")
    
    user_conversations[uid] = {
        "details": details,
        "links": current_links,
        "state": "edit_mode",
        "post_id": pid
    }
    
    links_text = "\n".join([f"{i+1}. {l['label']}" for i, l in enumerate(current_links)])
    msg_txt = f"📝 **Editing:** {details.get('title') or details.get('name')}\n🆔 **ID:** `{pid}`\n\n🔗 **Current Links:**\n{links_text}\n\n👇 **What to do?**"
    
    btns = [[InlineKeyboardButton("➕ Add New Link", callback_data=f"add_lnk_edit_{uid}")],
            [InlineKeyboardButton("✅ Generate New Code", callback_data=f"gen_edit_{uid}")]]
    
    if isinstance(message, Message): await message.reply_text(msg_txt, reply_markup=InlineKeyboardMarkup(btns))
    else: await message.edit_text(msg_txt, reply_markup=InlineKeyboardMarkup(btns))

@bot.on_callback_query(filters.regex("^forcedit_"))
async def force_edit_cb(client, cb):
    try: _, pid, uid = cb.data.split("_"); uid = int(uid)
    except: return
    post = await posts_col.find_one({"_id": pid})
    if post: await start_edit_session(uid, post, cb.message)

@bot.on_message(filters.command("post") & filters.private)
async def post_cmd(client, message):
    uid = message.from_user.id
    if not await is_authorized(uid): return await message.reply_text("🚫 Not Authorized.")
    if len(message.command) < 2: return await message.reply_text("⚠️ Usage:\n`/post Avatar`")
    
    query = message.text.split(" ", 1)[1].strip()
    msg = await message.reply_text(f"🔎 Processing `{query}`...")
    m_type, m_id = extract_tmdb_id(query)

    if m_type and m_id:
        if m_type == "imdb":
            find_url = f"https://api.themoviedb.org/3/find/{m_id}?api_key={TMDB_API_KEY}&external_source=imdb_id"
            data = await fetch_url(find_url)
            results = data.get("movie_results", []) + data.get("tv_results", [])
            if results: m_type, m_id = results[0]['media_type'], results[0]['id']
            else: return await msg.edit_text("❌ IMDb ID not found in TMDB.")

        details = await get_tmdb_details(m_type, m_id)
        if not details: return await msg.edit_text("❌ Details not found.")
        user_conversations[message.from_user.id] = { "details": details, "links": [], "state": "wait_lang" }
        await msg.edit_text(f"✅ Found: **{details.get('title') or details.get('name')}**\n\n🗣️ Enter **Language** (e.g. Hindi):")
        return

    results = await search_tmdb(query)
    if not results: return await msg.edit_text("❌ No results found.")
    buttons = []
    for r in results:
        btn_text = f"{r.get('title') or r.get('name')} ({str(r.get('release_date') or '----')[:4]})"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"sel_{r['media_type']}_{r['id']}")])
    await msg.edit_text("👇 **Select Content:**", reply_markup=InlineKeyboardMarkup(buttons))

@bot.on_callback_query(filters.regex("^sel_"))
async def on_select(client, cb):
    try:
        _, m_type, m_id = cb.data.split("_")
        details = await get_tmdb_details(m_type, m_id)
        if not details: return await cb.message.edit_text("❌ Details not found.")
        user_conversations[cb.from_user.id] = { "details": details, "links": [], "state": "wait_lang" }
        await cb.message.edit_text(f"✅ Selected: **{details.get('title') or details.get('name')}**\n\n🗣️ Enter **Language** (e.g. Hindi):")
    except Exception as e: logger.error(f"Select Error: {e}")

# ---- CONVERSATION HANDLER ----
@bot.on_message(filters.private & ~filters.command(["start", "post", "manual", "edit", "history", "setadlink", "mysettings", "auth", "ban", "stats", "broadcast", "setownerads"]))
async def text_handler(client, message):
    uid = message.from_user.id
    if uid not in user_conversations: return
    
    convo = user_conversations[uid]
    state = convo.get("state")
    text = message.text.strip() if message.text else ""
    
    if state == "manual_title":
        convo["details"]["title"] = text
        convo["state"] = "manual_plot"
        await message.reply_text("📝 এবার মুভির **গল্প/Plot** লিখুন:")
        
    elif state == "manual_plot":
        convo["details"]["overview"] = text
        convo["state"] = "manual_poster"
        await message.reply_text("🖼️ এবার একটি **পোস্টার (Photo)** সেন্ড করুন:")
        
    elif state == "manual_poster":
        if not message.photo: return await message.reply_text("⚠️ দয়া করে একটি ছবি (Photo) পাঠান।")
        msg = await message.reply_text("⏳ Processing Poster...")
        try:
            photo_path = await message.download()
            img_url = upload_to_catbox(photo_path) 
            os.remove(photo_path)
            if img_url:
                convo["details"]["manual_poster_url"] = img_url
                convo["state"] = "ask_screenshots"
                buttons = [[InlineKeyboardButton("📸 Add Screenshots", callback_data=f"ss_yes_{uid}")], [InlineKeyboardButton("⏭️ Skip", callback_data=f"ss_no_{uid}")]]
                await msg.edit_text(f"✅ Poster Uploaded!\n\n📸 **Add Custom Screenshots?**", reply_markup=InlineKeyboardMarkup(buttons))
            else: await msg.edit_text("❌ Poster Upload Failed.")
        except: await msg.edit_text("❌ Error uploading poster.")

    elif state == "wait_screenshots":
        if not message.photo: return await message.reply_text("⚠️ Please send a PHOTO for screenshot.")
        msg = await message.reply_text("⏳ Uploading Screenshot...")
        try:
            photo_path = await message.download()
            ss_url = upload_to_catbox(photo_path)
            os.remove(photo_path)
            if ss_url:
                if "manual_screenshots" not in convo["details"]: convo["details"]["manual_screenshots"] = []
                convo["details"]["manual_screenshots"].append(ss_url)
                count = len(convo["details"]["manual_screenshots"])
                buttons = [[InlineKeyboardButton("✅ DONE", callback_data=f"ss_done_{uid}")]]
                await msg.edit_text(f"✅ **Screenshot {count} Added!**\n\nSend another photo OR click DONE.", reply_markup=InlineKeyboardMarkup(buttons))
            else: await msg.edit_text("❌ Failed to upload.")
        except: await msg.edit_text("❌ Error processing.")

    elif state == "wait_lang":
        convo["details"]["custom_language"] = text
        convo["state"] = "wait_quality"
        await message.reply_text("💿 Enter **Quality** (e.g. 720p):")
        
    elif state == "wait_quality":
        convo["details"]["custom_quality"] = text
        convo["state"] = "ask_links"
        buttons = [[InlineKeyboardButton("➕ Add Links", callback_data=f"lnk_yes_{uid}")], [InlineKeyboardButton("🏁 Finish", callback_data=f"lnk_no_{uid}")]]
        await message.reply_text("🔗 Add Download Links?", reply_markup=InlineKeyboardMarkup(buttons))
        
    elif state == "wait_link_name":
        convo["temp_name"] = text
        convo["state"] = "wait_link_url"
        await message.reply_text("🔗 Enter **URL** for this button:")
        
    elif state == "wait_link_url":
        if text.startswith("http"):
            convo["links"].append({"label": convo["temp_name"], "url": text})
            # Check if it's edit mode
            if convo.get("post_id"):
                 convo["state"] = "edit_mode"
                 btns = [[InlineKeyboardButton("➕ Add Another", callback_data=f"add_lnk_edit_{uid}")],
                         [InlineKeyboardButton("✅ Generate New Code", callback_data=f"gen_edit_{uid}")]]
                 await message.reply_text(f"✅ Link Added!\n\nAdd another or Finish?", reply_markup=InlineKeyboardMarkup(btns))
            else:
                convo["state"] = "ask_links"
                buttons = [[InlineKeyboardButton("➕ Add Another", callback_data=f"lnk_yes_{uid}")], [InlineKeyboardButton("🏁 Finish", callback_data=f"lnk_no_{uid}")]]
                await message.reply_text(f"✅ Added! Total: {len(convo['links'])}", reply_markup=InlineKeyboardMarkup(buttons))
        else: await message.reply_text("⚠️ Invalid URL.")
    
    elif state == "wait_badge_text":
        convo["details"]["badge_text"] = text
        buttons = [[InlineKeyboardButton("✅ Safe", callback_data=f"safe_yes_{uid}")], [InlineKeyboardButton("🔞 18+ (Force Blur)", callback_data=f"safe_no_{uid}")]]
        await message.reply_text("🛡️ **Safety Check:**", reply_markup=InlineKeyboardMarkup(buttons))

# 🔥 HANDLERS FOR CALLBACKS
@bot.on_callback_query(filters.regex("^ss_"))
async def ss_cb(client, cb):
    try: action, uid = cb.data.rsplit("_", 1); uid = int(uid)
    except: return
    if uid != cb.from_user.id: return await cb.answer("Not for you!", show_alert=True)
    if action == "ss_yes":
        user_conversations[uid]["state"] = "wait_screenshots"
        user_conversations[uid]["details"]["manual_screenshots"] = []
        await cb.message.edit_text("📸 **Send Screenshots now.**\n(Send photos one by one)")
    elif action == "ss_no" or action == "ss_done":
        user_conversations[uid]["state"] = "wait_lang"
        ss_count = len(user_conversations[uid]["details"].get("manual_screenshots", []))
        msg_text = f"✅ Saved {ss_count} screenshots." if action == "ss_done" else "⏭️ Screenshots Skipped."
        await cb.message.edit_text(f"{msg_text}\n\n🗣️ Enter **Language** (e.g. Hindi):")

@bot.on_callback_query(filters.regex("^lnk_"))
async def link_cb(client, cb):
    try: action, uid = cb.data.rsplit("_", 1); uid = int(uid)
    except: return
    if uid != cb.from_user.id: return await cb.answer("Not for you!", show_alert=True)
    if action == "lnk_yes":
        user_conversations[uid]["state"] = "wait_link_name"
        await cb.message.edit_text("📝 বাটনের নাম লিখুন (Ex: '720p Download'):")
    else:
        user_conversations[uid]["state"] = "wait_badge_text"
        btns = [[InlineKeyboardButton("🚫 Skip Badge (No Text)", callback_data=f"skip_badge_{uid}")]]
        await cb.message.edit_text("🖼️ **পোস্টারে কোনো লেখা (Badge) বসাতে চান?**\n\nউদাহরণ: `বাংলা ডাবিং`, `Hindi Dubbed`\n_(ফেস ডিটেক্ট করে লেখাটি অটোমেটিক ফাঁকা জায়গায় বসানো হবে)_\n\n👇 নিচে লিখে পাঠান অথবা Skip করুন:", reply_markup=InlineKeyboardMarkup(btns))

# 🔥 NEW: Edit Mode Callbacks
@bot.on_callback_query(filters.regex("^add_lnk_edit_"))
async def add_lnk_edit(client, cb):
    uid = int(cb.data.split("_")[-1])
    if uid in user_conversations:
        user_conversations[uid]["state"] = "wait_link_name"
        await cb.message.edit_text("📝 বাটনের নাম লিখুন (Ex: 'Ep 5 Download'):")

@bot.on_callback_query(filters.regex("^gen_edit_"))
async def gen_edit_finish(client, cb):
    uid = int(cb.data.split("_")[-1])
    if uid in user_conversations:
        await cb.answer("⏳ Generating New Post...", show_alert=False)
        await generate_final_post(client, uid, cb.message)

@bot.on_callback_query(filters.regex("^skip_badge_"))
async def skip_badge_cb(client, cb):
    uid = int(cb.data.split("_")[-1])
    if uid in user_conversations:
        user_conversations[uid]["details"]["badge_text"] = None
        buttons = [[InlineKeyboardButton("✅ Safe", callback_data=f"safe_yes_{uid}")], [InlineKeyboardButton("🔞 18+ (Force Blur)", callback_data=f"safe_no_{uid}")]]
        await cb.message.edit_text("🛡️ **Safety Check:**\nIs this content 18+/Adult?", reply_markup=InlineKeyboardMarkup(buttons))

@bot.on_callback_query(filters.regex("^safe_"))
async def safety_cb(client, cb):
    try: action, uid = cb.data.rsplit("_", 1); uid = int(uid)
    except: return
    if uid not in user_conversations: return
    user_conversations[uid]["details"]["force_adult"] = True if action == "safe_no" else False
    await cb.message.edit_text("⏳ Generating Final Post (Fetching Ads from DB)...")
    await generate_final_post(client, uid, cb.message)

# 🔥 UPDATED: Generate Final Post (Crash Fix)
async def generate_final_post(client, uid, message):
    if uid not in user_conversations: 
        try: return await message.edit_text("❌ Session expired. Try again.")
        except: return

    convo = user_conversations[uid]
    
    # Send loading status
    try:
        status_msg = await message.edit_text("⏳ **Generating Post...**\nPlease wait while we process images & links.")
    except:
        status_msg = message # Fallback

    try:
        # 🔥 Save/Update Post in DB
        pid = await save_post_to_db(convo["details"], convo["links"])
        
        loop = asyncio.get_running_loop()
        
        # Image Generation (Safe execution)
        img_io = None
        poster_bytes = None
        try:
            img_io, poster_bytes = await loop.run_in_executor(None, generate_image, convo["details"])
        except Exception as e:
            logger.error(f"Image Gen Failed: {e}")

        # Update Poster URL if new badge applied
        if convo["details"].get("badge_text") and poster_bytes:
            new_poster_url = await loop.run_in_executor(None, upload_to_catbox_bytes, poster_bytes)
            if new_poster_url: convo["details"]["manual_poster_url"] = new_poster_url 
        
        my_ad_links = await get_user_ads(uid)
        owner_ad_links = await get_owner_ads()
        
        html = generate_html_code(convo["details"], convo["links"], my_ad_links, owner_ad_links)
        caption = generate_formatted_caption(convo["details"], pid)
        convo["final"] = {"html": html}
        
        btns = [[InlineKeyboardButton("📄 Get Blogger Code", callback_data=f"get_code_{uid}")]]
        
        # 1. Send Result to User
        if img_io:
            await client.send_photo(message.chat.id, img_io, caption=caption, reply_markup=InlineKeyboardMarkup(btns))
            # Delete status message
            try: await status_msg.delete()
            except: pass
        else:
            await client.send_message(message.chat.id, caption, reply_markup=InlineKeyboardMarkup(btns))
            try: await status_msg.delete()
            except: pass
        
        # 🔥 2. SEND TO LOG CHANNEL
        if LOG_CHANNEL_ID and LOG_CHANNEL_ID != 0 and img_io:
            img_io.seek(0)
            user_info = await client.get_users(uid)
            log_caption = caption + f"\n\n👤 **Generated By:** {user_info.mention} (`{uid}`)\n🕒 **Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
            try: await client.send_photo(LOG_CHANNEL_ID, img_io, caption=log_caption)
            except: pass
            
    except Exception as e:
        logger.error(f"Post Generation Critical Error: {e}")
        try:
            await status_msg.edit_text(f"❌ **Error:** Something went wrong.\n`{str(e)}`")
        except:
            await client.send_message(message.chat.id, f"❌ **Error:** Something went wrong during post generation.\n`{str(e)}`")

@bot.on_callback_query(filters.regex("^get_code_"))
async def get_code(client, cb):
    try: _, _, uid = cb.data.rsplit("_", 2); uid = int(uid)
    except: return
    data = user_conversations.get(uid, {})
    if "final" not in data: return await cb.answer("Expired.", show_alert=True)
    
    await cb.answer("⏳ Uploading to Dpaste...", show_alert=False)
    link = await create_paste_link(data["final"]["html"])
    
    if link: await cb.message.reply_text(f"✅ **Code Ready!**\n\n👇 Copy:\n{link}", disable_web_page_preview=True)
    else:
        file = io.BytesIO(data["final"]["html"].encode())
        file.name = "blogger_post.html"
        await client.send_document(cb.message.chat.id, file, caption="⚠️ Link failed. File attached.")

# ---- ENTRY POINT ----
if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    ping_thread = Thread(target=keep_alive_pinger)
    ping_thread.daemon = True
    ping_thread.start()
    
    print("🚀 Ultimate Bot Started (v40 - Stable Edit)!")
    bot.run()
