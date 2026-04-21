import os
import time
import asyncio
import logging
import aiohttp
import __main__ as main_mod 
from pyrogram.errors import FileReferenceExpired

logger = logging.getLogger(__name__)

# --- ইউটিলিটি: রিডেবল সাইজ ---
def get_readable_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0: return f"{bytes:.2f} {unit}"
        bytes /= 1024.0

# --- ইউটিলিটি: ভিজ্যুয়াল প্রসেস বার ---
def make_bar(percentage):
    completed = int(percentage / 10)
    return "■" * completed + "□" * (10 - completed)

# --- ডাউনলোড প্রসেস বার (TG to Bot) ---
async def fancy_progress(current, total, status_msg, start_time, last_update):
    now = time.time()
    if now - last_update[0] < 4.0 and current != total: return
    last_update[0] = now
    elapsed = max(now - start_time, 1)
    percentage = current * 100 / total
    speed = current / elapsed
    
    txt = (f"📥 **বট সার্ভারে ডাউনলোড হচ্ছে...**\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"🏁 `{make_bar(percentage)}` {percentage:.1f}%\n"
           f"📊 সাইজ: `{get_readable_size(current)}` / `{get_readable_size(total)}`\n"
           f"🚀 স্পিড: `{get_readable_size(speed)}/s`\n"
           f"⏱️ বাকি: `{int((total - current) / speed) if speed > 0 else 0}s`")
    try: await status_msg.edit_text(txt)
    except: pass

# --- আপলোড প্রসেস ট্র্যাকার ক্লাস ---
class AsyncFileReader:
    def __init__(self, file_path, callback):
        self.file_path = file_path
        self.size = os.path.getsize(file_path)
        self.callback = callback
        self._read_bytes = 0

    def __aiter__(self): return self

    async def __anext__(self):
        with open(self.file_path, 'rb') as f:
            f.seek(self._read_bytes)
            chunk = f.read(1024 * 1024) # 1MB Chunk
        if not chunk: raise StopAsyncIteration
        self._read_bytes += len(chunk)
        await self.callback(self._read_bytes, self.size)
        return chunk

# --- গ্লোবাল স্ট্যাটাস ম্যানেজার ---
upload_status = {}

async def update_ui_loop(status_msg, temp_name):
    """এটি একটি লুপ যা আপলোড প্রগ্রেস লাইভ দেখাবে"""
    last_edit = 0
    while True:
        now = time.time()
        if now - last_edit > 4.5:
            msg_txt = f"🎬 **ফাইল:** `{temp_name[:30]}`\n\n☁️ **সার্ভার আপলোড স্ট্যাটাস:**\n━━━━━━━━━━━━━━━━━━━━\n"
            all_done = True
            for server, data in upload_status.items():
                p = data['percent']
                msg_txt += f"🔘 **{server}:** `{make_bar(p)}` {p:.1f}%\n"
                if data['status'] == "running": all_done = False
            
            try: await status_msg.edit_text(msg_txt)
            except: pass
            last_edit = now
            if all_done: break
        await asyncio.sleep(1)

# --- আপলোড ফাংশনস (উইথ লাইভ ট্র্যাকিং) ---

async def upload_dood(file_path, server_name):
    upload_status[server_name] = {'percent': 0, 'status': 'running'}
    api_key = await main_mod.get_server_api("doodstream")
    if not api_key: 
        upload_status[server_name]['status'] = 'error'
        return None
    
    async def cb(c, t): upload_status[server_name]['percent'] = (c/t)*100

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://doodapi.com/api/upload/server?key={api_key}") as r:
                url = (await r.json())['result']
            data = aiohttp.FormData()
            data.add_field('api_key', api_key)
            data.add_field('file', AsyncFileReader(file_path, cb), filename=os.path.basename(file_path))
            async with session.post(url, data=data) as resp:
                res = await resp.json()
                upload_status[server_name]['status'] = 'done'
                return res['result'][0]['protected_embed']
    except:
        upload_status[server_name]['status'] = 'error'
        return None

async def upload_stape(file_path, server_name):
    upload_status[server_name] = {'percent': 0, 'status': 'running'}
    creds = await main_mod.get_server_api("streamtape")
    if not creds or ":" not in creds:
        upload_status[server_name]['status'] = 'error'
        return None
    
    async def cb(c, t): upload_status[server_name]['percent'] = (c/t)*100
    
    try:
        login, key = creds.split(":")
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.streamtape.com/file/ul?login={login}&key={key}") as r:
                url = (await r.json())['result']['url']
            data = aiohttp.FormData()
            data.add_field('file', AsyncFileReader(file_path, cb), filename=os.path.basename(file_path))
            async with session.post(url, data=data) as resp:
                res = await resp.json()
                upload_status[server_name]['status'] = 'done'
                return res['result']['url']
    except:
        upload_status[server_name]['status'] = 'error'
        return None

async def upload_pixel(file_path, server_name):
    upload_status[server_name] = {'percent': 0, 'status': 'running'}
    async def cb(c, t): upload_status[server_name]['percent'] = (c/t)*100
    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('file', AsyncFileReader(file_path, cb), filename=os.path.basename(file_path))
            async with session.post("https://pixeldrain.com/api/file", data=data) as resp:
                res = await resp.json()
                upload_status[server_name]['status'] = 'done'
                return f"https://pixeldrain.com/u/{res['id']}"
    except:
        upload_status[server_name]['status'] = 'error'
        return None

# --- মেইন প্রসেসিং লজিক ---

async def movie_process_upload(client, message, uid, temp_name):
    convo = main_mod.user_conversations.get(uid)
    if not convo: return
    
    convo["pending_uploads"] = convo.get("pending_uploads", 0) + 1
    status_msg = await message.reply_text(f"⏳ **প্রসেসিং:** `{temp_name}`", quote=True)
    
    try:
        async with main_mod.upload_semaphore:
            # ১. ডাউনলোড (Saved Msg ফরোয়ার্ড ফিক্স)
            try: refreshed_msg = await message.forward("me")
            except: refreshed_msg = message

            start_t = time.time()
            f_path = await client.download_media(refreshed_msg, progress=fancy_progress, progress_args=(status_msg, start_t, [0]))
            
            try: await refreshed_msg.delete()
            except: pass

            if not f_path or not os.path.exists(f_path):
                return await status_msg.edit_text("❌ ডাউনলোড ফেইল!")

            # ২. মিরর আপলোড লজিক
            global upload_status
            upload_status = {}
            ui_task = asyncio.create_task(update_ui_loop(status_msg, temp_name))
            
            # ৪টি সার্ভারে একসাথে আপলোড
            up_tasks = [
                upload_dood(f_path, "DoodStream"),
                upload_stape(f_path, "Streamtape"),
                upload_pixel(f_path, "PixelDrain"),
                main_mod.upload_to_gofile(f_path) # GoFile ডিফল্ট থাকবে
            ]
            
            results = await asyncio.gather(*up_tasks)
            await ui_task # UI শেষ হওয়া পর্যন্ত ওয়েট

            if os.path.exists(f_path): os.remove(f_path)

            # ৩. ডাটা সেভ
            copied = await message.copy(chat_id=main_mod.DB_CHANNEL_ID)
            tg_link = f"https://t.me/{(await client.get_me()).username}?start=get-{copied.id}"
            
            convo["links"].append({
                "label": temp_name, "tg_url": tg_link, 
                "dood_url": results[0], "stape_url": results[1],
                "pixel_url": results[2], "gofile_url": results[3],
                "is_grouped": True
            })
            
            # সাকসেস মেসেজ
            success = [s for s, r in zip(["Dood", "Stape", "Pixel", "GoFile"], results) if r]
            await status_msg.edit_text(f"✅ **মুভি আপলোড সফল!**\n📂 `{temp_name}`\n🚀 সার্ভার: {', '.join(success)}")

    except Exception as e:
        logger.error(f"Final Error: {e}")
        await status_msg.edit_text(f"❌ এরর: {str(e)}")
    finally:
        convo["pending_uploads"] = max(0, convo.get("pending_uploads", 0) - 1)

async def register(bot):
    main_mod.process_file_upload = movie_process_upload
    print("💎 Ultimate Pro Movie Plugin: All Features Online!")
