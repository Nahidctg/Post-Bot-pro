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

# --- GLOBAL VARIABLES ---
worker_client = None
user_conversations = {}
upload_semaphore = asyncio.Semaphore(2)
processing_ids = set() # ডাবল আপলোড ফিক্সের মেইন আইডি ট্র্যাকার

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

# ---- DETAILED DATABASE FUNCTIONS ----
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
    except: pass

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

async def get_worker_session():
    data = await settings_col.find_one({"_id": "worker_config"})
    return data.get("session_string") if data else None

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
    return # ====================================================================
# 🔥 RESOURCE & IMAGE CORE HELPERS (DETAILED)
# ====================================================================

URL_FONT = "https://raw.githubusercontent.com/mahabub81/bangla-fonts/master/Kalpurush.ttf"
URL_MODEL = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"

def setup_resources():
    font_name = "kalpurush.ttf"
    if not os.path.exists(font_name):
        logger.info("⏳ Downloading Kalpurush Font...")
        try:
            r = requests.get(URL_FONT, timeout=15)
            with open(font_name, "wb") as f:
                f.write(r.content)
            logger.info("✅ Font Downloaded Successfully!")
        except Exception as e:
            logger.error(f"❌ Font Download Error: {e}")

    model_name = "haarcascade_frontalface_default.xml"
    if not os.path.exists(model_name):
        logger.info("⏳ Downloading OpenCV HaarCascade Model...")
        try:
            r = requests.get(URL_MODEL, timeout=15)
            with open(model_name, "wb") as f:
                f.write(r.content)
            logger.info("✅ OpenCV Model Downloaded Successfully!")
        except Exception as e:
            logger.error(f"❌ Model Download Error: {e}")

# রিসোর্সগুলো রান করা
setup_resources()

def get_font(size=60, bold=False):
    """বটের জন্য ফন্ট রিটার্ন করে"""
    try:
        if os.path.exists("kalpurush.ttf"):
            return ImageFont.truetype("kalpurush.ttf", size)
        # ব্যাকআপ ফন্ট
        font_file = "Poppins-Bold.ttf" if bold else "Poppins-Regular.ttf"
        if os.path.exists(font_file):
            return ImageFont.truetype(font_file, size)
        return ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()

def upload_image_core(file_content):
    """ইমেজ আপলোড করার কোর ইঞ্জিন (Catbox + Graph.org)"""
    # ১. ক্যাটবক্স ট্রাই করা
    try:
        url = "https://catbox.moe/user/api.php"
        data = {"reqtype": "fileupload", "userhash": ""}
        files = {"fileToUpload": ("image.png", file_content, "image/png")}
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.post(url, data=data, files=files, headers=headers, timeout=10, verify=False)
        if response.status_code == 200:
            return response.text.strip()
    except Exception as e:
        logger.debug(f"Catbox Upload Failed: {e}")

    # ২. গ্রাফ ট্রাই করা (ব্যাকআপ)
    try:
        url = "https://graph.org/upload"
        files = {'file': ('image.jpg', file_content, 'image/jpeg')}
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.post(url, files=files, headers=headers, timeout=8, verify=False)
        if response.status_code == 200:
            json_data = response.json()
            return "https://graph.org" + json_data[0]["src"]
    except Exception as e:
        logger.debug(f"Graph.org Upload Failed: {e}")

    return None

def upload_to_catbox_bytes(img_bytes):
    """বাইট ডাটা থেকে সরাসরি আপলোড"""
    try:
        if hasattr(img_bytes, 'read'):
            img_bytes.seek(0)
            data = img_bytes.read()
        else:
            data = img_bytes
        return upload_image_core(data)
    except:
        return None

def upload_to_catbox(file_path):
    """ফাইল পাথ থেকে আপলোড"""
    try:
        if not os.path.exists(file_path):
            return None
        with open(file_path, "rb") as f:
            data = f.read()
        return upload_image_core(data)
    except:
        return None

# ====================================================================
# 🔥 OpenCV SMART BADGE & IMAGE POSITIONING LOGIC
# ====================================================================

def get_smart_badge_position(pil_img):
    """OpenCV ব্যবহার করে মানুষের মুখ ডিটেক্ট করে ব্যাজ পজিশন ঠিক করা"""
    try:
        # PIL থেকে OpenCV ফরম্যাটে কনভার্ট
        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        cascade_path = "haarcascade_frontalface_default.xml"
        
        if not os.path.exists(cascade_path):
            return int(pil_img.height * 0.40) # ডিফল্ট পজিশন ৪০% নিচে

        face_cascade = cv2.CascadeClassifier(cascade_path)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) > 0:
            lowest_y = 0
            for (x, y, w, h) in faces:
                bottom_of_face = y + h
                if bottom_of_face > lowest_y:
                    lowest_y = bottom_of_face
            
            # মুখের ৪০ পিক্সেল নিচে ব্যাজ বসানো
            target_y = lowest_y + 40 
            if target_y > (pil_img.height - 130):
                return 80 # যদি খুব নিচে চলে যায় তবে উপরে ৮২ পিক্সেল নিচে বসানো
            return target_y
        else:
            # মুখ পাওয়া না গেলে ৪০% হাইটে বসানো
            return int(pil_img.height * 0.40) 
    except Exception as e:
        logger.error(f"OpenCV Detection Error: {e}")
        return 200

def apply_badge_to_poster(poster_bytes, text):
    """পোস্টারের ওপর সুন্দর ব্যাজ ড্র করা"""
    try:
        base_img = Image.open(io.BytesIO(poster_bytes)).convert("RGBA")
        width, height = base_img.size
        font = get_font(size=70) 
        
        # স্মার্ট পজিশন নেওয়া
        pos_y = get_smart_badge_position(base_img)
        
        draw = ImageDraw.Draw(base_img)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        padding_x, padding_y = 40, 20
        box_w = text_w + (padding_x * 2)
        box_h = text_h + (padding_y * 2)
        pos_x = (width - box_w) // 2
        
        # সেমি-ট্রান্সপারেন্ট ব্ল্যাক বক্স
        overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        draw_overlay.rectangle([pos_x, pos_y, pos_x + box_w, pos_y + box_h], fill=(0, 0, 0, 150))
        base_img = Image.alpha_composite(base_img, overlay)
        
        draw = ImageDraw.Draw(base_img)
        cx = pos_x + padding_x
        cy = pos_y + padding_y - 12
        
        # ডুয়াল কালার টেক্সট লজিক
        words = text.split()
        if len(words) >= 2:
            draw.text((cx, cy), words[0], font=font, fill="#FFEB3B")
            w1 = draw.textlength(words[0], font=font)
            draw.text((cx + w1 + 15, cy), " ".join(words[1:]), font=font, fill="#FF5722")
        else:
            draw.text((cx, cy), text, font=font, fill="#FFEB3B")

        img_buffer = io.BytesIO()
        base_img.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        return img_buffer
    except Exception as e:
        logger.error(f"Badge Apply Error: {e}")
        return io.BytesIO(poster_bytes)

# ====================================================================
# 🔥 ADVANCED MIRROR UPLOAD FUNCTIONS (8 SERVERS DETAILED)
# ====================================================================

async def upload_to_gofile(file_path):
    """গোপন নয়, হাই-স্পিড গোপাইল আপলোডার"""
    try:
        async with aiohttp.ClientSession() as session:
            # সার্ভার লিস্ট আনা
            async with session.get("https://api.gofile.io/servers", timeout=10) as resp:
                data = await resp.json()
                if data['status'] != 'ok': return None
                server = data['data']['servers'][0]['name']
            
            # ফাইল আপলোড
            url = f"https://{server}.gofile.io/contents/uploadfile"
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form, timeout=600) as upload_resp:
                    result = await upload_resp.json()
                    if result['status'] == 'ok':
                        return result['data']['downloadPage']
    except Exception as e:
        logger.error(f"GoFile Error: {e}")
    return None

async def upload_to_fileditch(file_path):
    """ফাইলডিচ ডাইরেক্ট লিঙ্ক আপলোডার"""
    try:
        url = "https://up1.fileditch.com/upload.php"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('files[]', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form, timeout=600) as resp:
                    result = await resp.json()
                    return result['files'][0]['url']
    except Exception as e:
        logger.error(f"FileDitch Error: {e}")
    return None

async def upload_to_tmpfiles(file_path):
    """টিএমপি ফাইল আপলোডার (ডাইরেক্ট ডাউনলোড লিঙ্ক)"""
    try:
        url = "https://tmpfiles.org/api/v1/upload"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form, timeout=600) as resp:
                    result = await resp.json()
                    if result.get('status') == 'success':
                        # লিঙ্ক কনভার্ট (Download format)
                        return result['data']['url'].replace("tmpfiles.org/", "tmpfiles.org/dl/")
    except Exception as e:
        logger.error(f"TmpFiles Error: {e}")
    return None

async def upload_to_pixeldrain(file_path):
    """পিক্সেলড্রেন ফাস্ট আপলোডার"""
    try:
        url = "https://pixeldrain.com/api/file"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form, timeout=600) as resp:
                    result = await resp.json()
                    if result.get('success'):
                        return f"https://pixeldrain.com/u/{result['id']}"
    except Exception as e:
        logger.error(f"PixelDrain Error: {e}")
    return None

async def upload_to_doodstream(file_path):
    """ডুডস্ট্রিম এপিআই আপলোডার (Watch Online)"""
    api_key = await get_server_api("doodstream")
    if not api_key: return None
    try:
        async with aiohttp.ClientSession() as session:
            # ১. আপলোড সার্ভার আনা
            async with session.get(f"https://doodapi.com/api/upload/server?key={api_key}") as resp:
                data = await resp.json()
                if data.get('msg') != 'OK': return None
                upload_url = data['result']
            
            # ২. ফাইল পাঠানো
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                form.add_field('api_key', api_key)
                async with session.post(upload_url, data=form, timeout=600) as upload_resp:
                    result = await upload_resp.json()
                    if result.get('msg') == 'OK':
                        return result['result'][0]['protected_embed']
    except Exception as e:
        logger.error(f"DoodStream Error: {e}")
    return None

async def upload_to_streamtape(file_path):
    """স্ট্রিমটেপ এপিআই আপলোডার"""
    api_credentials = await get_server_api("streamtape")
    if not api_credentials: return None 
    try:
        login_id, api_key = api_credentials.split(":")
        async with aiohttp.ClientSession() as session:
            # ১. লিঙ্ক আনা
            async with session.get(f"https://api.streamtape.com/file/ul?login={login_id}&key={api_key}") as resp:
                data = await resp.json()
                upload_url = data['result']['url']
            
            # ২. আপলোড
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(upload_url, data=form, timeout=600) as upload_resp:
                    result = await upload_resp.json()
                    if result.get('status') == 200:
                        return result['result']['url']
    except Exception as e:
        logger.error(f"Streamtape Error: {e}")
    return None

async def upload_to_filemoon(file_path):
    """ফাইলমুন এপিআই আপলোডার (High Quality Online Player)"""
    api_key = await get_server_api("filemoon")
    if not api_key: return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://filemoonapi.com/api/upload/server?key={api_key}") as resp:
                data = await resp.json()
                if data.get('msg') != 'OK': return None
                upload_url = data['result']
            
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                form.add_field('api_key', api_key)
                async with session.post(upload_url, data=form, timeout=600) as upload_resp:
                    result = await upload_resp.json()
                    if result.get('msg') == 'OK':
                        return f"https://filemoon.sx/e/{result['result'][0]['filecode']}"
    except Exception as e:
        logger.error(f"Filemoon Error: {e}")
    return None

async def upload_to_mixdrop(file_path):
    """মিক্সড্রপ এপিআই আপলোডার"""
    api_credentials = await get_server_api("mixdrop")
    if not api_credentials or ":" not in api_credentials: return None 
    try:
        email, api_key = api_credentials.split(":")
        url = "https://api.mixdrop.co/upload"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                form.add_field('email', email)
                form.add_field('key', api_key)
                async with session.post(url, data=form, timeout=600) as resp:
                    result = await resp.json()
                    if result.get('success'):
                        return result['result']['embedurl']
    except Exception as e:
        logger.error(f"MixDrop Error: {e}")
    return # ============================================================================
# 🔥 ADVANCED SPA HTML GENERATOR (V42 PRO - 3 THEMES & JS UNLOCK SYSTEM)
# ============================================================================

def generate_html_code(data, links, user_ad_links_list, owner_ad_links_list, admin_share_percent=20):
    """
    এই ফাংশনটি একটি পূর্ণাঙ্গ সিঙ্গেল পেজ অ্যাপ্লিকেশন (SPA) কোড জেনারেট করে।
    এটি জাভাস্ক্রিপ্ট ব্যবহার করে মুভি ডিটেইলস থেকে ডাউনলোড লিঙ্কে সুইচ করে।
    """
    # ১. ডাটা প্রিপারেশন
    title = data.get("title") or data.get("name")
    overview = data.get("overview", "No plot available.")
    poster = data.get('manual_poster_url') or f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}"
    BTN_TELEGRAM = "https://i.ibb.co/kVfJvhzS/photo-2025-12-23-12-38-56-7587031987190235140.jpg"

    # 🔞 NSFW লজিক
    is_adult = data.get('adult', False) or data.get('force_adult', False)

    # 🎨 থিম সিলেকশন (Netflix, Prime, Light)
    theme = data.get("theme", "netflix")
    if theme == "netflix":
        root_css = """
        --bg-color: #0f0f13; --box-bg: #1a1a24; --text-main: #ffffff; --text-muted: #d1d1d1;
        --primary: #E50914; --accent: #00d2ff; --border: #2a2a35;
        --btn-grad: linear-gradient(90deg, #E50914 0%, #ff5252 100%);
        --btn-shadow: 0 4px 15px rgba(229, 9, 20, 0.4);
        """
    elif theme == "prime":
        root_css = """
        --bg-color: #0f171e; --box-bg: #1b2530; --text-main: #ffffff; --text-muted: #8197a4;
        --primary: #00A8E1; --accent: #00A8E1; --border: #2c3e50;
        --btn-grad: linear-gradient(90deg, #00A8E1 0%, #00d2ff 100%);
        --btn-shadow: 0 4px 15px rgba(0, 168, 225, 0.4);
        """
    else: # Light Theme
        root_css = """
        --bg-color: #f4f4f9; --box-bg: #ffffff; --text-main: #333333; --text-muted: #555555;
        --primary: #6200ea; --accent: #6200ea; --border: #dddddd;
        --btn-grad: linear-gradient(90deg, #6200ea 0%, #b388ff 100%);
        --btn-shadow: 0 4px 15px rgba(98, 0, 234, 0.4);
        """

    # ২. মেটাডাটা প্রসেসিং
    lang_str = data.get('custom_language', 'Dual Audio').strip()
    genres_list = [g['name'] for g in data.get('genres', [])] if not data.get('is_manual') else ["Custom Content"]
    genres_str = ", ".join(genres_list) if genres_list else "Unknown Genre"
    year = str(data.get("release_date") or data.get("first_air_date") or "----")[:4]
    rating = f"{data.get('vote_average', 0):.1f}/10"
    runtime = data.get('runtime') or (data.get('episode_run_time', [0])[0] if data.get('episode_run_time') else "N/A")
    runtime_str = f"{runtime} min" if runtime != "N/A" else "N/A"
    cast_list = data.get('credits', {}).get('cast', [])
    cast_names = ", ".join([c['name'] for c in cast_list[:4]]) if cast_list else "Unknown Cast"

    # ৩. পোস্টার এবং স্ক্রিনশট (Blur if Adult)
    if is_adult:
        poster_html = f'''
        <div class="nsfw-container" onclick="revealNSFW(this)">
            <img src="{poster}" alt="Poster" class="nsfw-blur">
            <div class="nsfw-warning">🔞 18+ CONTENT<br><small>Click to Reveal</small></div>
        </div>'''
    else:
        poster_html = f'<img src="{poster}" alt="{title} Poster" class="poster-img">'

    # ৪. ট্রেলার লজিক
    trailer_key = ""
    videos = data.get('videos', {}).get('results', [])
    for v in videos:
        if v.get('type') == 'Trailer' and v.get('site') == 'YouTube':
            trailer_key = v.get('key')
            break
    trailer_html = f'''
    <div class="section-title">🎬 Official Trailer</div>
    <div class="video-container">
        <iframe src="https://www.youtube.com/embed/{trailer_key}" allowfullscreen></iframe>
    </div>''' if trailer_key else ""

    # ৫. স্ক্রিনশট লজিক
    ss_html = ""
    screenshots = data.get('manual_screenshots', [])
    if not screenshots and not data.get('is_manual'):
        backdrops = data.get('images', {}).get('backdrops', [])
        screenshots = [f"https://image.tmdb.org/t/p/w780{b['file_path']}" for b in backdrops[:6]] 
    if screenshots:
        ss_imgs = ""
        for img in screenshots:
            if is_adult:
                ss_imgs += f'<div class="nsfw-container" onclick="revealNSFW(this)"><img src="{img}" class="nsfw-blur"><div class="nsfw-warning"><small>🔞 View</small></div></div>'
            else:
                ss_imgs += f'<img src="{img}" alt="SS">'
        ss_html = f'<div class="section-title">📸 Screenshots</div><div class="screenshot-grid">{ss_imgs}</div>'

    # ৬. লাইভ প্লেয়ার (Embed) সুইচ লজিক
    embed_links = []
    for link in links:
        if link.get("is_grouped"):
            if link.get('filemoon_url'):
                embed_links.append({'name': 'Filemoon HD', 'url': link['filemoon_url']})
            if link.get('mixdrop_url'):
                m_url = link['mixdrop_url']
                if m_u := m_url.startswith("//"): m_url = "https:" + m_url
                embed_links.append({'name': 'MixDrop Pro', 'url': m_url})

    embed_html = ""
    if embed_links:
        server_tabs = ""
        for i, el in enumerate(embed_links):
            b64_url = base64.b64encode(el['url'].encode()).decode()
            active_class = "active" if i == 0 else ""
            server_tabs += f'<button class="server-tab {active_class}" onclick="changeServer(\'{b64_url}\', this)">📺 {el["name"]}</button>'
        
        embed_html = f'''
        <div class="section-title">🍿 Watch Online (Live Player)</div>
        <div class="embed-container">
            <iframe id="main-embed-player" src="{embed_links[0]['url']}" allowfullscreen="true"></iframe>
        </div>
        <div class="server-switcher">
            {server_tabs}
        </div>
        <hr style="border-top: 1px dashed var(--border); margin: 20px 0;">'''

    # ৭. ডাউনলোড সার্ভার গ্রিড লজিক
    server_list_html = ""
    grouped_links = {}
    for link in links:
        lbl = link.get('label', 'Download')
        if lbl not in grouped_links: grouped_links[lbl] = []
        grouped_links[lbl].append(link)

    for lbl, grp in grouped_links.items():
        server_list_html += f'<div class="quality-title">📺 {lbl}</div><div class="server-grid">'
        for link in grp:
            if link.get("is_grouped"):
                # ৮টি ভিন্ন সার্ভারের জন্য বাটন জেনারেট
                server_map = [
                    ('filemoon_url', '🎬 Filemoon', '#673AB7'),
                    ('mixdrop_url', '⚡ MixDrop', '#FFC107'),
                    ('dood_url', '🎬 DoodStream', '#F57C00'),
                    ('stape_url', '🎥 Streamtape', '#E91E63'),
                    ('gofile_url', '▶️ GoFile Fast', '#2196F3'),
                    ('tg_url', '✈️ Telegram', '#0088cc'),
                    ('fileditch_url', '☁️ Direct Cloud', '#009688'),
                    ('tmpfiles_url', '🚀 High Speed', '#6A1B9A'),
                    ('pixel_url', '⚡ Fast Server 2', '#2E7D32')
                ]
                for key, name, color in server_map:
                    if link.get(key):
                        u_b64 = base64.b64encode(link[key].encode()).decode()
                        txt_color = "#000" if key == 'mixdrop_url' else "#fff"
                        server_list_html += f'<button class="final-server-btn" onclick="goToLink(\'{u_b64}\')" style="background:{color}; color:{txt_color};">{name}</button>'
            else:
                u_b64 = base64.b64encode(link.get('url', '').encode()).decode()
                server_list_html += f'<button class="final-server-btn" onclick="goToLink(\'{u_b64}\')" style="background:#0088cc; color:#fff;">📥 Download Link</button>'
        server_list_html += '</div>'

    # ৮. রেভিনিউ শেয়ার অ্যাড লজিক
    weighted_ads = []
    u_list = user_ad_links_list if user_ad_links_list else ["https://google.com"]
    o_list = owner_ad_links_list if owner_ad_links_list else ["https://google.com"]
    admin_slots = int(admin_share_percent)
    user_slots = 100 - admin_slots
    for _ in range(admin_slots): weighted_ads.append(random.choice(o_list))
    for _ in range(user_slots): weighted_ads.append(random.choice(u_list))
    random.shuffle(weighted_ads)

    # ৯. ফুল এইচটিএমএল স্ট্রিং রিটার্ন (বিশাল অংশ)
    return f"""
    <!-- ADVANCED SPA BOT GENERATED CODE -->
    <style>
        :root {{ {root_css} }}
        * {{ box-sizing: border-box; }}
        body {{ background: #000; margin: 0; padding: 0; }}
        .app-wrapper {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: var(--bg-color); border: 1px solid var(--border); border-radius: 15px; max-width: 650px; margin: 20px auto; padding: 25px; color: var(--text-main); box-shadow: 0 10px 40px rgba(0,0,0,0.7); position: relative; overflow: hidden; }}
        
        .movie-title {{ color: var(--accent); font-size: 26px; font-weight: 800; text-align: center; margin-bottom: 25px; text-transform: uppercase; letter-spacing: 1px; line-height: 1.3; }}
        
        .info-box {{ display: flex; flex-direction: row; background: var(--box-bg); border: 1px solid var(--border); border-radius: 12px; padding: 18px; gap: 20px; margin-bottom: 25px; align-items: center; transition: 0.3s; }}
        @media (max-width: 480px) {{ .info-box {{ flex-direction: column; text-align: center; }} }}
        .info-box:hover {{ transform: translateY(-5px); border-color: var(--primary); }}
        
        .info-poster {{ flex-shrink: 0; }}
        .info-poster img {{ width: 160px; border-radius: 10px; border: 2px solid var(--border); box-shadow: 0 5px 15px rgba(0,0,0,0.5); }}
        
        .info-text {{ flex: 1; font-size: 14px; color: var(--text-muted); line-height: 1.8; }}
        .info-text div {{ margin-bottom: 5px; }}
        .info-text span {{ color: var(--primary); font-weight: bold; margin-right: 5px; }}
        
        .section-title {{ font-size: 19px; color: var(--text-main); margin: 25px 0 15px; border-bottom: 3px solid var(--primary); display: inline-block; padding-bottom: 5px; font-weight: 800; text-transform: uppercase; }}
        
        .plot-box {{ background: rgba(255,255,255,0.03); padding: 18px; border-left: 5px solid var(--primary); border-radius: 6px; font-size: 14.5px; color: var(--text-muted); margin-bottom: 25px; line-height: 1.7; text-align: justify; border-top: 1px solid var(--border); border-right: 1px solid var(--border); border-bottom: 1px solid var(--border); }}
        
        .video-container, .embed-container {{ position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; border-radius: 12px; margin-bottom: 20px; border: 2px solid var(--border); background: #000; box-shadow: 0 5px 20px rgba(0,0,0,0.5); }}
        .video-container iframe, .embed-container iframe {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: none; }}
        
        .screenshot-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 30px; }}
        .screenshot-grid img {{ width: 100%; border-radius: 10px; border: 1px solid var(--border); transition: 0.4s; filter: brightness(0.8); cursor: pointer; }}
        .screenshot-grid img:hover {{ filter: brightness(1.1); transform: scale(1.05); z-index: 2; }}
        
        .action-grid {{ display: flex; flex-direction: column; gap: 18px; margin-top: 25px; }}
        .main-btn {{ width: 100%; padding: 18px; font-size: 17px; font-weight: 800; text-transform: uppercase; color: #fff; border: none; border-radius: 10px; cursor: pointer; transition: 0.3s; display: flex; justify-content: center; align-items: center; gap: 12px; letter-spacing: 1.5px; }}
        .btn-watch {{ background: var(--btn-grad); box-shadow: var(--btn-shadow); }}
        .btn-download {{ background: linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%); color: #000; box-shadow: 0 4px 15px rgba(0, 201, 255, 0.4); }}
        .main-btn:hover {{ transform: scale(1.02); filter: brightness(1.2); }}
        .main-btn:disabled {{ filter: grayscale(1); cursor: not-allowed; opacity: 0.6; }}
        
        #view-links {{ display: none; background: var(--box-bg); padding: 25px; border-radius: 15px; border: 1px solid var(--border); text-align: center; animation: fadeIn 0.6s cubic-bezier(0.4, 0, 0.2, 1); }}
        .success-title {{ color: #00e676; font-size: 20px; margin-bottom: 20px; font-weight: 800; text-shadow: 0 0 10px rgba(0,230,118,0.3); }}
        
        .quality-title {{ font-size: 16px; font-weight: 800; color: var(--accent); margin-top: 25px; margin-bottom: 12px; background: rgba(0,0,0,0.2); padding: 10px 15px; border-radius: 8px; text-align: left; border-left: 4px solid var(--accent); border-top: 1px solid var(--border); }}
        .server-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }}
        .final-server-btn {{ width: 100%; padding: 15px; font-size: 14px; font-weight: 700; border: none; border-radius: 8px; cursor: pointer; transition: 0.2s; box-shadow: 0 4px 10px rgba(0,0,0,0.4); }}
        .final-server-btn:hover {{ transform: scale(1.05); filter: brightness(1.2); }}
        
        .server-switcher {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; justify-content: center; }}
        .server-tab {{ background: var(--bg-color); color: var(--text-main); border: 1px solid var(--border); padding: 10px 18px; border-radius: 8px; cursor: pointer; font-size: 13.5px; font-weight: 700; transition: 0.3s; }}
        .server-tab:hover, .server-tab.active {{ background: var(--primary); color: #fff; border-color: var(--primary); transform: translateY(-2px); }}

        .nsfw-container {{ position: relative; cursor: pointer; overflow: hidden; border-radius: 10px; width: 100%; }}
        .nsfw-blur {{ filter: blur(35px) !important; transform: scale(1.15); transition: 0.6s; width: 100%; display: block; }}
        .nsfw-warning {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.9); color: #ff5252; padding: 15px; border-radius: 10px; font-weight: 800; text-align: center; border: 2px solid #ff5252; box-shadow: 0 0 20px rgba(255,82,82,0.4); z-index: 10; pointer-events: none; }}

        .promo-box {{ margin-top: 35px; text-align: center; border-top: 1px solid var(--border); padding-top: 20px; }}
        .promo-box img {{ width: 100%; max-width: 320px; border-radius: 15px; transition: 0.3s; }}
        .promo-box img:hover {{ transform: scale(1.05); }}
    </style>

    <div class="app-wrapper">
        <div id="view-details">
            <div class="movie-title">{title} ({year})</div>
            <div class="info-box">
                <div class="info-poster">{poster_html}</div>
                <div class="info-text">
                    <div><span>⭐ RATING:</span> {rating}</div>
                    <div><span>🎭 GENRE:</span> {genres_str}</div>
                    <div><span>🗣️ LANGUAGE:</span> {lang_str}</div>
                    <div><span>⏱️ RUNTIME:</span> {runtime_str}</div>
                    <div><span>👥 CAST:</span> {cast_names}</div>
                </div>
            </div>
            <div class="section-title">📖 STORYLINE</div>
            <div class="plot-box">{overview}</div>
            {trailer_html}
            {ss_html}
            <div class="section-title">📥 LINKS & PLAYER</div>
            <div class="action-grid">
                <button class="main-btn btn-watch" onclick="startUnlock(this)">▶️ WATCH ONLINE (LIVE PLAYER)</button>
                <button class="main-btn btn-download" onclick="startUnlock(this)">📥 DOWNLOAD FILES & LINKS</button>
            </div>
        </div>
        
        <div id="view-links">
            <div class="success-title">✅ SUCCESSFULLY UNLOCKED!</div>
            {embed_html}
            <div class="section-title">📥 DOWNLOAD SERVERS</div>
            {server_list_html}
        </div>
        
        <div class="promo-box">
            <a href="https://t.me/+6hvCoblt6CxhZjhl" target="_blank"><img src="{BTN_TELEGRAM}"></a>
        </div>
    </div>

    <script>
    const ADS = {json.dumps(weighted_ads)};
    function startUnlock(btn) {{
        const randomAd = ADS[Math.floor(Math.random() * ADS.length)];
        window.open(randomAd, '_blank');
        
        const btns = document.querySelectorAll('.main-btn');
        btns.forEach(b => b.disabled = true);
        
        let timeLeft = 5;
        const timer = setInterval(() => {{
            btn.innerHTML = "⏳ PLEASE WAIT... " + timeLeft + "s";
            if(timeLeft-- <= 0) {{
                clearInterval(timer);
                document.getElementById('view-details').style.display = 'none';
                document.getElementById('view-links').style.display = 'block';
                window.scrollTo({{top: 0, behavior: 'smooth'}});
            }}
        }}, 1000);
    }}
    
    function goToLink(b64) {{
        window.location.href = atob(b64);
    }}
    
    function changeServer(b64, btn) {{
        document.getElementById('main-embed-player').src = atob(b64);
        document.querySelectorAll('.server-tab').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
    }}
    
    function revealNSFW(container) {{
        const img = container.querySelector('img');
        if(img) img.classList.remove('nsfw-blur');
        const warn = container.querySelector('.nsfw-warning');
        if(warn) warn.style.display = 'none';
        container.onclick = null;
        container.style.cursor = 'default';
    }}
    </script>
    """# ====================================================================
# 🔥 TMDB SEARCH & DATA EXTRACTION LOGIC (DETAILED)
# ====================================================================

def extract_tmdb_id(text):
    """টেক্সট বা ইউআরএল থেকে TMDB বা IMDb আইডি খুঁজে বের করে"""
    # ১. TMDB ইউআরএল চেক
    tmdb_match = re.search(r'themoviedb\.org/(movie|tv)/(\d+)', text)
    if tmdb_match:
        return tmdb_match.group(1), tmdb_match.group(2)
    
    # ২. IMDb ইউআরএল চেক
    imdb_url_match = re.search(r'imdb\.com/title/(tt\d+)', text)
    if imdb_url_match:
        return "imdb", imdb_url_match.group(1)
    
    # ৩. শুধু IMDb আইডি (tt123456) চেক
    imdb_id_match = re.search(r'(tt\d{6,})', text)
    if imdb_id_match:
        return "imdb", imdb_id_match.group(1)
    
    return None, None

async def fetch_url(url, method="GET", data=None, headers=None, json_data=None):
    """গ্লোবাল এইচটিটিপি রিকোয়েস্ট ফাংশন"""
    async with aiohttp.ClientSession() as session:
        try:
            if method == "GET":
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        if "application/json" in resp.headers.get("Content-Type", ""):
                            return await resp.json()
                        return await resp.read()
            elif method == "POST":
                async with session.post(url, data=data, json=json_data, headers=headers, ssl=False, timeout=15) as resp:
                    return await resp.text()
        except Exception as e:
            logger.error(f"HTTP Request Error: {e}")
            return None
    return None

async def search_tmdb(query):
    """TMDB থেকে মুভি বা সিরিজ সার্চ করার লজিক"""
    try:
        # মুভির নাম এবং বছর আলাদা করা (যদি থাকে)
        match = re.search(r'(.+?)\s*\(?(\d{4})\)?$', query)
        name = match.group(1).strip() if match else query.strip()
        year = match.group(2) if match else None
        
        url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={name}&include_adult=true"
        if year:
            url += f"&year={year}"
        
        data = await fetch_url(url)
        if not data:
            return []
        
        # শুধুমাত্র মুভি এবং টিভি শো ফিল্টার করা
        return [r for r in data.get("results", []) if r.get("media_type") in ["movie", "tv"]][:15]
    except Exception as e:
        logger.error(f"TMDB Search Error: {e}")
        return []

async def get_tmdb_details(media_type, media_id):
    """আইডি ব্যবহার করে মুভির সব ডিটেইলস (Cast, Video, Images) আনা"""
    url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={TMDB_API_KEY}&append_to_response=credits,similar,images,videos&include_image_language=en,null"
    return await fetch_url(url)

async def create_paste_link(content):
    """dpaste.com এপিআই ব্যবহার করে এইচটিএমএল কোডের লিঙ্ক তৈরি"""
    if not content:
        return None
    url = "https://dpaste.com/api/"
    data = {
        "content": content, 
        "syntax": "html", 
        "expiry_days": 14, 
        "title": "Movie Post SPA Code"
    }
    headers = {'User-Agent': 'Mozilla/5.0'}
    link = await fetch_url(url, method="POST", data=data, headers=headers)
    if link and "dpaste.com" in link:
        return link.strip()
    return None

# ====================================================================
# 🔥 ADVANCED IMAGE CARD GENERATOR (PIL DRAWING LOGIC)
# ====================================================================

def generate_formatted_caption(data, pid=None):
    """বটের জন্য সুন্দর স্টাইলিশ ক্যাপশন জেনারেটর"""
    title = data.get("title") or data.get("name") or "N/A"
    is_adult = data.get('adult', False) or data.get('force_adult', False)
    
    if data.get('is_manual'):
        year, rating, genres, language = "Manual", "⭐ N/A", "Custom", "N/A"
    else:
        year = (data.get("release_date") or data.get("first_air_date") or "----")[:4]
        rating = f"⭐ {data.get('vote_average', 0):.1f}/10"
        genres = ", ".join([g["name"] for g in data.get("genres", [])] or ["N/A"])
        language = data.get('custom_language', '').title()
    
    overview = data.get("overview", "No plot available.")
    
    caption = f"🎬 **{title} ({year})**\n"
    if pid:
        caption += f"🆔 **ID:** `{pid}` (Use to Edit)\n\n"
    
    if is_adult:
        caption += "⚠️ **WARNING: 18+ ADULT CONTENT**\n\n"
    
    if not data.get('is_manual'):
        caption += f"**🎭 GENRES:** {genres}\n"
        caption += f"**🗣️ LANGUAGE:** {language}\n"
        caption += f"**⭐ RATING:** {rating}\n\n"
        
    caption += f"**📝 STORYLINE:** _{overview[:350]}..._\n\n"
    caption += f"⚠️ _Disclaimer: This post is for informational purposes only._"
    return caption

def generate_image(data):
    """মুভির পোস্টার এবং ব্যাকড্রপ দিয়ে একটি প্রিমিয়াম ইনফো কার্ড ড্র করে"""
    try:
        # ১. পোস্টার কালেকশন
        poster_url = data.get('manual_poster_url') or (f"https://image.tmdb.org/t/p/w500{data['poster_path']}" if data.get('poster_path') else None)
        if not poster_url:
            return None, None
            
        poster_bytes = requests.get(poster_url, timeout=10, verify=False).content
        is_adult = data.get('adult', False) or data.get('force_adult', False)
        
        # ২. স্মার্ট ব্যাজ অ্যাপ্লাই
        if data.get('badge_text'):
            badge_io = apply_badge_to_poster(poster_bytes, data['badge_text'])
            poster_bytes = badge_io.getvalue()

        # ৩. মেইন পোস্টার ইমেজ প্রসেস
        poster_img = Image.open(io.BytesIO(poster_bytes)).convert("RGBA").resize((410, 610))
        if is_adult:
            poster_img = poster_img.filter(ImageFilter.GaussianBlur(25))

        # ৪. ব্যাকগ্রাউন্ড ক্যানভাস (1280x720)
        bg_canvas = Image.new('RGBA', (1280, 720), (10, 10, 20, 255))
        
        # ৫. ব্যাকড্রপ ব্লার ইফেক্ট
        backdrop_path = data.get('backdrop_path')
        backdrop = None
        if backdrop_path and not data.get('is_manual'):
            try:
                bd_url = f"https://image.tmdb.org/t/p/w1280{backdrop_path}"
                bd_bytes = requests.get(bd_url, timeout=10, verify=False).content
                backdrop = Image.open(io.BytesIO(bd_bytes)).convert("RGBA").resize((1280, 720))
            except:
                pass
        
        if not backdrop:
            # যদি ব্যাকড্রপ না থাকে তবে পোস্টারকেই ব্যাকগ্রাউন্ড হিসেবে ব্যবহার করা
            backdrop = poster_img.resize((1280, 720))
            
        backdrop = backdrop.filter(ImageFilter.GaussianBlur(15))
        
        # ব্যাকগ্রাউন্ডের ওপর ডার্ক ওভারলে বসানো
        overlay = Image.new('RGBA', (1280, 720), (0, 0, 0, 180))
        bg_canvas = Image.alpha_composite(backdrop, overlay)
        
        # ৬. পোস্টারটি ক্যানভাসের বাম দিকে বসানো
        bg_canvas.paste(poster_img, (55, 55), poster_img)
        
        # ৭. টেক্সট ড্রয়িং লজিক
        draw = ImageDraw.Draw(bg_canvas)
        f_title = get_font(size=48, bold=True)
        f_info = get_font(size=26, bold=False)
        f_plot = get_font(size=22, bold=False)

        title = data.get("title") or data.get("name")
        year = (data.get("release_date") or data.get("first_air_date") or "----")[:4]
        
        if is_adult:
            title += " (🔞 18+)"

        # টাইটেল ড্র করা
        draw.text((510, 80), f"{title} ({year})", font=f_title, fill="#00d2ff", stroke_width=2, stroke_fill="black")
        
        if not data.get('is_manual'):
            # রেটিং এবং জনরা ড্র করা
            draw.text((510, 155), f"⭐ Rating: {data.get('vote_average', 0):.1f}/10", font=f_info, fill="#00e676")
            
            genres = ", ".join([g["name"] for g in data.get("genres", [])[:3]])
            draw.text((510, 200), f"🎭 Genre: {genres}", font=f_info, fill="#ffeb3b")
            
            lang = data.get('custom_language', 'Dual Audio')
            draw.text((510, 245), f"🗣️ Language: {lang}", font=f_info, fill="#ffffff")

        # ৮. স্টোরিলাইন/প্লট ড্র করা (স্মার্ট র‍্যাপিং)
        overview = data.get("overview", "No plot description available for this content.")
        # প্লটকে লাইনে ভাগ করা
        words = overview.split()
        lines = []
        current_line = ""
        for word in words:
            if len(current_line) + len(word) < 60:
                current_line += word + " "
            else:
                lines.append(current_line)
                current_line = word + " "
        lines.append(current_line)
        
        # সর্বোচ্চ ৭ লাইন ড্র করা
        y_text = 310
        draw.text((510, y_text - 35), "📖 STORYLINE:", font=f_info, fill="#00d2ff")
        for line in lines[:7]:
            draw.text((510, y_text), line.strip(), font=f_plot, fill="#E0E0E0")
            y_text += 32
            
        # ইমেজটি বাফারে সেভ করা
        img_buffer = io.BytesIO()
        img_buffer.name = "info_card.png"
        bg_canvas.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        
        return img_buffer, poster_bytes 
    except Exception as e:
        logger.error(f"Image Generation Error: {e}")
        return None, None

def generate_file_caption(details):
    """ডাউনলোড ফাইলের সাথে দেওয়ার জন্য শর্ট ক্যাপশন"""
    title = details.get("title") or details.get("name") or "Unknown"
    year = (details.get("release_date") or details.get("first_air_date") or "----")[:4]
    rating = f"{details.get('vote_average', 0):.1f}/10"
    
    if details.get('is_manual'):
        genres, lang = "Movie/Series", details.get("custom_language") or "N/A"
    else:
        genres = ", ".join([g['name'] for g in details.get('genres', [])][:3])
        lang = details.get("custom_language") or "Dual Audio"
        
    return f"🎬 **{title} ({year})**\n━━━━━━━━━━━━━━━━━━━━━━━\n⭐ Rating: {rating}\n🎭 Genre: {genres}\n🔊 Language: {lang}\n\n🤖 Join Us: @{(bot.me).username if bot.me else 'Bot'}"# ====================================================================
# 🔥 CORE UPLOAD ORCHESTRATOR (THE REAL DOUBLE UPLOAD FIX)
# ====================================================================

async def down_progress(current, total, status_msg, start_time, last_update_time):
    """ডাউনলোড প্রগ্রেস বার দেখানোর ফাংশন"""
    now = time.time()
    if now - last_update_time[0] >= 3.5 or current == total:
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
        try:
            await status_msg.edit_text(
                f"⏳ **২/৩: বট সার্ভারে ডাউনলোড হচ্ছে...**\n\n"
                f"📊 {bar} {percent:.1f}%\n"
                f"💾 {hb(current)} / {hb(total)}\n"
                f"🚀 স্পিড: {hb(speed)}/s | ⏱️ সময়: {int(eta)}s"
            )
        except: pass

async def process_file_upload(client, message, uid, temp_name):
    """
    ভিডিও ফাইল ডাউনলোড করে ৮টি মাল্টি-সার্ভারে আপলোড করার মেইন ইঞ্জিন।
    🚀 ডাবল আপলোড প্রতিরোধের জন্য এখানে ইউনিক আইডি ট্র্যাকিং ব্যবহার করা হয়েছে।
    """
    convo = user_conversations.get(uid)
    if not convo: return
    
    # 🚫 ডাবল আপলোড প্রোটেকশন: একই মেসেজ আইডি একবারের বেশি প্রসেস হবে না
    if "processing_ids" not in convo: convo["processing_ids"] = set()
    if message.id in convo["processing_ids"]:
        return 
    convo["processing_ids"].add(message.id)
    
    convo["pending_uploads"] = convo.get("pending_uploads", 0) + 1
    status_msg = await message.reply_text(f"🕒 **সারির অপেক্ষায় (Queued)...**\n({temp_name})", quote=True)
    
    # ওয়ার্কার বা মেইন বট সিলেক্ট করা
    uploader = worker_client if (worker_client and worker_client.is_connected) else client
    
    try:
        async with upload_semaphore:
            await status_msg.edit_text(f"⏳ **১/৩: টেলিগ্রাম ডাটাবেসে সেভ হচ্ছে...**\n({temp_name})")
            
            # ডাটাবেস চ্যানেলে কপি করা
            copied_msg = await message.copy(chat_id=DB_CHANNEL_ID)
            bot_username = (await client.get_me()).username
            tg_link = f"https://t.me/{bot_username}?start=get-{copied_msg.id}"
            
            # ফাইল ডাউনলোড করা
            start_time = time.time()
            last_update_time = [start_time]
            file_path = await uploader.download_media(
                message, 
                progress=down_progress, 
                progress_args=(status_msg, start_time, last_update_time)
            )

            await status_msg.edit_text(f"⏳ **৩/৩: এক্সটার্নাল মাল্টি-সার্ভারে আপলোড হচ্ছে...**\n({temp_name})\n_(প্যারালাল আপলোড প্রসেস চলছে)_")
            
            # ৮টি ভিন্ন সার্ভারে প্যারালাল আপলোড লজিক
            tasks = [
                upload_to_gofile(file_path), upload_to_fileditch(file_path),
                upload_to_tmpfiles(file_path), upload_to_pixeldrain(file_path),
                upload_to_doodstream(file_path), upload_to_streamtape(file_path),
                upload_to_filemoon(file_path), upload_to_mixdrop(file_path)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # ফাইল ডিলিট করা
            if os.path.exists(file_path): os.remove(file_path)
            
            # রেজাল্টগুলো লিঙ্কে সেভ করা
            convo["links"].append({
                "label": temp_name,
                "tg_url": tg_link,
                "is_grouped": True,
                "gofile_url": results[0] if isinstance(results[0], str) else None,
                "fileditch_url": results[1] if isinstance(results[1], str) else None,
                "tmpfiles_url": results[2] if isinstance(results[2], str) else None,
                "pixel_url": results[3] if isinstance(results[3], str) else None,
                "dood_url": results[4] if isinstance(results[4], str) else None,
                "stape_url": results[5] if isinstance(results[5], str) else None,
                "filemoon_url": results[6] if isinstance(results[6], str) else None,
                "mixdrop_url": results[7] if isinstance(results[7], str) else None,
            })
            
            await status_msg.edit_text(f"✅ **আপলোড সম্পন্ন:** {temp_name}")
            
    except Exception as e:
        logger.error(f"Upload Master Error: {e}")
        await status_msg.edit_text(f"❌ ফেইলড: {e}")
    finally:
        convo["pending_uploads"] = max(0, convo.get("pending_uploads", 0) - 1)
        if message.id in convo["processing_ids"]:
            convo["processing_ids"].remove(message.id)

# ====================================================================
# 🔥 BOT COMMAND HANDLERS (START, CANCEL, ADMIN)
# ====================================================================

bot = Client("moviebot", api_id=int(API_ID), api_hash=API_HASH, bot_token=BOT_TOKEN)

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    uid = message.from_user.id
    name = message.from_user.first_name
    await add_user(uid, name) 
    
    # ডিপ লিঙ্কিং চেক (ফাইল ডাউনলোড করার জন্য)
    if len(message.command) > 1:
        payload = message.command[1]
        if payload.startswith("get-"):
            if await is_banned(uid): return
            try:
                msg_id = int(payload.split("-")[1])
                # ফাইলটি পোস্ট ডাটাবেসে আছে কিনা চেক (ক্যাপশন ঠিক করার জন্য)
                post = await posts_col.find_one({"links.tg_url": {"$regex": f"get-{msg_id}"}})
                cap = generate_file_caption(post["details"]) if post else "🎥 **আপনার ফাইলটি নিচে দেওয়া হলো:**"
                
                f_msg = await client.copy_message(chat_id=uid, from_chat_id=DB_CHANNEL_ID, message_id=msg_id, caption=cap)
                timer = await get_auto_delete_timer()
                if timer > 0:
                    warn = await message.reply_text(f"⚠️ কপিরাইট এড়াতে ফাইলটি **{timer} সেকেন্ড** পর ডিলিট হবে।")
                    asyncio.create_task(auto_delete_task(client, uid, [f_msg.id, warn.id], timer))
                return 
            except: return await message.reply_text("❌ ফাইলটি খুঁজে পাওয়া যায়নি।")

    user_conversations.pop(uid, None)
    if not await is_authorized(uid):
        return await message.reply_text("⚠️ অ্যাক্সেস নেই। এডমিনের সাথে যোগাযোগ করুন।")

    await message.reply_text(f"👋 **স্বাগতম {name}!**\n\n🎬 পোস্ট করতে: `/post MovieName` লিখুন।\n📝 ম্যানুয়াল: `/manual` লিখুন।")

@bot.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client, message):
    user_conversations.pop(message.from_user.id, None)
    await message.reply_text("✅ চলমান সব প্রসেস বাতিল করা হয়েছে।")

# ADMIN COMMANDS
@bot.on_message(filters.command(["auth", "ban", "stats", "broadcast", "setapi", "setworker", "setdel", "setshare"]) & filters.user(OWNER_ID))
async def admin_panel(client, message):
    cmd = message.command[0]
    if cmd == "auth":
        target = int(message.command[1]); await users_col.update_one({"_id": target}, {"$set": {"authorized": True}}, upsert=True)
        await message.reply_text(f"✅ User {target} Authorized.")
    elif cmd == "stats":
        u = await get_all_users_count(); p = await posts_col.count_documents({})
        await message.reply_text(f"📊 **বট স্ট্যাটস**\n\nইউজার: {u}\nপোস্ট: {p}")
    elif cmd == "setapi":
        await set_server_api(message.command[1].lower(), message.command[2])
        await message.reply_text(f"✅ {message.command[1]} API Saved.")
    elif cmd == "broadcast":
        if not message.reply_to_message: return
        count = 0
        async for user in users_col.find({}):
            try: await message.reply_to_message.copy(user["_id"]); count += 1; await asyncio.sleep(0.05)
            except: pass
        await message.reply_text(f"✅ {count} জনকে মেসেজ পাঠানো হয়েছে।")

# ====================================================================
# 🔥 STATE MACHINE: TEXT & MEDIA HANDLER (THE BIG PIECE)
# ====================================================================

@bot.on_message(filters.private & (filters.text | filters.video | filters.document | filters.photo) & ~filters.command(["start", "post", "manual", "edit", "cancel", "history"]))
async def main_handler(client, message):
    uid = message.from_user.id
    if uid not in user_conversations: return
    
    convo = user_conversations[uid]
    state = convo.get("state")
    text = message.text.strip() if message.text else ""

    # ১. ম্যানুয়াল পোস্ট স্টেট
    if state == "manual_title":
        convo["details"]["title"] = text; convo["state"] = "manual_plot"
        await message.reply_text("📝 এবার মুভির **স্টোরিলাইন/প্লট** লিখুন:")
    elif state == "manual_plot":
        convo["details"]["overview"] = text; convo["state"] = "manual_poster"
        await message.reply_text("🖼️ এবার একটি **পোস্টার (Photo)** পাঠান:")
    elif state == "manual_poster":
        if not message.photo: return await message.reply_text("⚠️ দয়া করে ছবি পাঠান।")
        p = await message.download(); url = upload_to_catbox(p); os.remove(p)
        convo["details"]["manual_poster_url"] = url; convo["state"] = "ask_screenshots"
        await message.reply_text("✅ পোস্টার সেভ। স্ক্রিনশট দিতে চান?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Add SS", callback_data=f"ss_yes_{uid}"), InlineKeyboardButton("Skip", callback_data=f"ss_no_{uid}")]]))

    # ২. অটো পোস্ট স্টেট
    elif state == "wait_lang":
        convo["details"]["custom_language"] = text; convo["state"] = "wait_quality"
        await message.reply_text("💿 মুভির **কোয়ালিটি** লিখুন (যেমন: 1080p Web-DL):")
    elif state == "wait_quality":
        convo["details"]["custom_quality"] = text; convo["state"] = "ask_links"
        await message.reply_text("🔗 মুভির ডাউনলোড লিঙ্ক বা ফাইল দিবেন?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Add Link", callback_data=f"lnk_yes_{uid}"), InlineKeyboardButton("Finish", callback_data=f"lnk_no_{uid}")]]))

    # ৩. লিঙ্ক এবং ভিডিও ফাইল প্রসেসিং
    elif state == "wait_link_name_custom":
        convo["temp_name"] = text; convo["state"] = "wait_link_url"
        await message.reply_text(f"✅ নাম সেট: {text}। এবার লিঙ্ক দিন বা ভিডিও ফাইল ফরোয়ার্ড করুন:")
    elif state == "wait_link_url":
        if message.video or message.document:
            # 🚀 ডাবল আপলোড ফিক্স: স্টেট সাথে সাথে বদলে দিন যাতে পরের ফাইল না রিসিভ করে
            convo["state"] = "ask_links" 
            asyncio.create_task(process_file_upload(client, message, uid, convo.get("temp_name", "Download")))
            await message.reply_text("⏳ আপলোড শুরু হয়েছে। আরও ফাইল দিতে চাইলে Add এ ক্লিক করুন।", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add More", callback_data=f"lnk_yes_{uid}"), InlineKeyboardButton("🏁 Finish", callback_data=f"lnk_no_{uid}")]]))
        elif text.startswith("http"):
            convo["links"].append({"label": convo["temp_name"], "url": text, "is_grouped": False})
            convo["state"] = "ask_links"; await message.reply_text("✅ লিঙ্ক সেভ হয়েছে।", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add More", callback_data=f"lnk_yes_{uid}"), InlineKeyboardButton("🏁 Finish", callback_data=f"lnk_no_{uid}")]]))

    # ৪. ব্যাচ মোড (সিরিজের জন্য)
    elif state == "wait_batch_files":
        if text.lower() == "/done":
            convo["state"] = "ask_links"; await message.reply_text("✅ ব্যাচ গ্রহণ করা হয়েছে। আপলোড শেষ হলে Finish এ ক্লিক করবেন।", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏁 Finish", callback_data=f"lnk_no_{uid}")]]))
        elif message.video or message.document:
            fname = getattr(message.video, "file_name", None) or f"EP-{len(convo['links'])+1}"
            asyncio.create_task(process_file_upload(client, message, uid, fname))

    elif state == "wait_badge_text":
        convo["details"]["badge_text"] = text
        await message.reply_text("🛡️ **সেফটি চেক:** মুভিটি কি এডাল্ট (18+)?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Safe", callback_data=f"safe_yes_{uid}"), InlineKeyboardButton("🔞 18+", callback_data=f"safe_no_{uid}")]]))

# ====================================================================
# 🔥 CALLBACK QUERIES & FINAL GENERATION
# ====================================================================

@bot.on_callback_query(filters.regex("^sel_|^ss_|^lnk_|^setlname_|^safe_|^theme_|^get_code_"))
async def callbacks(client, cb):
    uid = cb.from_user.id; data = cb.data
    if uid not in user_conversations and not data.startswith("get_code_"): return
    
    if data.startswith("sel_"):
        _, mtype, mid = data.split("_"); d = await get_tmdb_details(mtype, mid)
        user_conversations[uid] = {"details": d, "links": [], "state": "wait_lang"}
        await cb.message.edit_text(f"✅ নির্বাচিত: {d.get('title') or d.get('name')}\n\n🗣️ মুভির **ভাষা** লিখুন:")
    elif data.startswith("lnk_yes"):
        user_conversations[uid]["state"] = "wait_link_name"
        btns = [[InlineKeyboardButton("1080p", callback_data=f"setlname_1080p_{uid}"), InlineKeyboardButton("720p", callback_data=f"setlname_720p_{uid}")],[InlineKeyboardButton("✍️ Custom", callback_data=f"setlname_custom_{uid}"), InlineKeyboardButton("📦 Batch", callback_data=f"setlname_batch_{uid}")]]
        await cb.message.edit_text("বাটন নাম সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(btns))
    elif data.startswith("setlname_"):
        _, act, _ = data.split("_"); user_conversations[uid]["temp_name"] = act
        if act == "batch": 
            user_conversations[uid]["state"] = "wait_batch_files"; await cb.message.edit_text("সব ফাইল একসাথে ফরোয়ার্ড করুন। শেষে /done লিখুন।")
        else:
            user_conversations[uid]["state"] = "wait_link_url"; await cb.message.edit_text(f"✅ সেট: {act}। এবার ফাইল বা লিঙ্ক দিন:")
    elif data.startswith("lnk_no"):
        if user_conversations[uid].get("pending_uploads", 0) > 0: return await cb.answer("⏳ ফাইল আপলোড শেষ হওয়া পর্যন্ত অপেক্ষা করুন...", show_alert=True)
        user_conversations[uid]["state"] = "wait_badge_text"
        await cb.message.edit_text("🖼️ **পোস্টারে ব্যাজ টেক্সট দিবেন?**\n(যেমন: Dual Audio) অথবা Skip করুন।", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚫 Skip", callback_data=f"skip_badge_{uid}")]]))
    elif data.startswith("safe_"):
        user_conversations[uid]["details"]["force_adult"] = (data.split("_")[1] == "no")
        btns = [[InlineKeyboardButton("Netflix", callback_data=f"theme_netflix_{uid}"), InlineKeyboardButton("Prime", callback_data=f"theme_prime_{uid}"), InlineKeyboardButton("Light", callback_data=f"theme_light_{uid}")]]
        await cb.message.edit_text("🎨 **থিম সিলেক্ট করুন:**", reply_markup=InlineKeyboardMarkup(btns))
    elif data.startswith("theme_"):
        user_conversations[uid]["details"]["theme"] = data.split("_")[1]
        await generate_final_post_process(client, uid, cb.message)
    elif data.startswith("get_code_"):
        h = user_conversations[uid].get("final_html"); l = await create_paste_link(h)
        await cb.message.reply_text(f"✅ **ব্লগার কোড লিঙ্ক:**\n{l}")

async def generate_final_post_process(client, uid, message):
    convo = user_conversations[uid]
    st_msg = await message.edit_text("⏳ **পোস্ট জেনারেট হচ্ছে...**")
    try:
        pid = await save_post_to_db(convo["details"], convo["links"])
        img_io, poster_bytes = await asyncio.get_event_loop().run_in_executor(None, generate_image, convo["details"])
        html = generate_html_code(convo["details"], convo["links"], await get_user_ads(uid), await get_owner_ads(), await get_admin_share())
        convo["final_html"] = html
        cap = generate_formatted_caption(convo["details"], pid)
        await client.send_photo(uid, img_io, caption=cap, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📄 Get Blogger Code", callback_data=f"get_code_{uid}")]]))
        await st_msg.delete()
    except Exception as e: await st_msg.edit_text(f"❌ এরর: {e}")

# ====================================================================
# 🔥 FLASK & PINGER KEEP-ALIVE
# ====================================================================
app = Flask(__name__)
@app.route('/')
def home(): return "🤖 V42 SPA Bot is Alive!"

def run_flask(): app.run(host='0.0.0.0', port=8080)
def keep_alive_pinger():
    while True:
        try: requests.get("http://localhost:8080", timeout=5); time.sleep(600)
        except: time.sleep(600)

# ====================================================================
# 🔥 MAIN STARTUP LOOP
# ====================================================================

async def main():
    logger.info("🚀 বট চালু হচ্ছে...")
    await bot.start()
    
    # প্লাগইন লোডার
    p_path = os.path.join(os.path.dirname(__file__), "plugins")
    if os.path.exists(p_path):
        for loader, name, is_pkg in pkgutil.iter_modules([p_path]):
            try:
                mod = importlib.import_module(f"plugins.{name}")
                if hasattr(mod, "register"): await mod.register(bot)
                logger.info(f"✅ Plugin Loaded: {name}")
            except: pass

    await start_worker()
    logger.info("✅ বট এবং ওয়ার্কার অনলাইন!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    Thread(target=keep_alive_pinger, daemon=True).start()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
