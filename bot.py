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
MONGO_URL = os.getenv("MONGO_URL") 
OWNER_ID = int(os.getenv("OWNER_ID", 0)) 
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "admin") 
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 0))
DB_CHANNEL_ID = int(os.getenv("DB_CHANNEL_ID", 0)) 

# --- GLOBAL VARIABLES ---
worker_client = None
user_conversations = {}
upload_semaphore = asyncio.Semaphore(2)
processing_ids = set() # ডাবল আপলোড প্রতিরোধের জন্য আইডি ট্র্যাকার

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

# ---- DATABASE FUNCTIONS ----
async def add_user(user_id, name):
    if not await users_col.find_one({"_id": user_id}):
        await users_col.insert_one({
            "_id": user_id, "name": name,
            "authorized": False, "banned": False,
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

async def get_all_users_count(): return await users_col.count_documents({})

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

def generate_short_id(): return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

async def save_post_to_db(post_data, links):
    pid = post_data.get("post_id") or generate_short_id()
    post_data["post_id"] = pid
    save_data = {"_id": pid, "details": post_data, "links": links, "updated_at": datetime.datetime.now()}
    await posts_col.replace_one({"_id": pid}, save_data, upsert=True)
    return pid

# ====================================================================
# 🔥 AUTO MIRROR UPLOAD FUNCTIONS (8 SERVERS)
# ====================================================================

async def upload_to_gofile(file_path):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.gofile.io/servers") as resp:
                data = await resp.json()
                server = data['data']['servers'][0]['name']
            url = f"https://{server}.gofile.io/contents/uploadfile"
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData(); form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form) as upload_resp:
                    result = await upload_resp.json()
                    if result['status'] == 'ok': return result['data']['downloadPage']
    except: return None

async def upload_to_fileditch(file_path):
    try:
        url = "https://up1.fileditch.com/upload.php"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData(); form.add_field('files[]', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form) as resp:
                    result = await resp.json(); return result['files'][0]['url']
    except: return None

async def upload_to_tmpfiles(file_path):
    try:
        url = "https://tmpfiles.org/api/v1/upload"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData(); form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form) as resp:
                    result = await resp.json()
                    if result.get('status') == 'success': return result['data']['url'].replace("api/v1/download/", "")
    except: return None

async def upload_to_pixeldrain(file_path):
    try:
        url = "https://pixeldrain.com/api/file"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData(); form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form) as resp:
                    result = await resp.json()
                    if result.get('success'): return f"https://pixeldrain.com/u/{result['id']}"
    except: return None

async def upload_to_doodstream(file_path):
    api_key = await get_server_api("doodstream")
    if not api_key: return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://doodapi.com/api/upload/server?key={api_key}") as resp:
                data = await resp.json()
                if data.get('msg') != 'OK': return None
                upload_url = data['result']
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData(); form.add_field('file', f, filename=os.path.basename(file_path)); form.add_field('api_key', api_key)
                async with session.post(upload_url, data=form) as upload_resp:
                    result = await upload_resp.json()
                    if result.get('msg') == 'OK': return result['result'][0]['protected_embed']
    except: return None

async def upload_to_streamtape(file_path):
    api_credentials = await get_server_api("streamtape")
    if not api_credentials: return None 
    try:
        login_id, api_key = api_credentials.split(":")
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.streamtape.com/file/ul?login={login_id}&key={api_key}") as resp:
                data = await resp.json(); upload_url = data['result']['url']
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData(); form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(upload_url, data=form) as upload_resp:
                    result = await upload_resp.json()
                    if result.get('status') == 200: return result['result']['url']
    except: return None

async def upload_to_filemoon(file_path):
    api_key = await get_server_api("filemoon")
    if not api_key: return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://filemoonapi.com/api/upload/server?key={api_key}") as resp:
                data = await resp.json(); upload_url = data['result']
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData(); form.add_field('file', f, filename=os.path.basename(file_path)); form.add_field('api_key', api_key)
                async with session.post(upload_url, data=form) as upload_resp:
                    result = await upload_resp.json()
                    if result.get('msg') == 'OK': return f"https://filemoon.sx/e/{result['result'][0]['filecode']}"
    except: return None

async def upload_to_mixdrop(file_path):
    api_credentials = await get_server_api("mixdrop")
    if not api_credentials or ":" not in api_credentials: return None 
    try:
        email, api_key = api_credentials.split(":")
        url = "https://api.mixdrop.co/upload"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData(); form.add_field('file', f, filename=os.path.basename(file_path)); form.add_field('email', email); form.add_field('key', api_key)
                async with session.post(url, data=form) as resp:
                    result = await resp.json()
                    if result.get('success'): return result['result']['embedurl']
    except: return None

    # ====================================================================
# 🔥 RESOURCE & IMAGE HELPERS
# ====================================================================

URL_FONT = "https://raw.githubusercontent.com/mahabub81/bangla-fonts/master/Kalpurush.ttf"
URL_MODEL = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"

def setup_resources():
    if not os.path.exists("kalpurush.ttf"):
        try:
            r = requests.get(URL_FONT)
            with open("kalpurush.ttf", "wb") as f: f.write(r.content)
        except: pass
    if not os.path.exists("haarcascade_frontalface_default.xml"):
        try:
            r = requests.get(URL_MODEL)
            with open("haarcascade_frontalface_default.xml", "wb") as f: f.write(r.content)
        except: pass

setup_resources()

def get_font(size=60, bold=False):
    try: return ImageFont.truetype("kalpurush.ttf", size)
    except: return ImageFont.load_default()

def upload_image_core(file_content):
    # Try Catbox
    try:
        url = "https://catbox.moe/user/api.php"
        data = {"reqtype": "fileupload", "userhash": ""}
        files = {"fileToUpload": ("image.png", file_content, "image/png")}
        response = requests.post(url, data=data, files=files, timeout=10, verify=False)
        if response.status_code == 200: return response.text.strip()
    except: pass
    # Try Graph.org
    try:
        url = "https://graph.org/upload"
        files = {'file': ('image.jpg', file_content, 'image/jpeg')}
        response = requests.post(url, files=files, timeout=8, verify=False)
        if response.status_code == 200: return "https://graph.org" + response.json()[0]["src"]
    except: pass
    return None

def upload_to_catbox_bytes(img_bytes): return upload_image_core(img_bytes)

def upload_to_catbox(file_path):
    try:
        with open(file_path, "rb") as f: return upload_image_core(f.read())
    except: return None

# ====================================================================
# 🔥 OpenCV SMART BADGE POSITIONING
# ====================================================================

def get_smart_badge_position(pil_img):
    try:
        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        if len(faces) > 0:
            lowest_y = 0
            for (x, y, w, h) in faces:
                if (y + h) > lowest_y: lowest_y = y + h
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
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        padding_x, padding_y = 40, 20
        box_w, box_h = text_w + (padding_x * 2), text_h + (padding_y * 2)
        pos_x = (width - box_w) // 2
        overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)
        draw_ov.rectangle([pos_x, pos_y, pos_x + box_w, pos_y + box_h], fill=(0, 0, 0, 150))
        base_img = Image.alpha_composite(base_img, overlay)
        draw = ImageDraw.Draw(base_img); cx, cy = pos_x + padding_x, pos_y + padding_y - 12
        words = text.split()
        if len(words) >= 2:
            draw.text((cx, cy), words[0], font=font, fill="#FFEB3B")
            w1 = draw.textlength(words[0], font=font)
            draw.text((cx + w1 + 15, cy), " ".join(words[1:]), font=font, fill="#FF5722")
        else: draw.text((cx, cy), text, font=font, fill="#FFEB3B")
        img_buffer = io.BytesIO(); base_img.save(img_buffer, format="PNG"); img_buffer.seek(0)
        return img_buffer
    except: return io.BytesIO(poster_bytes)

# ====================================================================
# 🔥 ADVANCED HTML GENERATOR (SPA V42)
# ====================================================================

def generate_html_code(data, links, user_ads, owner_ads, share_percent=20):
    title = data.get("title") or data.get("name")
    overview = data.get("overview", "No plot available.")
    poster = data.get('manual_poster_url') or f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}"
    is_adult = data.get('adult', False) or data.get('force_adult', False)
    theme = data.get("theme", "netflix")

    # Theme Switching Logic
    if theme == "netflix":
        root_css = "--bg-color: #0f0f13; --box-bg: #1a1a24; --text-main: #ffffff; --text-muted: #d1d1d1; --primary: #E50914; --accent: #00d2ff; --border: #2a2a35; --btn-grad: linear-gradient(90deg, #E50914 0%, #ff5252 100%); --btn-shadow: 0 4px 15px rgba(229, 9, 20, 0.4);"
    elif theme == "prime":
        root_css = "--bg-color: #0f171e; --box-bg: #1b2530; --text-main: #ffffff; --text-muted: #8197a4; --primary: #00A8E1; --accent: #00A8E1; --border: #2c3e50; --btn-grad: linear-gradient(90deg, #00A8E1 0%, #00d2ff 100%); --btn-shadow: 0 4px 15px rgba(0, 168, 225, 0.4);"
    else: # Light Theme
        root_css = "--bg-color: #f4f4f9; --box-bg: #ffffff; --text-main: #333333; --text-muted: #555555; --primary: #6200ea; --accent: #6200ea; --border: #dddddd; --btn-grad: linear-gradient(90deg, #6200ea 0%, #b388ff 100%); --btn-shadow: 0 4px 15px rgba(98, 0, 234, 0.4);"

    # Poster & NSFW Logic
    if is_adult:
        poster_html = f'<div class="nsfw-container" onclick="revealNSFW(this)"><img src="{poster}" class="nsfw-blur"><div class="nsfw-warning">🔞 18+<br><small>Click to Reveal</small></div></div>'
    else:
        poster_html = f'<img src="{poster}" alt="Poster">'

    # Trailer & Screenshot Logic
    trailer_key = ""
    for v in data.get('videos', {}).get('results', []):
        if v.get('type') == 'Trailer' and v.get('site') == 'YouTube': trailer_key = v.get('key'); break
    trailer_html = f'<div class="section-title">🎬 Official Trailer</div><div class="video-container"><iframe src="https://www.youtube.com/embed/{trailer_key}" allowfullscreen></iframe></div>' if trailer_key else ""

    ss_html = ""
    screenshots = data.get('manual_screenshots') or [f"https://image.tmdb.org/t/p/w780{b['file_path']}" for b in data.get('images', {}).get('backdrops', [])[:6]]
    if screenshots:
        ss_imgs = "".join([f'<div class="nsfw-container" onclick="revealNSFW(this)"><img src="{img}" class="{"nsfw-blur" if is_adult else ""}"><div class="nsfw-warning" style="{"display:block" if is_adult else "display:none"}"><small>🔞 Tap to View</small></div></div>' for img in screenshots])
        ss_html = f'<div class="section-title">📸 Screenshots</div><div class="screenshot-grid">{ss_imgs}</div>'

    # Revenue Share Logic (Weighted Random)
    weighted_ads = []
    u_list = user_ads if user_ads else ["https://google.com"]
    o_list = owner_ads if owner_ads else ["https://google.com"]
    for _ in range(share_percent): weighted_ads.append(random.choice(o_list))
    for _ in range(100 - share_percent): weighted_ads.append(random.choice(u_list))
    random.shuffle(weighted_ads)

    # Server Grid Logic
    server_list_html = ""
    grouped_links = {}
    for l in links:
        lbl = l.get('label', 'Download')
        if lbl not in grouped_links: grouped_links[lbl] = []
        grouped_links[lbl].append(l)

    for lbl, grp in grouped_links.items():
        server_list_html += f'<div class="quality-title">📺 {lbl}</div><div class="server-grid">'
        for l in grp:
            if l.get("is_grouped"):
                for k, n, c in [('filemoon_url','Filemoon','#673AB7'),('mixdrop_url','MixDrop','#FFC107'),('dood_url','Dood','#F57C00'),('stape_url','Stape','#E91E63'),('gofile_url','GoFile','#2196F3'),('tg_url','Telegram','#0088cc'),('fileditch_url','Cloud','#009688'),('tmpfiles_url','Fast','#6A1B9A'),('pixel_url','Pixel','#2E7D32')]:
                    if l.get(k):
                        u_b64 = base64.b64encode(l[k].encode()).decode()
                        t_color = "#000" if k == 'mixdrop_url' else "#fff"
                        server_list_html += f'<button class="final-server-btn" onclick="goToLink(\'{u_b64}\')" style="background:{c}; color:{t_color};">{n}</button>'
            else:
                u_b64 = base64.b64encode(l.get('url','').encode()).decode()
                server_list_html += f'<button class="final-server-btn" onclick="goToLink(\'{u_b64}\')" style="background:#0088cc; color:#fff;">Download Link</button>'
        server_list_html += '</div>'

    # LIVE PLAYER LOGIC
    embed_links = []
    for l in links:
        if l.get("is_grouped"):
            if l.get('filemoon_url'): embed_links.append({'name': 'Filemoon HD', 'url': l['filemoon_url']})
            if l.get('mixdrop_url'): 
                m_u = l['mixdrop_url']
                if m_u.startswith("//"): m_u = "https:" + m_u
                embed_links.append({'name': 'MixDrop HD', 'url': m_u})

    embed_html = ""
    if embed_links:
        server_tabs = "".join([f'<button class="server-tab { "active" if i==0 else "" }" onclick="changeServer(\'{base64.b64encode(el["url"].encode()).decode()}\', this)">📺 {el["name"]}</button>' for i, el in enumerate(embed_links)])
        embed_html = f'<div class="section-title">🍿 Watch Online (Live Player)</div><div class="embed-container"><iframe id="main-embed-player" src="{embed_links[0]["url"]}" allowfullscreen></iframe></div><div class="server-switcher">{server_tabs}</div><hr style="border-top:1px dashed var(--border); margin:20px 0;">'

    # Full HTML Wrapper
    return f"""
    <!-- SPA V42 ENGINE -->
    <style>
        :root {{ {root_css} }}
        .app-wrapper {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: var(--bg-color); border: 1px solid var(--border); border-radius: 12px; max-width: 650px; margin: 20px auto; padding: 20px; color: var(--text-main); }}
        .movie-title {{ color: var(--accent); font-size: 24px; font-weight: bold; text-align: center; margin-bottom: 20px; }}
        .info-box {{ display: flex; background: var(--box-bg); border: 1px solid var(--border); border-radius: 12px; padding: 15px; gap: 20px; margin-bottom: 20px; align-items: center; }}
        @media (max-width: 480px) {{ .info-box {{ flex-direction: column; text-align: center; }} }}
        .info-poster img {{ width: 150px; border-radius: 8px; border: 2px solid var(--border); }}
        .info-text {{ flex: 1; font-size: 14px; color: var(--text-muted); line-height: 1.7; }}
        .info-text span {{ color: var(--primary); font-weight: bold; }}
        .section-title {{ font-size: 18px; color: var(--text-main); margin: 20px 0 10px; border-bottom: 2px solid var(--primary); display: inline-block; font-weight: bold; }}
        .plot-box {{ background: rgba(0,0,0,0.05); padding: 15px; border-left: 4px solid var(--primary); border-radius: 4px; font-size: 14px; color: var(--text-muted); margin-bottom: 20px; line-height: 1.6; border: 1px solid var(--border); }}
        .video-container, .embed-container {{ position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; border-radius: 10px; border: 1px solid var(--border); margin-bottom: 15px; }}
        .video-container iframe, .embed-container iframe {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: none; }}
        .screenshot-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 25px; }}
        .screenshot-grid img {{ width: 100%; border-radius: 8px; border: 1px solid var(--border); transition: 0.3s; }}
        .main-btn {{ width: 100%; padding: 16px; font-size: 16px; font-weight: bold; color: #fff; border: none; border-radius: 8px; cursor: pointer; transition: 0.3s; margin-top: 10px; }}
        .btn-watch {{ background: var(--btn-grad); box-shadow: var(--btn-shadow); }}
        .btn-download {{ background: linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%); color: #000; }}
        #view-links {{ display: none; background: var(--box-bg); padding: 20px; border-radius: 10px; border: 1px solid var(--border); animation: fadeIn 0.5s; }}
        @keyframes fadeIn {{ from {{ opacity:0; transform:translateY(10px); }} to {{ opacity:1; transform:translateY(0); }} }}
        .quality-title {{ font-size: 16px; font-weight: bold; color: var(--accent); margin-top: 20px; background: rgba(0,0,0,0.1); padding: 8px; border-radius: 6px; border: 1px solid var(--border); }}
        .server-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-top: 10px; }}
        .final-server-btn {{ padding: 12px; font-size: 13px; font-weight: 600; border: none; border-radius: 6px; cursor: pointer; transition: 0.2s; }}
        .server-switcher {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 15px; justify-content: center; }}
        .server-tab {{ background: var(--bg-color); color: var(--text-main); border: 1px solid var(--border); padding: 8px 15px; border-radius: 6px; cursor: pointer; }}
        .server-tab.active {{ background: var(--primary); color: #fff; }}
        .nsfw-container {{ position: relative; cursor: pointer; overflow: hidden; border-radius: 8px; }}
        .nsfw-blur {{ filter: blur(25px); transform: scale(1.1); transition: 0.5s; width: 100%; display: block; }}
        .nsfw-warning {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.85); color: #ff5252; padding: 10px; border-radius: 8px; font-weight: bold; text-align: center; border: 2px solid #ff5252; z-index: 5; pointer-events: none; }}
    </style>

    <div class="app-wrapper">
        <div id="view-details">
            <div class="movie-title">{title}</div>
            <div class="info-box">
                <div class="info-poster">{poster_html}</div>
                <div class="info-text">
                    <div><span>⭐ Rating:</span> {data.get('vote_average', 0):.1f}/10</div>
                    <div><span>🎭 Genre:</span> {genres}</div>
                    <div><span>🗣️ Language:</span> {lang_str}</div>
                    <div><span>⏱️ Runtime:</span> {runtime} min</div>
                </div>
            </div>
            <div class="section-title">📖 Storyline</div>
            <div class="plot-box">{overview}</div>
            {trailer_html}
            {ss_html}
            <div class="section-title">📥 Links & Player</div>
            <button class="main-btn btn-watch" onclick="startUnlock(this)">▶️ WATCH ONLINE (LIVE PLAYER)</button>
            <button class="main-btn btn-download" onclick="startUnlock(this)">📥 DOWNLOAD FILES & LINKS</button>
        </div>
        <div id="view-links">
            <h3 style="color:#00e676; text-align:center;">✅ Unlocked Successfully!</h3>
            {embed_html}
            <div class="section-title">📥 Download Servers</div>
            {server_list_html}
        </div>
    </div>

    <script>
        const ADS = {json.dumps(weighted_ads)};
        function startUnlock(btn) {{
            window.open(ADS[Math.floor(Math.random()*ADS.length)], '_blank');
            btn.disabled = true;
            let time = 5;
            let timer = setInterval(() => {{
                btn.innerHTML = "⏳ Please Wait... " + time + "s";
                if(time-- <= 0) {{
                    clearInterval(timer);
                    document.getElementById('view-details').style.display = 'none';
                    document.getElementById('view-links').style.display = 'block';
                    window.scrollTo({{top:0, behavior:'smooth'}});
                }}
            }}, 1000);
        }}
        function goToLink(b64) {{ window.location.href = atob(b64); }}
        function changeServer(b64, btn) {{
            document.getElementById('main-embed-player').src = atob(b64);
            document.querySelectorAll('.server-tab').forEach(t => t.classList.remove('active'));
            btn.classList.add('active');
        }}
        function revealNSFW(el) {{
            el.querySelector('img').classList.remove('nsfw-blur');
            el.querySelector('.nsfw-warning').style.display = 'none';
            el.onclick = null;
        }}
    </script>
    """

# ====================================================================
# 🔥 IMAGE & CAPTION GENERATORS
# ====================================================================

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
        genres = ", ".join([g["name"] for g in data.get("genres",[])] or ["N/A"])
        language = data.get('custom_language', '').title()
    
    overview = data.get("overview", "No plot available.")
    caption = f"🎬 **{title} ({year})**\n"
    if pid: caption += f"🆔 **ID:** `{pid}` (Use to Edit)\n\n"
    
    if is_adult: caption += "⚠️ **WARNING: 18+ Content.**\n_Suitable for mature audiences only._\n\n"
    
    if not data.get('is_manual'):
        caption += f"**🎭 Genres:** {genres}\n**🗣️ Language:** {language}\n**⭐ Rating:** {rating}\n\n"
        
    caption += f"**📝 Plot:** _{overview[:300]}..._\n\n⚠️ _Disclaimer: Informational post only._"
    return caption

def generate_image(data):
    try:
        poster_url = data.get('manual_poster_url') or (f"https://image.tmdb.org/t/p/w500{data['poster_path']}" if data.get('poster_path') else None)
        if not poster_url: return None, None
            
        poster_bytes = requests.get(poster_url, timeout=10, verify=False).content
        is_adult = data.get('adult', False) or data.get('force_adult', False)
        
        # Badge Text Logic
        if data.get('badge_text'):
            badge_io = apply_badge_to_poster(poster_bytes, data['badge_text'])
            poster_bytes = badge_io.getvalue()

        poster_img = Image.open(io.BytesIO(poster_bytes)).convert("RGBA").resize((400, 600))
        if is_adult: poster_img = poster_img.filter(ImageFilter.GaussianBlur(25))

        # Background Canvas (1280x720)
        bg_img = Image.new('RGBA', (1280, 720), (10, 10, 20))
        backdrop = None
        if data.get('backdrop_path') and not data.get('is_manual'):
            try:
                bd_url = f"https://image.tmdb.org/t/p/w1280{data['backdrop_path']}"
                bd_bytes = requests.get(bd_url, timeout=10, verify=False).content
                backdrop = Image.open(io.BytesIO(bd_bytes)).convert("RGBA").resize((1280, 720))
            except: pass
        
        if not backdrop: backdrop = poster_img.resize((1280, 720))
        backdrop = backdrop.filter(ImageFilter.GaussianBlur(15))
        bg_img = Image.alpha_composite(backdrop, Image.new('RGBA', (1280, 720), (0, 0, 0, 180))) 
        bg_img.paste(poster_img, (60, 60), poster_img)
        
        draw = ImageDraw.Draw(bg_img)
        f_bold = get_font(size=45, bold=True); f_reg = get_font(size=25)

        title = (data.get("title") or data.get("name"))[:45]
        year = str(data.get("release_date") or data.get("first_air_date") or "")[:4]
        
        draw.text((490, 80), f"{title} ({year})", font=f_bold, fill="#00d2ff", stroke_width=2, stroke_fill="black")
        
        if not data.get('is_manual'):
            draw.text((490, 150), f"⭐ Rating: {data.get('vote_average', 0):.1f}/10", font=f_reg, fill="#00e676")
            genre_txt = " | ".join([g["name"] for g in data.get("genres",[])[:3]])
            draw.text((490, 195), f"🎭 Genres: {genre_txt}", font=f_reg, fill="#E0E0E0")
        
        # Wrapping Overview Text
        overview = data.get("overview", "")
        lines = [overview[i:i+65] for i in range(0, len(overview), 65)][:8]
        y_text = 270
        for line in lines:
            draw.text((490, y_text), line, font=f_reg, fill="#B0B0B0")
            y_text += 35
            
        img_buffer = io.BytesIO(); img_buffer.name = "poster.png"
        bg_img.save(img_buffer, format="PNG"); img_buffer.seek(0)
        return img_buffer, poster_bytes 
    except Exception as e:
        logger.error(f"Generate Image Error: {e}")
        return None, None

def generate_file_caption(details):
    title = details.get("title") or details.get("name") or "Unknown"
    year = (details.get("release_date") or details.get("first_air_date") or "----")[:4]
    rating = f"{details.get('vote_average', 0):.1f}/10"
    lang = details.get("custom_language") or "Dual Audio"
    genres = ", ".join([g['name'] for g in details.get('genres', [])][:3]) or "Movie"
    return f"🎬 **{title} ({year})**\n━━━━━━━━━━━━━━━━━━━━━━━\n⭐ Rating: {rating}\n🎭 Genre: {genres}\n🔊 Language: {lang}\n\n🤖 Join: @{(bot.me).username if bot.me else 'Bot'}"

# ====================================================================
# 🔥 TMDB & UTILITY LOGIC
# ====================================================================

def extract_tmdb_id(text):
    tmdb_match = re.search(r'themoviedb\.org/(movie|tv)/(\d+)', text)
    if tmdb_match: return tmdb_match.group(1), tmdb_match.group(2)
    imdb_url_match = re.search(r'imdb\.com/title/(tt\d+)', text)
    if imdb_url_match: return "imdb", imdb_url_match.group(1)
    imdb_id_match = re.search(r'(tt\d{6,})', text)
    if imdb_id_match: return "imdb", imdb_id_match.group(1)
    return None, None

async def search_tmdb(query):
    try:
        match = re.search(r'(.+?)\s*\(?(\d{4})\)?$', query)
        name = match.group(1).strip() if match else query.strip()
        year = match.group(2) if match else None
        url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={name}&include_adult=true"
        if year: url += f"&year={year}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                return [r for r in data.get("results", []) if r.get("media_type") in ["movie", "tv"]][:15]
    except: return []

async def get_tmdb_details(media_type, media_id):
    url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={TMDB_API_KEY}&append_to_response=credits,similar,images,videos&include_image_language=en,null"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp: return await resp.json()

async def create_paste_link(content):
    if not content: return None
    url = "https://dpaste.com/api/"
    data = {"content": content, "syntax": "html", "expiry_days": 14}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as resp:
            link = await resp.text()
            return link.strip() if "dpaste.com" in link else None

# ====================================================================
# 🔥 BOT CORE: START, CANCEL & ADMIN COMMANDS
# ====================================================================

bot = Client("moviebot", api_id=int(API_ID), api_hash=API_HASH, bot_token=BOT_TOKEN)

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    uid = message.from_user.id; await add_user(uid, message.from_user.first_name)
    if len(message.command) > 1 and message.command[1].startswith("get-"):
        if await is_banned(uid): return await message.reply_text("🚫 Banned.")
        try:
            msg_id = int(message.command[1].split("-")[1])
            temp_msg = await message.reply_text("🔍 Searching...")
            post = await posts_col.find_one({"links.tg_url": {"$regex": f"get-{msg_id}"}})
            cap = generate_file_caption(post["details"]) if post else "🎥 Your File!"
            f_msg = await client.copy_message(chat_id=uid, from_chat_id=DB_CHANNEL_ID, message_id=msg_id, caption=cap)
            await temp_msg.delete()
            timer = await get_auto_delete_timer()
            if timer > 0:
                warn = await message.reply_text(f"⚠️ ফাইলটি **{timer}সতর্কবার্তা** পর ডিলিট হবে।")
                asyncio.create_task(auto_delete_task(client, uid, [f_msg.id, warn.id], timer))
            return
        except: return await message.reply_text("❌ Not Found.")
    user_conversations.pop(uid, None)
    if not await is_authorized(uid): return await message.reply_text("🚫 No Access. Contact Admin.")
    await message.reply_text(f"👋 Welcome {message.from_user.first_name}!\n\nCommands:\n/post Movie\n/manual\n/edit <ID>\n/mysettings")

@bot.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client, message):
    user_conversations.pop(message.from_user.id, None)
    await message.reply_text("✅ All processes cancelled.")

@bot.on_message(filters.command(["auth", "ban", "setownerads", "setshare", "setdel", "broadcast", "setapi", "setworker", "workerinfo", "stats"]) & filters.user(OWNER_ID))
async def admin_handler(client, message):
    cmd = message.command[0]
    if cmd == "auth":
        tid = int(message.command[1]); await users_col.update_one({"_id": tid}, {"$set": {"authorized": True}}, upsert=True)
        await message.reply_text(f"✅ Authorized {tid}")
    elif cmd == "stats":
        u, p = await get_all_users_count(), await posts_col.count_documents({})
        await message.reply_text(f"📊 Stats: {u} Users | {p} Posts")
    elif cmd == "setapi":
        await set_server_api(message.command[1].lower(), message.command[2])
        await message.reply_text("✅ API Saved.")
    elif cmd == "broadcast":
        if not message.reply_to_message: return
        msg = await message.reply_text("⏳ Sending...")
        c = 0
        async for u in users_col.find({}):
            try: await message.reply_to_message.copy(u["_id"]); c += 1; await asyncio.sleep(0.05)
            except: pass
        await msg.edit_text(f"✅ Sent to {c} users.")

# ====================================================================
# 🔥 CORE UPLOAD ORCHESTRATOR (THE DOUBLE UPLOAD FIX)
# ====================================================================

async def down_progress(current, total, status_msg, start_time, last_update_time):
    now = time.time()
    if now - last_update_time[0] >= 3.0 or current == total:
        last_update_time[0] = now
        percent = (current / total) * 100 if total > 0 else 0
        speed = current / (now - start_time) if (now - start_time) > 0 else 1
        eta = (total - current) / speed if speed > 0 else 0
        def hb(s):
            for u in ['B','KB','MB','GB']:
                if s < 1024.0: return f"{s:.2f} {u}"
                s /= 1024.0
            return f"{s:.2f} TB"
        bar = "█" * int(percent/10) + "░" * (10 - int(percent/10))
        try: await status_msg.edit_text(f"⏳ **২/৩: ডাউনলোড হচ্ছে...**\n\n{bar} {percent:.1f}%\n💾 {hb(current)}/{hb(total)}\n🚀 {hb(speed)}/s")
        except: pass

async def process_file_upload(client, message, uid, temp_name):
    convo = user_conversations.get(uid); if not convo: return
    if message.id in processing_ids: return
    processing_ids.add(message.id)
    convo["pending_uploads"] = convo.get("pending_uploads", 0) + 1
    status = await message.reply_text(f"🕒 **Queued...** ({temp_name})", quote=True)
    upld = worker_client if (worker_client and worker_client.is_connected) else client
    try:
        async with upload_semaphore:
            await status.edit_text(f"⏳ **১/৩: সেভ হচ্ছে...** ({temp_name})")
            copy = await message.copy(DB_CHANNEL_ID)
            tg_url = f"https://t.me/{(await client.get_me()).username}?start=get-{copy.id}"
            start = time.time(); lut = [start]
            file = await upld.download_media(message, progress=down_progress, progress_args=(status, start, lut))
            await status.edit_text(f"⏳ **৩/৩: মিরর আপলোড হচ্ছে...**")
            res = await asyncio.gather(
                upload_to_gofile(file), upload_to_fileditch(file), upload_to_tmpfiles(file), upload_to_pixeldrain(file),
                upload_to_doodstream(file), upload_to_streamtape(file), upload_to_filemoon(file), upload_to_mixdrop(file),
                return_exceptions=True
            )
            if os.path.exists(file): os.remove(file)
            convo["links"].append({
                "label": temp_name, "tg_url": tg_url, "is_grouped": True,
                "gofile_url": res[0] if isinstance(res[0],str) else None,
                "fileditch_url": res[1] if isinstance(res[1],str) else None,
                "tmpfiles_url": res[2] if isinstance(res[2],str) else None,
                "pixel_url": res[3] if isinstance(res[3],str) else None,
                "dood_url": res[4] if isinstance(res[4],str) else None,
                "stape_url": res[5] if isinstance(res[5],str) else None,
                "filemoon_url": res[6] if isinstance(res[6],str) else None,
                "mixdrop_url": res[7] if isinstance(res[7],str) else None,
            })
            await status.edit_text(f"✅ **Done:** {temp_name}")
    except Exception as e: await status.edit_text(f"❌ Error: {e}")
    finally:
        convo["pending_uploads"] = max(0, convo.get("pending_uploads", 0) - 1)
        if message.id in processing_ids: processing_ids.remove(message.id)

# ====================================================================
# 🔥 STATE MACHINE: TEXT HANDLER & CALLBACKS
# ====================================================================

@bot.on_message(filters.command("post") & filters.private)
async def post_cmd(c, m):
    if not await is_authorized(m.from_user.id): return
    q = m.text.split(None, 1)[1]
    res = await search_tmdb(q)
    if not res: return await m.reply_text("❌ No results.")
    btns = [[InlineKeyboardButton(f"{r.get('title') or r.get('name')} ({str(r.get('release_date','----'))[:4]})", callback_data=f"sel_{r['media_type']}_{r['id']}")] for r in res]
    await m.reply_text("👇 Select Content:", reply_markup=InlineKeyboardMarkup(btns))

@bot.on_callback_query(filters.regex("^sel_|^ss_|^lnk_|^setlname_|^safe_|^theme_|^get_code_|^gen_edit_|^skip_badge_|^forcedit_"))
async def cb_handler(c, cb):
    uid = cb.from_user.id; data = cb.data
    if data.startswith("sel_"):
        _, mt, mi = data.split("_"); d = await get_tmdb_details(mt, mi)
        user_conversations[uid] = {"details": d, "links": [], "state": "wait_lang"}
        await cb.message.edit_text(f"✅ Found: {d.get('title') or d.get('name')}\n\nEnter **Language**:")
    elif data.startswith("lnk_yes"):
        user_conversations[uid]["state"] = "wait_link_name"
        btns = [[InlineKeyboardButton("1080p", callback_data=f"setlname_1080p_{uid}"), InlineKeyboardButton("720p", callback_data=f"setlname_720p_{uid}")], [InlineKeyboardButton("Batch", callback_data=f"setlname_batch_{uid}")]]
        await cb.message.edit_text("Select button:", reply_markup=InlineKeyboardMarkup(btns))
    elif data.startswith("setlname_"):
        _, act, _ = data.split("_"); user_conversations[uid]["temp_name"] = act
        if act == "batch":
            user_conversations[uid]["state"] = "wait_batch_files"; await cb.message.edit_text("Send files, then type /done")
        else:
            user_conversations[uid]["state"] = "wait_link_url"; await cb.message.edit_text(f"Send File/URL for {act}:")
    elif data.startswith("lnk_no") or data.startswith("gen_edit_"):
        if user_conversations[uid].get("pending_uploads", 0) > 0: return await cb.answer("⏳ Wait for uploads...", show_alert=True)
        user_conversations[uid]["state"] = "wait_badge_text"
        await cb.message.edit_text("Enter **Badge Text** or /skip:")
    elif data.startswith("theme_"):
        _, th, _ = data.split("_"); user_conversations[uid]["details"]["theme"] = th
        await generate_final_post(c, uid, cb.message)
    elif data.startswith("get_code_"):
        h = user_conversations[uid].get("final_html"); l = await create_paste_link(h)
        await cb.message.reply_text(f"✅ Code Link: {l}")

@bot.on_message(filters.private & (filters.text | filters.video | filters.document) & ~filters.command(["start","post","cancel","manual","edit"]))
async def text_handler(client, message):
    uid = message.from_user.id; if uid not in user_conversations: return
    convo = user_conversations[uid]; state = convo.get("state"); txt = message.text
    if state == "wait_lang":
        convo["details"]["custom_language"] = txt; convo["state"] = "wait_quality"; await message.reply_text("Enter Quality:")
    elif state == "wait_quality":
        convo["details"]["custom_quality"] = txt; convo["state"] = "ask_links"
        await message.reply_text("Add Links?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Add", callback_data=f"lnk_yes_{uid}"), InlineKeyboardButton("Finish", callback_data=f"lnk_no_{uid}")]]))
    elif state == "wait_link_url":
        if message.video or message.document:
            convo["state"] = "ask_links"; asyncio.create_task(process_file_upload(client, message, uid, convo["temp_name"]))
            await message.reply_text("⏳ Uploading. Add more?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Add", callback_data=f"lnk_yes_{uid}"), InlineKeyboardButton("Finish", callback_data=f"lnk_no_{uid}")]]))
        elif txt.startswith("http"):
            convo["links"].append({"label": convo["temp_name"], "url": txt, "is_grouped": False}); convo["state"] = "ask_links"
            await message.reply_text("✅ Saved.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Add", callback_data=f"lnk_yes_{uid}"), InlineKeyboardButton("Finish", callback_data=f"lnk_no_{uid}")]]))
    elif state == "wait_batch_files" and (message.video or message.document):
        asyncio.create_task(process_file_upload(client, message, uid, "Episode"))
    elif state == "wait_badge_text":
        convo["details"]["badge_text"] = txt; convo["state"] = "select_theme"
        btns = [[InlineKeyboardButton("Netflix", callback_data=f"theme_netflix_{uid}"), InlineKeyboardButton("Prime", callback_data=f"theme_prime_{uid}")]]
        await message.reply_text("Select Theme:", reply_markup=InlineKeyboardMarkup(btns))

async def generate_final_post(client, uid, message):
    convo = user_conversations[uid]; st = await message.edit_text("⏳ Generating...")
    try:
        pid = await save_post_to_db(convo["details"], convo["links"])
        img, _ = generate_image(convo["details"])
        html = generate_html_code(convo["details"], convo["links"], await get_user_ads(uid), await get_owner_ads())
        convo["final_html"] = html
        cap = generate_formatted_caption(convo["details"], pid)
        await client.send_photo(uid, img, caption=cap, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📄 Get Code", callback_data=f"get_code_{uid}")]]))
        await st.delete()
    except Exception as e: await st.edit_text(f"❌ Error: {e}")

# ====================================================================
# 🔥 APP STARTUP
# ====================================================================

async def main():
    await bot.start(); await start_worker()
    print("✅ Bot is Online!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    app = Flask(__name__)
    @app.route('/')
    def h(): return "V42 Bot Active"
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080), daemon=True).start()
    loop = asyncio.get_event_loop(); loop.run_until_complete(main())
