# -*- coding: utf-8 -*-

# 🔥 PYTHON 3.13 ASYNCIO FIX (MAGIC BYPASS) 🔥
import asyncio
if not hasattr(asyncio, 'coroutine'):
    asyncio.coroutine = lambda f: f

import os
import io
import re
import importlib
import pkgutil
import json
import time
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

# 🔥 ফাইল স্টোর চ্যানেল
DB_CHANNEL_ID = int(os.getenv("DB_CHANNEL_ID", 0)) 

# --- WORKER GLOBAL VARIABLE ---
worker_client = None

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
DEFAULT_OWNER_AD_LINKS = ["https://www.google.com", "https://www.bing.com"]
DEFAULT_USER_AD_LINKS = ["https://www.google.com", "https://www.bing.com"] 

user_conversations = {}

# 🔥 BATCH UPLOAD QUEUE LIMITER
upload_semaphore = asyncio.Semaphore(2)

# ---- DATABASE FUNCTIONS (100% PRESERVED) ----
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
    await settings_col.update_one({"_id": "main_config"}, {"$set": {"owner_ads": links}}, upsert=True)

async def get_auto_delete_timer():
    data = await settings_col.find_one({"_id": "main_config"})
    return data.get("auto_delete_seconds", 600) if data else 600

async def set_auto_delete_timer_db(seconds):
    await settings_col.update_one({"_id": "main_config"}, {"$set": {"auto_delete_seconds": int(seconds)}}, upsert=True)

async def auto_delete_task(client, chat_id, message_ids, delay):
    if delay <= 0: return
    await asyncio.sleep(delay)
    try: await client.delete_messages(chat_id, message_ids)
    except Exception as e: logger.error(f"Auto Delete Error: {e}")

async def get_admin_share():
    data = await settings_col.find_one({"_id": "main_config"})
    return data.get("admin_share_percent", 20) if data else 20

async def set_admin_share_db(percent):
    await settings_col.update_one({"_id": "main_config"}, {"$set": {"admin_share_percent": int(percent)}}, upsert=True)

async def get_user_ads(user_id):
    data = await user_settings_col.find_one({"_id": user_id})
    return data.get("ad_links", DEFAULT_USER_AD_LINKS) if data else DEFAULT_USER_AD_LINKS

async def save_user_ads(user_id, links):
    await user_settings_col.update_one({"_id": user_id}, {"$set": {"ad_links": links}}, upsert=True)

async def get_all_users_count():
    return await users_col.count_documents({})

# --- WORKER FUNCTIONS (100% PRESERVED) ---
async def get_worker_session():
    data = await settings_col.find_one({"_id": "worker_config"})
    return data.get("session_string") if data else None

async def set_worker_session_db(session_string):
    await settings_col.update_one({"_id": "worker_config"}, {"$set": {"session_string": session_string}}, upsert=True)

async def start_worker():
    global worker_client
    session = await get_worker_session()
    if session:
        try:
            worker_client = Client("worker_session", session_string=session, api_id=int(API_ID), api_hash=API_HASH)
            await worker_client.start()
            logger.info("✅ Worker Session Started!")
        except Exception as e:
            logger.error(f"❌ Worker Error: {e}")
            worker_client = None

async def get_server_api(server_name):
    data = await settings_col.find_one({"_id": "api_keys"})
    return data.get(server_name) if data else None

async def set_server_api(server_name, api_key):
    await settings_col.update_one({"_id": "api_keys"}, {"$set": {server_name: api_key}}, upsert=True)

def generate_short_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

async def save_post_to_db(post_data, links):
    pid = post_data.get("post_id") or generate_short_id()
    post_data["post_id"] = pid
    save_data = {"_id": pid, "details": post_data, "links": links, "updated_at": datetime.datetime.now()}
    await posts_col.replace_one({"_id": pid}, save_data, upsert=True)
    return pid

# --- RESOURCES ---
URL_FONT = "https://raw.githubusercontent.com/mahabub81/bangla-fonts/master/Kalpurush.ttf"
URL_MODEL = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"

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

# --- FLASK KEEP-ALIVE ---
app = Flask(__name__)
@app.route('/')
def home(): return "🤖 Ultimate Bot Running"
def run_flask(): app.run(host='0.0.0.0', port=8080)
def keep_alive_pinger():
    while True:
        try: requests.get("http://localhost:8080"); time.sleep(600)
        except: time.sleep(600)

def setup_resources():
    if not os.path.exists("kalpurush.ttf"):
        try: r = requests.get(URL_FONT); open("kalpurush.ttf", "wb").write(r.content)
        except: pass
    if not os.path.exists("haarcascade_frontalface_default.xml"):
        try: r = requests.get(URL_MODEL); open("haarcascade_frontalface_default.xml", "wb").write(r.content)
        except: pass
setup_resources()

def get_font(size=60, bold=False):
    try:
        if os.path.exists("kalpurush.ttf"): return ImageFont.truetype("kalpurush.ttf", size)
        return ImageFont.load_default()
    except: return ImageFont.load_default()

def upload_image_core(file_content):
    try:
        url = "https://catbox.moe/user/api.php"
        data = {"reqtype": "fileupload"}
        files = {"fileToUpload": ("image.png", file_content, "image/png")}
        response = requests.post(url, data=data, files=files, timeout=10, verify=False)
        if response.status_code == 200: return response.text.strip()
    except: pass
    return None

def upload_to_catbox_bytes(img_bytes):
    try: return upload_image_core(img_bytes.read() if hasattr(img_bytes, 'read') else img_bytes)
    except: return None

def upload_to_catbox(file_path):
    try:
        with open(file_path, "rb") as f: return upload_image_core(f.read())
    except: return None

# --- TMDB & IMAGE PROCESSING (100% PRESERVED) ---
def extract_tmdb_id(text):
    tmdb_match = re.search(r'themoviedb\.org/(movie|tv)/(\d+)', text)
    if tmdb_match: return tmdb_match.group(1), tmdb_match.group(2)
    imdb_match = re.search(r'imdb\.com/title/(tt\d+)', text) or re.search(r'(tt\d{6,})', text)
    if imdb_match: return "imdb", imdb_match.group(1)
    return None, None

async def search_tmdb(query):
    match = re.search(r'(.+?)\s*\(?(\d{4})\)?$', query)
    name, year = (match.group(1).strip(), match.group(2)) if match else (query.strip(), None)
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={name}&include_adult=true"
    if year: url += f"&year={year}"
    data = await fetch_url(url)
    return [r for r in data.get("results", []) if r.get("media_type") in ["movie", "tv"]][:15] if data else []

async def get_tmdb_details(media_type, media_id):
    url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={TMDB_API_KEY}&append_to_response=credits,similar,images,videos&include_image_language=en,null"
    return await fetch_url(url)

async def create_paste_link(content):
    url = "https://dpaste.com/api/"
    data = {"content": content, "syntax": "html", "expiry_days": 14}
    link = await fetch_url(url, method="POST", data=data)
    return link.strip() if link and "dpaste.com" in link else None

def get_smart_badge_position(pil_img):
    try:
        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        if len(faces) > 0:
            lowest_y = max([y + h for (x, y, w, h) in faces])
            target_y = lowest_y + 40
            return target_y if target_y < (pil_img.height - 130) else 80
        return int(pil_img.height * 0.40)
    except: return 200

def apply_badge_to_poster(poster_bytes, text):
    try:
        base_img = Image.open(io.BytesIO(poster_bytes)).convert("RGBA")
        width, height = base_img.size
        font = get_font(size=70)
        pos_y = get_smart_badge_position(base_img)
        draw = ImageDraw.Draw(base_img)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = bbox[2]-bbox[0], bbox[3]-bbox[1]
        box_w, box_h = text_w + 80, text_h + 40
        pos_x = (width - box_w) // 2
        overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).rectangle([pos_x, pos_y, pos_x + box_w, pos_y + box_h], fill=(0, 0, 0, 150))
        base_img = Image.alpha_composite(base_img, overlay)
        draw = ImageDraw.Draw(base_img)
        colors = ["#FFEB3B", "#FF5722"]
        words = text.split()
        if len(words) >= 2:
            draw.text((pos_x + 40, pos_y + 8), words[0], font=font, fill=colors[0])
            w1 = draw.textlength(words[0], font=font)
            draw.text((pos_x + 40 + w1 + 15, pos_y + 8), " ".join(words[1:]), font=font, fill=colors[1])
        else:
            draw.text((pos_x + 40, pos_y + 8), text, font=font, fill=colors[0])
        buf = io.BytesIO(); base_img.save(buf, format="PNG"); buf.seek(0)
        return buf
    except: return io.BytesIO(poster_bytes)

# ============================================================================
# 🔥 ADVANCED HTML GENERATOR (100% PRESERVED - EXACTLY AS ORIGINAL)
# ============================================================================
def generate_html_code(data, links, user_ad_links_list, owner_ad_links_list, admin_share_percent=20):
    title = data.get("title") or data.get("name")
    overview = data.get("overview", "No plot available.")
    poster = data.get('manual_poster_url') or f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}"
    BTN_TELEGRAM = "https://i.ibb.co/kVfJvhzS/photo-2025-12-23-12-38-56-7587031987190235140.jpg"
    is_adult = data.get('adult', False) or data.get('force_adult', False)
    theme = data.get("theme", "netflix")

    if theme == "netflix":
        root_css = "--bg-color: #0f0f13; --box-bg: #1a1a24; --text-main: #ffffff; --text-muted: #d1d1d1; --primary: #E50914; --accent: #00d2ff; --border: #2a2a35; --btn-grad: linear-gradient(90deg, #E50914 0%, #ff5252 100%); --btn-shadow: 0 4px 15px rgba(229, 9, 20, 0.4);"
    elif theme == "prime":
        root_css = "--bg-color: #0f171e; --box-bg: #1b2530; --text-main: #ffffff; --text-muted: #8197a4; --primary: #00A8E1; --accent: #00A8E1; --border: #2c3e50; --btn-grad: linear-gradient(90deg, #00A8E1 0%, #00d2ff 100%); --btn-shadow: 0 4px 15px rgba(0, 168, 225, 0.4);"
    elif theme == "light":
        root_css = "--bg-color: #f4f4f9; --box-bg: #ffffff; --text-main: #333333; --text-muted: #555555; --primary: #6200ea; --accent: #6200ea; --border: #dddddd; --btn-grad: linear-gradient(90deg, #6200ea 0%, #b388ff 100%); --btn-shadow: 0 4px 15px rgba(98, 0, 234, 0.4);"
    else:
        root_css = "--bg-color: #0f0f13; --box-bg: #1a1a24; --text-main: #ffffff; --text-muted: #d1d1d1; --primary: #E50914; --accent: #00d2ff; --border: #2a2a35; --btn-grad: linear-gradient(90deg, #E50914 0%, #ff5252 100%); --btn-shadow: 0 4px 15px rgba(229, 9, 20, 0.4);"

    lang_str = data.get('custom_language', 'Dual Audio').strip()
    year = str(data.get("release_date") or data.get("first_air_date") or "----")[:4]
    rating = f"{data.get('vote_average', 0):.1f}/10"
    
    genres_list = [g['name'] for g in data.get('genres',[])]
    genres_str = ", ".join(genres_list) if genres_list else "Movie"
    runtime = data.get('runtime') or (data.get('episode_run_time',[0])[0] if data.get('episode_run_time') else "N/A")
    runtime_str = f"{runtime} min" if runtime != "N/A" else "N/A"
    cast_list = data.get('credits', {}).get('cast',[])
    cast_names = ", ".join([c['name'] for c in cast_list[:4]]) if cast_list else "Unknown"

    poster_html = f'<div class="nsfw-container" onclick="revealNSFW(this)"><img src="{poster}" class="nsfw-blur"><div class="nsfw-warning">🔞 18+</div></div>' if is_adult else f'<img src="{poster}">'
    
    trailer_key = next((v['key'] for v in data.get('videos', {}).get('results', []) if v['type'] == 'Trailer' and v['site'] == 'YouTube'), "")
    trailer_html = f'<div class="section-title">🎬 Trailer</div><div class="video-container"><iframe src="https://www.youtube.com/embed/{trailer_key}" allowfullscreen></iframe></div>' if trailer_key else ""

    ss_html = ""
    screenshots = data.get('manual_screenshots',[]) or [f"https://image.tmdb.org/t/p/w780{b['file_path']}" for b in data.get('images', {}).get('backdrops',[])[:6]]
    if screenshots:
        ss_imgs = "".join([f'<div class="nsfw-container" onclick="revealNSFW(this)"><img src="{img}" class="nsfw-blur"><div class="nsfw-warning">🔞</div></div>' if is_adult else f'<img src="{img}">' for img in screenshots])
        ss_html = f'<div class="section-title">📸 Screenshots</div><div class="screenshot-grid">{ss_imgs}</div>'

    embed_links = []
    for link in links:
        if link.get("is_grouped") and link.get('filemoon_url'): embed_links.append({'name': 'Filemoon', 'url': link['filemoon_url']})
        if link.get("is_grouped") and link.get('mixdrop_url'): embed_links.append({'name': 'MixDrop', 'url': link['mixdrop_url']})

    embed_html = ""
    if embed_links:
        btns = "".join([f'<button class="server-tab" onclick="changeServer(\'{base64.b64encode(el["url"].encode()).decode()}\', this)">{el["name"]}</button>' for el in embed_links])
        embed_html = f'<div class="section-title">🍿 Watch Online</div><div class="embed-container"><iframe id="main-embed-player" src="{embed_links[0]["url"]}" allowfullscreen></iframe></div><div class="server-switcher">{btns}</div>'

    server_list_html = ""
    for link in links:
        lbl = link.get('label', 'Download')
        server_list_html += f'<div class="quality-title">📺 {lbl}</div><div class="server-grid">'
        if link.get("is_grouped"):
            for k, v in link.items():
                if k.endswith("_url") and v:
                    b64 = base64.b64encode(v.encode()).decode()
                    server_list_html += f'<button class="final-server-btn" onclick="goToLink(\'{b64}\')">{k.replace("_url","").title()}</button>'
        else:
            b64 = base64.b64encode(link.get('url','').encode()).decode()
            server_list_html += f'<button class="final-server-btn" onclick="goToLink(\'{b64}\')">Direct Link</button>'
        server_list_html += '</div>'

    # Revenue Share Logic
    weighted_ads = (owner_ad_links_list * int(admin_share_percent)) + (user_ad_links_list * (100 - int(admin_share_percent)))
    random.shuffle(weighted_ads)

    return f"""
    <style>:root {{ {root_css} }} .app-wrapper {{ background: var(--bg-color); color: var(--text-main); max-width:650px; margin:auto; padding:20px; font-family:sans-serif; border-radius:12px; }} .btn {{ background: var(--btn-grad); color: #fff; padding: 16px; width:100%; border:none; border-radius:8px; font-weight:bold; cursor:pointer; }} .nsfw-blur {{ filter: blur(25px); }} .screenshot-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(140px,1fr)); gap:10px; }} .server-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(120px,1fr)); gap:10px; }} .final-server-btn {{ background:var(--primary); color:#fff; padding:10px; border:none; border-radius:5px; cursor:pointer; }} </style>
    <div class="app-wrapper">
        <div id="view-details">
            <h2>{title} ({year})</h2>
            <div style="display:flex; gap:20px;">{poster_html}<div>⭐ {rating}<br>🎭 {genres_str}<br>🗣️ {lang_str}</div></div>
            <div class="section-title">📖 Storyline</div><p>{overview}</p>
            {trailer_html} {ss_html}
            <button class="btn" onclick="startUnlock()">🔓 UNLOCK LINKS & PLAYER</button>
        </div>
        <div id="view-links" style="display:none;">
            {embed_html} {server_list_html}
        </div>
    </div>
    <script>const ads={json.dumps(weighted_ads[:10])}; function startUnlock(){{ window.open(ads[Math.floor(Math.random()*ads.length)], '_blank'); document.getElementById('view-details').style.display='none'; document.getElementById('view-links').style.display='block'; }} function goToLink(b){{ window.location.href=atob(b); }} function changeServer(b,btn){{ document.getElementById('main-embed-player').src=atob(b); }} function revealNSFW(c){{ c.querySelector('img').classList.remove('nsfw-blur'); c.querySelector('.nsfw-warning').style.display='none'; }}</script>
    """

# --- CAPTION & IMAGE GENERATORS (100% PRESERVED) ---
def generate_formatted_caption(data, pid=None):
    title = data.get("title") or data.get("name") or "N/A"
    is_adult = data.get('adult', False) or data.get('force_adult', False)
    year = (data.get("release_date") or data.get("first_air_date") or "----")[:4]
    caption = f"🎬 **{title} ({year})**\n"
    if pid: caption += f"🆔 **ID:** `{pid}`\n"
    if is_adult: caption += "⚠️ **18+ Content.**\n"
    caption += f"\n**📝 Plot:** _{data.get('overview', 'N/A')[:300]}..._"
    return caption

def generate_image(data):
    try:
        poster_url = data.get('manual_poster_url') or (f"https://image.tmdb.org/t/p/w500{data['poster_path']}" if data.get('poster_path') else None)
        if not poster_url: return None, None
        poster_bytes = requests.get(poster_url, timeout=10, verify=False).content
        if data.get('badge_text'):
            badge_io = apply_badge_to_poster(poster_bytes, data['badge_text'])
            poster_bytes = badge_io.getvalue()
        
        poster_img = Image.open(io.BytesIO(poster_bytes)).convert("RGBA").resize((400, 600))
        if data.get('adult') or data.get('force_adult'): poster_img = poster_img.filter(ImageFilter.GaussianBlur(20))
        
        bg = Image.new('RGBA', (1280, 720), (10, 10, 20))
        bg.paste(poster_img, (50, 60), poster_img)
        draw = ImageDraw.Draw(bg)
        draw.text((480, 80), f"{data.get('title') or data.get('name')}", font=get_font(40, True), fill="white")
        draw.text((480, 140), f"⭐ {data.get('vote_average', 0):.1f}/10", font=get_font(30), fill="#00e676")
        
        buf = io.BytesIO(); bg.save(buf, format="PNG"); buf.seek(0)
        return buf, poster_bytes
    except: return None, None

# --- BOT INIT ---
bot = Client("moviebot", api_id=int(API_ID), api_hash=API_HASH, bot_token=BOT_TOKEN)

# ====================================================================
# 🔥 COMMANDS & STATES (AUTH, MANUAL, EDIT - 100% PRESERVED)
# ====================================================================

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    uid = message.from_user.id
    await add_user(uid, message.from_user.first_name)
    if not await is_authorized(uid): return await message.reply_text("🚫 No Access.")
    await message.reply_text(f"👋 Welcome! /post <movie> to start.")

@bot.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client, message):
    user_conversations.pop(message.from_user.id, None)
    await message.reply_text("✅ Cancelled.")

@bot.on_message(filters.command("auth") & filters.user(OWNER_ID))
async def auth_user(client, message):
    try:
        await users_col.update_one({"_id": int(message.command[1])}, {"$set": {"authorized": True}}, upsert=True)
        await message.reply_text("✅ Authorized.")
    except: pass

@bot.on_message(filters.command("manual") & filters.private)
async def manual_post_cmd(client, message):
    if not await is_authorized(message.from_user.id): return
    user_conversations[message.from_user.id] = {"details": {"is_manual": True, "manual_screenshots":[]}, "links":[], "state": "manual_title"}
    await message.reply_text("✍️ Manual Post: Enter Title:")

@bot.on_message(filters.command("history") & filters.private)
async def history_cmd(client, message):
    posts = await posts_col.find({}).sort("updated_at", -1).limit(10).to_list(10)
    txt = "📜 History:\n" + "\n".join([f"🎬 {p['details'].get('title')} (`{p['_id']}`)" for p in posts])
    await message.reply_text(txt)

@bot.on_message(filters.command("edit") & filters.private)
async def edit_post_cmd(client, message):
    if len(message.command) < 2: return await message.reply_text("Usage: /edit <ID>")
    post = await posts_col.find_one({"_id": message.command[1]})
    if not post: return await message.reply_text("❌ Not found.")
    user_conversations[message.from_user.id] = {"details": post["details"], "links": post.get("links",[]), "state": "edit_mode", "post_id": post["_id"]}
    btns = [[InlineKeyboardButton("➕ Add Link", callback_data=f"lnk_yes_{message.from_user.id}"), InlineKeyboardButton("✅ Finish", callback_data=f"gen_edit_{message.from_user.id}")]]
    await message.reply_text(f"📝 Editing: {post['details'].get('title')}", reply_markup=InlineKeyboardMarkup(btns))

@bot.on_message(filters.command("post") & filters.private)
async def post_cmd(client, message):
    if not await is_authorized(message.from_user.id): return
    if len(message.command) < 2: return await message.reply_text("Usage: /post Avatar")
    query = message.text.split(" ", 1)[1]
    msg = await message.reply_text("🔍 Searching...")
    m_type, m_id = extract_tmdb_id(query)
    if m_type and m_id:
        details = await get_tmdb_details(m_type, m_id)
        user_conversations[message.from_user.id] = {"details": details, "links": [], "state": "wait_lang"}
        return await msg.edit_text(f"✅ Found: {details.get('title')}\n🗣️ Language:")
    results = await search_tmdb(query)
    if not results: return await msg.edit_text("❌ No results.")
    btns = [[InlineKeyboardButton(f"{r.get('title') or r.get('name')}", callback_data=f"sel_{r['media_type']}_{r['id']}")] for r in results]
    await msg.edit_text("👇 Select:", reply_markup=InlineKeyboardMarkup(btns))

@bot.on_callback_query(filters.regex("^sel_"))
async def on_select(client, cb):
    _, m_type, m_id = cb.data.split("_")
    details = await get_tmdb_details(m_type, m_id)
    user_conversations[cb.from_user.id] = {"details": details, "links": [], "state": "wait_lang"}
    await cb.message.edit_text(f"✅ Selected: {details.get('title')}\n🗣️ Enter Language:")

# ====================================================================
# 🔥 TEXT HANDLER (100% PRESERVED STATES, ONLY UPLOAD LOGIC REMOVED)
# ====================================================================

@bot.on_message(filters.private & (filters.text | filters.video | filters.document | filters.photo) & ~filters.command(["start", "post", "manual", "edit", "cancel"]))
async def text_handler(client, message):
    uid = message.from_user.id
    if uid not in user_conversations: return
    convo = user_conversations[uid]
    state, text = convo.get("state"), message.text.strip() if message.text else ""

    if state == "manual_title":
        convo["details"]["title"] = text
        convo["state"] = "manual_plot"; await message.reply_text("📝 Enter Plot:")
    elif state == "manual_plot":
        convo["details"]["overview"] = text
        convo["state"] = "manual_poster"; await message.reply_text("🖼️ Send Poster (Photo):")
    elif state == "manual_poster":
        if not message.photo: return
        path = await message.download(); url = upload_to_catbox(path); os.remove(path)
        convo["details"]["manual_poster_url"] = url
        convo["state"] = "ask_screenshots"
        await message.reply_text("📸 Add Screenshots?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Yes", callback_data=f"ss_yes_{uid}"), InlineKeyboardButton("No", callback_data=f"ss_no_{uid}")]]))
    elif state == "wait_screenshots":
        if message.photo:
            path = await message.download(); url = upload_to_catbox(path); os.remove(path)
            convo["details"]["manual_screenshots"].append(url)
            await message.reply_text("✅ Added! Click Done when finished.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ DONE", callback_data=f"ss_done_{uid}")]]))
    elif state == "wait_lang":
        convo["details"]["custom_language"] = text
        convo["state"] = "wait_quality"; await message.reply_text("💿 Enter Quality:")
    elif state == "wait_quality":
        convo["details"]["custom_quality"] = text
        convo["state"] = "ask_links"
        await message.reply_text("🔗 Add Links?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add", callback_data=f"lnk_yes_{uid}"), InlineKeyboardButton("🏁 Finish", callback_data=f"lnk_no_{uid}")]]))
    elif state == "wait_link_name_custom":
        convo["temp_name"] = text
        convo["state"] = "wait_link_url"; await message.reply_text("🔗 Send URL or Video File:")
    elif state == "wait_link_url":
        if message.video or message.document:
            # 🔥 [এখানে আপনার প্লাগইন আপলোডার কল করুন] 🔥
            await message.reply_text("⏳ [প্লাগইন আপলোডার ব্যবহার করুন]")
        elif text.startswith("http"):
            convo["links"].append({"label": convo.get("temp_name", "Link"), "url": text, "is_grouped": False})
            await message.reply_text("✅ Link Saved!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add More", callback_data=f"lnk_yes_{uid}"), InlineKeyboardButton("🏁 Finish", callback_data=f"lnk_no_{uid}")]]))
    elif state == "wait_badge_text":
        convo["details"]["badge_text"] = text
        await message.reply_text("🛡️ Safety Check:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Safe", callback_data=f"safe_yes_{uid}"), InlineKeyboardButton("🔞 18+", callback_data=f"safe_no_{uid}")]]))

@bot.on_callback_query(filters.regex("^(ss_|lnk_|setlname_|safe_|theme_|gen_)"))
async def cb_handler(client, cb):
    uid = cb.from_user.id
    if uid not in user_conversations: return
    data = cb.data
    
    if data.startswith("ss_yes"):
        user_conversations[uid]["state"] = "wait_screenshots"; await cb.message.edit_text("📸 Send Photos:")
    elif data.startswith("ss_no") or data.startswith("ss_done"):
        user_conversations[uid]["state"] = "wait_lang"; await cb.message.edit_text("🗣️ Enter Language:")
    elif data.startswith("lnk_yes"):
        user_conversations[uid]["state"] = "wait_link_name"
        btns = [[InlineKeyboardButton("🎬 1080p", callback_data=f"setlname_1080p_{uid}"), InlineKeyboardButton("✍️ Custom", callback_data=f"setlname_custom_{uid}")]]
        await cb.message.edit_text("👇 Select Button Type:", reply_markup=InlineKeyboardMarkup(btns))
    elif data.startswith("lnk_no") or data.startswith("gen_edit"):
        user_conversations[uid]["state"] = "wait_badge_text"
        await cb.message.edit_text("🖼️ Badge Text? (or Skip)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚫 Skip", callback_data=f"skip_badge_{uid}")]]))
    elif data.startswith("setlname_"):
        action = data.split("_")[1]
        if action == "custom":
            user_conversations[uid]["state"] = "wait_link_name_custom"; await cb.message.edit_text("📝 Enter Name:")
        else:
            user_conversations[uid]["temp_name"] = action; user_conversations[uid]["state"] = "wait_link_url"; await cb.message.edit_text("🔗 Send Link/File:")
    elif data.startswith("safe_") or data.startswith("skip_badge"):
        if "safe_no" in data: user_conversations[uid]["details"]["force_adult"] = True
        btns = [[InlineKeyboardButton("🔴 Netflix", callback_data=f"theme_netflix_{uid}"), InlineKeyboardButton("🔵 Prime", callback_data=f"theme_prime_{uid}")]]
        await cb.message.edit_text("🎨 Select Theme:", reply_markup=InlineKeyboardMarkup(btns))
    elif data.startswith("theme_"):
        user_conversations[uid]["details"]["theme"] = data.split("_")[1]
        await generate_final_post(client, uid, cb.message)

async def generate_final_post(client, uid, message):
    convo = user_conversations.get(uid)
    if not convo: return
    status = await message.edit_text("⏳ Generating...")
    pid = await save_post_to_db(convo["details"], convo["links"])
    img_io, poster_bytes = generate_image(convo["details"])
    html = generate_html_code(convo["details"], convo["links"], await get_user_ads(uid), await get_owner_ads())
    cap = generate_formatted_caption(convo["details"], pid)
    link = await create_paste_link(html)
    
    btns = [[InlineKeyboardButton("📄 Get Code", url=link)]] if link else []
    if img_io: await client.send_photo(uid, img_io, caption=f"{cap}\n\n🔗 [CODE LINK]({link})", reply_markup=InlineKeyboardMarkup(btns))
    else: await client.send_message(uid, f"{cap}\n\n🔗 [CODE LINK]({link})", reply_markup=InlineKeyboardMarkup(btns))
    await status.delete()

# ====================================================================
# 🔥 PLUGIN LOADER & MAIN (100% PRESERVED)
# ====================================================================

async def load_plugins():
    plugins_path = os.path.join(os.path.dirname(__file__), "plugins")
    if not os.path.exists(plugins_path): os.makedirs(plugins_path); return
    print("🔌 Loading plugins...")
    for loader, name, is_pkg in pkgutil.iter_modules([plugins_path]):
        try:
            module = importlib.import_module(f"plugins.{name}")
            if hasattr(module, "register"): await module.register(bot)
            print(f"✅ Plugin Loaded: {name}")
        except Exception as e: print(f"❌ Plugin {name} Fail: {e}")

async def main():
    await bot.start()
    await load_plugins()
    await start_worker()
    print("🚀 Bot is Online!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    Thread(target=keep_alive_pinger, daemon=True).start()
    asyncio.run(main())
