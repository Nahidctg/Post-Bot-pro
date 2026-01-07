# -*- coding: utf-8 -*-

import os
import io
import re
import json
import time
import asyncio
import logging
import random
import aiohttp
import requests 
import urllib3 # SSL Warning বন্ধ করার জন্য
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

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# SSL Warnings বন্ধ করা (ISP ব্লকিং বাইপাস করার জন্য জরুরি)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables
load_dotenv()

# ---- CONFIGURATION ----
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# Check Variables
if not all([BOT_TOKEN, API_ID, API_HASH, TMDB_API_KEY]):
    logger.critical("❌ FATAL ERROR: Variables missing in .env file!")
    exit(1)

# ====================================================================
# 🔥 OWNER PROFIT SETUP
# ====================================================================
OWNER_AD_LINKS = [
    "https://www.effectivegatecpm.com/c90zejmfrg?key=45a67d2f1523ee6b3988c4cc8f764a35",
    "https://www.effectivegatecpm.com/q5cpmxwy44?key=075b9f116b4174922cadfae2d3291743",
    "https://www.effectivegatecpm.com/p4bm30ss3?key=8bb102e9258871570c79a9a90fa3cf9f"
]

# ---- GLOBAL STATE ----
user_conversations = {}
user_ad_links = {} 
USER_AD_LINKS_FILE = "user_ad_links.json"
DEFAULT_AD_LINKS = [
    "https://www.google.com", 
    "https://www.bing.com"
] 

# ---- RESOURCES URLS (Fallback) ----
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

# ---- PERSISTENCE FUNCTIONS ----
def save_json(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Save JSON Error: {e}")

def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                data = json.load(f)
                processed_data = {}
                for k, v in data.items():
                    if isinstance(v, str):
                        processed_data[int(k)] = [v]
                    else:
                        processed_data[int(k)] = v
                return processed_data
        except Exception as e:
            logger.error(f"Load JSON Error: {e}")
    return {}

# Load saved data
user_ad_links = load_json(USER_AD_LINKS_FILE)

# ---- FLASK KEEP-ALIVE ----
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot is Running! (Fixed Icons & Speed Optimized)"

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
# 🔥 ULTRA POWERFUL UPLOAD FUNCTION (Optimized for Speed)
# ====================================================================

def upload_image_core(file_content):
    """
    Tries 3 servers with Optimized Timeouts (Fast Response)
    """
    # 1. Try 0x0.st (Fastest)
    try:
        url = "https://0x0.st"
        files = {'file': ('image.jpg', file_content)}
        # Timeout reduced to 5s for speed, verify=False for ISP bypass
        response = requests.post(url, files=files, timeout=5, verify=False)
        if response.status_code == 200:
            link = response.text.strip()
            return link
    except Exception as e:
        pass 

    # 2. Try Catbox.moe (Reliable)
    try:
        url = "https://catbox.moe/user/api.php"
        data = {"reqtype": "fileupload", "userhash": ""}
        files = {"fileToUpload": ("image.png", file_content, "image/png")}
        headers = {"User-Agent": "Mozilla/5.0"}
        # Timeout reduced to 6s
        response = requests.post(url, data=data, files=files, headers=headers, timeout=6, verify=False)
        if response.status_code == 200:
            link = response.text.strip()
            return link
    except Exception as e:
        pass

    # 3. Try Graph.org (Telegraph) - Backup
    try:
        url = "https://graph.org/upload"
        files = {'file': ('image.jpg', file_content, 'image/jpeg')}
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.post(url, files=files, headers=headers, timeout=5, verify=False)
        if response.status_code == 200:
            json_data = response.json()
            link = "https://graph.org" + json_data[0]["src"]
            return link
    except Exception as e:
        pass

    logger.error("❌ All upload servers failed.")
    return None

def upload_to_catbox_bytes(img_bytes):
    try:
        if hasattr(img_bytes, 'read'):
            img_bytes.seek(0)
            data = img_bytes.read()
        else:
            data = img_bytes
        return upload_image_core(data)
    except Exception as e:
        logger.error(f"Byte Process Error: {e}")
        return None

def upload_to_catbox(file_path):
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        return upload_image_core(data)
    except Exception as e:
        logger.error(f"File Read Error: {e}")
        return None

# ---- TMDB & LINK EXTRACTION ----
def extract_tmdb_id(text):
    tmdb_match = re.search(r'themoviedb\.org/(movie|tv)/(\d+)', text)
    if tmdb_match:
        return tmdb_match.group(1), tmdb_match.group(2)
    imdb_match = re.search(r'(tt\d+)', text)
    if imdb_match:
        return "imdb", imdb_match.group(1)
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
    except Exception as e:
        logger.error(f"TMDB Search Error: {e}")
        return []

async def get_tmdb_details(media_type, media_id):
    url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={TMDB_API_KEY}&append_to_response=credits,similar"
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
# 🔥 FACE DETECTION & SMART BADGE PLACEMENT SYSTEM
# ============================================================================
def get_smart_badge_position(pil_img):
    try:
        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        
        cascade_path = "haarcascade_frontalface_default.xml"
        if not os.path.exists(cascade_path):
            return int(pil_img.height * 0.40) 

        face_cascade = cv2.CascadeClassifier(cascade_path)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        height = pil_img.height
        
        if len(faces) > 0:
            lowest_y = 0
            for (x, y, w, h) in faces:
                bottom_of_face = y + h
                if bottom_of_face > lowest_y:
                    lowest_y = bottom_of_face
            
            target_y = lowest_y + 40 
            if target_y > (height - 130):
                return 80 
            return target_y
        else:
            return int(height * 0.40) 
            
    except Exception as e:
        logger.error(f"Face Detect Error: {e}")
        return 200

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
        draw_overlay = ImageDraw.Draw(overlay)
        draw_overlay.rectangle(
            [pos_x, pos_y, pos_x + box_w, pos_y + box_h], 
            fill=(0, 0, 0, 220) 
        )
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
    except Exception as e:
        logger.error(f"Badge Apply Error: {e}")
        return io.BytesIO(poster_bytes)

# ============================================================================
# 🔥 OPTIMIZED HTML GENERATOR (Fixed Icons Issue)
# ============================================================================
def generate_html_code(data, links, ad_links_list):
    title = data.get("title") or data.get("name")
    overview = data.get("overview", "")
    poster = data.get('manual_poster_url') or f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}"
    BTN_TELEGRAM = "https://i.ibb.co/kVfJvhzS/photo-2025-12-23-12-38-56-7587031987190235140.jpg"

    # 🔥 MIX AD LINKS & SHUFFLE (Ensure Rotation)
    final_ad_list = list(ad_links_list)
    if OWNER_AD_LINKS:
        final_ad_list.extend(OWNER_AD_LINKS)
    
    random.shuffle(final_ad_list) 

    style_html = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');
        body { margin: 0; padding: 10px; background-color: #121212; font-family: 'Poppins', sans-serif; color: #fff; }
        .main-card {
            max-width: 600px; margin: 0 auto; background: #1e1e1e;
            border: 1px solid #333; border-radius: 15px; padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5); text-align: center;
        }
        .poster-img {
            width: 100%; max-width: 250px; border-radius: 10px;
            box-shadow: 0 0 10px rgba(0,0,0,0.5); margin-bottom: 15px;
        }
        h2 { color: #00d2ff; margin: 10px 0; font-size: 22px; font-weight: 700; }
        p { text-align: justify; color: #bbb; font-size: 13px; margin-bottom: 20px; line-height: 1.5; }
        
        .dl-item { background: #252525; padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #333; }
        .dl-link-label { display: block; font-size: 16px; color: #ffeb3b; margin-bottom: 10px; font-weight: 600; text-transform: uppercase; }
        
        /* 🔥 Optimized Gradient Button */
        .rgb-btn {
            width: 100%; padding: 14px; font-size: 18px; font-weight: bold;
            color: white; border: none; border-radius: 8px; cursor: pointer;
            background: linear-gradient(45deg, #FF512F, #DD2476);
            box-shadow: 0 4px 10px rgba(221, 36, 118, 0.4);
            transition: all 0.3s ease; text-decoration: none; display: inline-block;
            display: flex; align-items: center; justify-content: center; gap: 10px;
        }
        .rgb-btn:active { transform: scale(0.98); }
        .rgb-btn.processing { background: #555; cursor: wait; box-shadow: none; }
        
        .instruction-box {
            background: rgba(255,255,255,0.05); padding: 10px; 
            border-radius: 8px; margin-bottom: 20px; 
            font-size: 12px; color: #aaa; text-align: left;
            border-left: 3px solid #ffeb3b;
        }
    </style>
    """

    links_html = ""
    for idx, link in enumerate(links):
        links_html += f"""
        <div class="dl-item">
            <span class="dl-link-label">📂 {link['label']}</span>
            <!-- Unique ID for each button area -->
            <div id="area-{idx}">
                <button class="rgb-btn" data-clicks="0" onclick="processLink(this, '{link['url']}', 'area-{idx}')">
                    ⬇️ DOWNLOAD / WATCH
                </button>
            </div>
        </div>"""

    # 🔥 Optimized JavaScript (Fixed .innerHTML for Icons)
    script_html = f"""
    <script>
    const AD_LINKS = {json.dumps(final_ad_list)};
    const MAX_CLICKS = 1; 

    function processLink(btn, realUrl, areaId) {{
        let clicks = parseInt(btn.getAttribute('data-clicks') || 0);
        
        // 1. Button Feedback
        btn.innerHTML = "⏳ Verifying..."; 
        btn.classList.add('processing');
        btn.disabled = true;

        setTimeout(() => {{
            btn.disabled = false;
            btn.classList.remove('processing');

            if (clicks < MAX_CLICKS) {{
                // Open Random Ad
                let randomAd = AD_LINKS[Math.floor(Math.random() * AD_LINKS.length)];
                window.open(randomAd, '_blank');
                
                btn.setAttribute('data-clicks', clicks + 1);
                
                // 🔥 FIX: Using innerHTML allows special characters/icons
                btn.innerHTML = "&#8635; Click Again (Get Link)"; 
            }} else {{
                // Success State - Show Green Button
                btn.style.display = 'none';
                let area = document.getElementById(areaId);
                
                let successBtn = document.createElement('a');
                successBtn.href = realUrl;
                successBtn.className = 'rgb-btn';
                successBtn.style.background = '#00C853'; // Green
                successBtn.style.backgroundImage = 'none';
                successBtn.style.boxShadow = '0 4px 10px rgba(0, 200, 83, 0.4)';
                
                // 🔥 FIX: Using innerHTML here too
                successBtn.innerHTML = "&#9989; OPEN LINK";
                
                successBtn.target = "_blank";
                area.appendChild(successBtn);
            }}
        }}, 800); 
    }}
    </script>
    """

    return f"""
    <!-- Optimized Bot Post -->
    {style_html}
    <div class="main-card">
        <img src="{poster}" class="poster-img">
        <h2>{title}</h2>
        <p>{overview[:350]}...</p>
        
        <div class="instruction-box">
            ℹ️ <b>How to Download:</b><br>
            1. Click the <b>Download</b> button.<br>
            2. If an ad opens, verify and go back.<br>
            3. Click the <b>Green Button</b> to get link.
        </div>

        <div class="dl-container-area">{links_html}</div>
        
        <div style="margin-top: 20px; border-top: 1px solid #333; padding-top: 15px;">
            <a href="https://t.me/+6hvCoblt6CxhZjhl" target="_blank">
                <img src="{BTN_TELEGRAM}" style="width: 100%; max-width: 300px; border-radius: 50px; border: 2px solid #333;">
            </a>
        </div>
    </div>
    {script_html}
    """

# ---- IMAGE & CAPTION GENERATOR ----
def generate_formatted_caption(data):
    title = data.get("title") or data.get("name") or "N/A"
    
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
    
    caption = f"🎬 **{title} ({year})**\n\n"
    if not data.get('is_manual'):
        caption += f"**🎭 Genres:** {genres}\n**🗣️ Language:** {language}\n**⭐ Rating:** {rating}\n\n"
    caption += f"**📝 Plot:** _{overview[:300]}..._"
    return caption

def generate_image(data):
    try:
        if data.get('manual_poster_url'):
            poster_url = data.get('manual_poster_url')
        else:
            poster_url = f"https://image.tmdb.org/t/p/w500{data['poster_path']}" if data.get('poster_path') else None
        
        if not poster_url: return None, None

        # verify=False here too
        poster_bytes = requests.get(poster_url, timeout=10, verify=False).content
        
        if data.get('badge_text'):
            badge_io = apply_badge_to_poster(poster_bytes, data['badge_text'])
            poster_bytes = badge_io.getvalue()

        poster_img = Image.open(io.BytesIO(poster_bytes)).convert("RGBA").resize((400, 600))
        
        bg_img = Image.new('RGBA', (1280, 720), (10, 10, 20))
        backdrop = None
        if data.get('backdrop_path') and not data.get('is_manual'):
            try:
                bd_url = f"https://image.tmdb.org/t/p/w1280{data['backdrop_path']}"
                bd_bytes = requests.get(bd_url, timeout=10, verify=False).content
                backdrop = Image.open(io.BytesIO(bd_bytes)).convert("RGBA").resize((1280, 720))
            except: pass
        
        if not backdrop:
            backdrop = poster_img.resize((1280, 720))
            
        backdrop = backdrop.filter(ImageFilter.GaussianBlur(10))
        bg_img = Image.alpha_composite(backdrop, Image.new('RGBA', (1280, 720), (0, 0, 0, 150))) 

        bg_img.paste(poster_img, (50, 60), poster_img)
        draw = ImageDraw.Draw(bg_img)
        
        f_bold = get_font(size=36, bold=True)
        f_reg = get_font(size=24, bold=False)

        title = data.get("title") or data.get("name")
        year = (data.get("release_date") or data.get("first_air_date") or "----")[:4]
        if data.get('is_manual'): year = ""

        draw.text((480, 80), f"{title} {year}", font=f_bold, fill="white", stroke_width=1, stroke_fill="black")
        
        if not data.get('is_manual'):
            draw.text((480, 140), f"⭐ {data.get('vote_average', 0):.1f}/10", font=f_reg, fill="#00e676")
            draw.text((480, 180), " | ".join([g["name"] for g in data.get("genres", [])]), font=get_font(18), fill="#00bcd4")
        
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
    user_conversations.pop(message.from_user.id, None)
    await message.reply_text(
        "🎬 **Movie & Series Bot (Fixed Icons & Speed v22)**\n\n"
        "⚡ `/post <Link or Name>` - Auto Post\n"
        "✍️ `/manual` - Custom Manual Post\n"
        "🛠 `/mysettings` - View Your Ad Links\n"
        "⚙️ `/setadlink <URL1> <URL2>` - Set Ad Links"
    )

@bot.on_message(filters.command("mysettings") & filters.private)
async def mysettings_cmd(client, message):
    uid = message.from_user.id
    my_links = user_ad_links.get(uid, DEFAULT_AD_LINKS)
    links_str = "\n".join([f"{i+1}. {l}" for i, l in enumerate(my_links)])
    await message.reply_text(f"⚙️ **MY SETTINGS**\n\n🔗 **Your Ad Links:**\n{links_str}", disable_web_page_preview=True)

@bot.on_message(filters.command("setadlink") & filters.private)
async def set_ad(client, message):
    if len(message.command) > 1:
        raw_links = message.text.split(None, 1)[1].split()
        valid_links = [l for l in raw_links if l.startswith("http")]
        if valid_links:
            user_ad_links[message.from_user.id] = valid_links
            save_json(USER_AD_LINKS_FILE, user_ad_links)
            links_str = "\n".join([f"{i+1}. {l}" for i, l in enumerate(valid_links)])
            await message.reply_text(f"✅ **Ad Links Saved!** ({len(valid_links)} links)\n\n{links_str}")
        else:
            await message.reply_text("⚠️ Invalid Links. Must start with http/https.")
    else:
        await message.reply_text("⚠️ Usage Example:\n`/setadlink https://site1.com https://site2.com`")

@bot.on_message(filters.command("manual") & filters.private)
async def manual_post_cmd(client, message):
    uid = message.from_user.id
    user_conversations[uid] = {
        "details": {"is_manual": True}, 
        "links": [], 
        "state": "manual_title"
    }
    await message.reply_text("✍️ **Manual Post Started**\n\nপ্রথমে **টাইটেল (Title)** লিখুন:")

@bot.on_message(filters.command("post") & filters.private)
async def post_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("⚠️ Usage:\n`/post Avatar` (Search by Name)\n`/post https://...` (By TMDB/IMDb Link)")
    
    query = message.text.split(" ", 1)[1].strip()
    msg = await message.reply_text(f"🔎 Processing `{query}`...")

    m_type, m_id = extract_tmdb_id(query)

    if m_type and m_id:
        if m_type == "imdb":
            find_url = f"https://api.themoviedb.org/3/find/{m_id}?api_key={TMDB_API_KEY}&external_source=imdb_id"
            data = await fetch_url(find_url)
            results = data.get("movie_results", []) + data.get("tv_results", [])
            if results:
                m_type = results[0]['media_type']
                m_id = results[0]['id']
            else:
                return await msg.edit_text("❌ IMDb ID not found in TMDB database.")

        details = await get_tmdb_details(m_type, m_id)
        if not details: return await msg.edit_text("❌ Details not found from Link.")
        
        user_conversations[message.from_user.id] = {
            "details": details, "links": [], "state": "wait_lang"
        }
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

        user_conversations[cb.from_user.id] = {
            "details": details, "links": [], "state": "wait_lang"
        }
        await cb.message.edit_text(f"✅ Selected: **{details.get('title') or details.get('name')}**\n\n🗣️ Enter **Language** (e.g. Hindi):")
    except Exception as e:
        logger.error(f"Select Error: {e}")

# ---- CONVERSATION HANDLER ----
@bot.on_message(filters.private & ~filters.command(["start", "post", "manual", "setadlink", "mysettings"]))
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
        msg = await message.reply_text("⏳ Processing Image (0x0.st / Catbox)...")
        try:
            photo_path = await message.download()
            img_url = upload_to_catbox(photo_path) # Multi-Server Logic
            os.remove(photo_path)
            if img_url:
                convo["details"]["manual_poster_url"] = img_url
                convo["state"] = "ask_links"
                buttons = [[InlineKeyboardButton("➕ Add Links", callback_data=f"lnk_yes_{uid}")], [InlineKeyboardButton("🏁 Finish", callback_data=f"lnk_no_{uid}")]]
                await msg.edit_text(f"✅ ছবি আপলোড হয়েছে!\n🔗 Link: {img_url}\n\n🔗 এবার ডাউনলোড লিংক অ্যাড করবেন?", reply_markup=InlineKeyboardMarkup(buttons))
            else: await msg.edit_text("❌ ইমেজ আপলোড ফেইল হয়েছে। (Try again later)")
        except: await msg.edit_text("❌ কোড ক্র্যাশ করেছে।")

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
            convo["state"] = "ask_links"
            buttons = [[InlineKeyboardButton("➕ Add Another", callback_data=f"lnk_yes_{uid}")], [InlineKeyboardButton("🏁 Finish", callback_data=f"lnk_no_{uid}")]]
            await message.reply_text(f"✅ Added! Total: {len(convo['links'])}", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await message.reply_text("⚠️ Invalid URL. Try again.")
    
    elif state == "wait_badge_text":
        convo["details"]["badge_text"] = text
        await message.reply_text(f"✅ ব্যাজ যুক্ত করা হচ্ছে: **{text}**\n\n🕵️‍♂️ **Detecting Faces to avoid covering...**\n⏳ Generating Final Post...")
        await generate_final_post(client, uid, message)

@bot.on_callback_query(filters.regex("^lnk_"))
async def link_cb(client, cb):
    try:
        action, uid_str = cb.data.rsplit("_", 1)
        uid = int(uid_str)
    except: return
    
    if uid != cb.from_user.id: return await cb.answer("Not for you!", show_alert=True)
    
    if action == "lnk_yes":
        user_conversations[uid]["state"] = "wait_link_name"
        await cb.message.edit_text("📝 বাটনের নাম লিখুন (Ex: '720p Download' or 'Watch Online'):")
    else:
        user_conversations[uid]["state"] = "wait_badge_text"
        btns = [[InlineKeyboardButton("🚫 Skip Badge (No Text)", callback_data=f"skip_badge_{uid}")]]
        await cb.message.edit_text(
            "🖼️ **পোস্টারে কোনো লেখা (Badge) বসাতে চান?**\n\n"
            "উদাহরণ: `বাংলা ডাবিং`, `Hindi Dubbed`\n"
            "_(ফেস ডিটেক্ট করে লেখাটি অটোমেটিক ফাঁকা জায়গায় বসানো হবে)_\n\n"
            "👇 নিচে লিখে পাঠান অথবা Skip করুন:", 
            reply_markup=InlineKeyboardMarkup(btns)
        )

@bot.on_callback_query(filters.regex("^skip_badge_"))
async def skip_badge_cb(client, cb):
    uid = int(cb.data.split("_")[-1])
    if uid in user_conversations:
        user_conversations[uid]["details"]["badge_text"] = None
        await cb.message.edit_text("⏳ Generating Final Post...")
        await generate_final_post(client, uid, cb.message)

async def generate_final_post(client, uid, message):
    if uid not in user_conversations: return await message.edit_text("❌ Session expired.")
    convo = user_conversations[uid]
    
    loop = asyncio.get_running_loop()
    
    img_io, poster_bytes = await loop.run_in_executor(None, generate_image, convo["details"])
    
    if convo["details"].get("badge_text") and poster_bytes:
        new_poster_url = await loop.run_in_executor(None, upload_to_catbox_bytes, poster_bytes)
        if new_poster_url:
            convo["details"]["manual_poster_url"] = new_poster_url 
    
    my_ad_links = user_ad_links.get(uid, DEFAULT_AD_LINKS)
    html = generate_html_code(convo["details"], convo["links"], my_ad_links)
    
    caption = generate_formatted_caption(convo["details"])
    convo["final"] = {"html": html}
    
    btns = [[InlineKeyboardButton("📄 Get Blogger Code", callback_data=f"get_code_{uid}")]]
    
    try:
        if img_io:
            await client.send_photo(message.chat.id, img_io, caption=caption, reply_markup=InlineKeyboardMarkup(btns))
            await message.delete()
        else:
            await message.edit_text(caption, reply_markup=InlineKeyboardMarkup(btns))
    except Exception as e:
        logger.error(f"Post Send Error: {e}")
        await message.edit_text("❌ Error sending post.")

@bot.on_callback_query(filters.regex("^get_code_"))
async def get_code(client, cb):
    try:
        _, _, uid_str = cb.data.rsplit("_", 2)
        uid = int(uid_str)
    except: return

    data = user_conversations.get(uid, {})
    if "final" not in data: return await cb.answer("Expired.", show_alert=True)
    
    await cb.answer("⏳ Uploading to Dpaste...", show_alert=False)
    link = await create_paste_link(data["final"]["html"])
    
    if link:
        await cb.message.reply_text(f"✅ **Code Ready!**\n\n👇 Copy:\n{link}", disable_web_page_preview=True)
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
    
    print("🚀 Bot Started (Fixed Icons & Speed v22)!")
    bot.run()
