# plugins/multi_paste_backup.py
import __main__
import aiohttp
import io
import logging
import asyncio
import os
import time
from pyrogram import filters, handlers
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

# ====================================================================
# 🔥 ১. মাল্টি-সার্ভার আপলোড ফাংশনসমূহ (৮টি অ্যাডভান্স সার্ভার)
# ====================================================================

async def upload_to_gofile(file_path):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.gofile.io/servers") as resp:
                data = await resp.json()
                server = data['data']['servers'][0]['name']
            url = f"https://{server}.gofile.io/contents/uploadfile"
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form) as upload_resp:
                    result = await upload_resp.json()
                    if result['status'] == 'ok': return result['data']['downloadPage']
    except: return None

async def upload_to_fileditch(file_path):
    try:
        url = "https://up1.fileditch.com/upload.php"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('files[]', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form) as resp:
                    result = await resp.json()
                    return result['files'][0]['url']
    except: return None

async def upload_to_tmpfiles(file_path):
    try:
        url = "https://tmpfiles.org/api/v1/upload"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form) as resp:
                    result = await resp.json()
                    if result.get('status') == 'success': return result['data']['url'].replace("api/v1/download/", "")
    except: return None

async def upload_to_pixeldrain(file_path):
    try:
        url = "https://pixeldrain.com/api/file"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form) as resp:
                    result = await resp.json()
                    if result.get('success'): return f"https://pixeldrain.com/u/{result['id']}"
    except: return None

async def upload_to_doodstream(file_path):
    api_key = await __main__.get_server_api("doodstream")
    if not api_key: return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://doodapi.com/api/upload/server?key={api_key}") as resp:
                data = await resp.json()
                upload_url = data['result']
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path)); form.add_field('api_key', api_key)
                async with session.post(upload_url, data=form) as upload_resp:
                    res = await upload_resp.json()
                    if res.get('msg') == 'OK': return res['result'][0]['protected_embed']
    except: return None

async def upload_to_streamtape(file_path):
    api_credentials = await __main__.get_server_api("streamtape")
    if not api_credentials: return None 
    try:
        login_id, api_key = api_credentials.split(":")
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.streamtape.com/file/ul?login={login_id}&key={api_key}") as resp:
                upload_url = (await resp.json())['result']['url']
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData(); form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(upload_url, data=form) as upload_resp:
                    res = await upload_resp.json()
                    if res.get('status') == 200: return res['result']['url']
    except: return None

async def upload_to_filemoon(file_path):
    api_key = await __main__.get_server_api("filemoon")
    if not api_key: return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://filemoonapi.com/api/upload/server?key={api_key}") as resp:
                upload_url = (await resp.json())['result']
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData(); form.add_field('file', f, filename=os.path.basename(file_path)); form.add_field('api_key', api_key)
                async with session.post(upload_url, data=form) as upload_resp:
                    res = await upload_resp.json()
                    if res.get('msg') == 'OK': return f"https://filemoon.sx/e/{res['result'][0]['filecode']}"
    except: return None

async def upload_to_mixdrop(file_path):
    api_credentials = await __main__.get_server_api("mixdrop")
    if not api_credentials or ":" not in api_credentials: return None 
    try:
        email, api_key = api_credentials.split(":")
        url = "https://api.mixdrop.co/upload"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData(); form.add_field('file', f, filename=os.path.basename(file_path))
                form.add_field('email', email); form.add_field('key', api_key)
                async with session.post(url, data=form) as resp:
                    res = await resp.json()
                    if res.get('success'): return res['result']['embedurl']
    except: return None

# ====================================================================
# 🔥 ২. ব্যাকগ্রাউন্ড প্রসেসিং ও প্রগ্রেস সিস্টেম
# ====================================================================

async def down_progress(current, total, status_msg, start_time, last_update_time):
    now = time.time()
    if now - last_update_time[0] >= 3.0 or current == total:
        last_update_time[0] = now
        percent = (current / total) * 100 if total > 0 else 0
        speed = current / (now - start_time) if (now - start_time) > 0 else 1
        eta = (total - current) / speed if speed > 0 else 0
        def hbytes(size):
            for unit in['B', 'KB', 'MB', 'GB']:
                if size < 1024.0: return f"{size:.2f} {unit}"
                size /= 1024.0
            return f"{size:.2f} TB"
        filled = int(percent / 10); bar = "█" * filled + "░" * (10 - filled)
        try: await status_msg.edit_text(f"⏳ **২/৩: ডাউনলোড হচ্ছে...**\n\n📊 {bar} {percent:.1f}%\n💾 {hbytes(current)} / {hbytes(total)}\n🚀 স্পিড: {hbytes(speed)}/s | ⏱️ {int(eta)}s বাকি")
        except: pass

async def plugin_process_upload(client, message, uid, temp_name):
    convo = __main__.user_conversations.get(uid)
    if not convo: return
    convo["pending_uploads"] = convo.get("pending_uploads", 0) + 1
    status_msg = await message.reply_text(f"🕒 **সারির অপেক্ষায় (Queued)...**\n({temp_name})", quote=True)
    uploader = __main__.worker_client if (__main__.worker_client and __main__.worker_client.is_connected) else client
    
    try:
        async with __main__.upload_semaphore:
            await status_msg.edit_text(f"⏳ **১/৩: ডাটাবেসে সেভ হচ্ছে...**\n(By: {'Worker' if uploader == __main__.worker_client else 'Bot'})")
            copied_msg = await message.copy(chat_id=__main__.DB_CHANNEL_ID)
            bot_username = (await client.get_me()).username
            tg_link = f"https://t.me/{bot_username}?start=get-{copied_msg.id}"
            
            start_time = time.time(); last_update_time = [start_time]
            file_path = await uploader.download_media(message, progress=down_progress, progress_args=(status_msg, start_time, last_update_time))
            
            await status_msg.edit_text(f"⏳ **৩/৩: মাল্টি-সার্ভারে আপলোড হচ্ছে...**")
            results = await asyncio.gather(
                upload_to_gofile(file_path), upload_to_fileditch(file_path), upload_to_tmpfiles(file_path),
                upload_to_pixeldrain(file_path), upload_to_doodstream(file_path), upload_to_streamtape(file_path),
                upload_to_filemoon(file_path), upload_to_mixdrop(file_path), return_exceptions=True
            )
            if os.path.exists(file_path): os.remove(file_path)
            
            convo["links"].append({
                "label": temp_name, "tg_url": tg_link, 
                "gofile_url": results[0] if not isinstance(results[0], Exception) else None,
                "fileditch_url": results[1] if not isinstance(results[1], Exception) else None,
                "tmpfiles_url": results[2] if not isinstance(results[2], Exception) else None,
                "pixel_url": results[3] if not isinstance(results[3], Exception) else None,
                "dood_url": results[4] if not isinstance(results[4], Exception) else None,
                "stape_url": results[5] if not isinstance(results[5], Exception) else None,
                "filemoon_url": results[6] if not isinstance(results[6], Exception) else None,
                "mixdrop_url": results[7] if not isinstance(results[7], Exception) else None,
                "is_grouped": True
            })
            await status_msg.edit_text(f"✅ **আপলোড সম্পন্ন:** {temp_name}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Failed: {e}")
    finally:
        convo["pending_uploads"] = max(0, convo.get("pending_uploads", 0) - 1)

# ====================================================================
# 🔥 ৩. মাল্টি-সার্ভার কোড সেভ (PASTE SERVICE)
# ====================================================================

async def enhanced_paste_service(content):
    if not content: return None
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post("https://dpaste.com/api/", data={"content": content, "syntax": "html", "expiry_days": 14}, timeout=10) as resp:
                if resp.status in [200, 201]: return (await resp.text()).strip()
        except: pass
        try:
            async with session.post("https://paste.rs", data=content.encode('utf-8'), timeout=10) as resp:
                if resp.status in [200, 201]: return await resp.text()
        except: pass
    return None

async def patched_get_code(client, cb):
    try: _, _, uid = cb.data.rsplit("_", 2); uid = int(uid)
    except: return
    data = __main__.user_conversations.get(uid)
    if not data or "final" not in data: return await cb.answer("❌ ডেটা পাওয়া যায়নি!", show_alert=True)
    await cb.answer("⏳ জেনারেট হচ্ছে (Multi-Server Try)...", show_alert=False)
    html_code = data["final"]["html"]; link = await enhanced_paste_service(html_code)
    btns = []
    if link: btns.append([InlineKeyboardButton("🌐 Open Blogger Code", url=link)])
    btns.append([InlineKeyboardButton("📝 Get Direct Code (Message)", callback_data=f"get_raw_text_{uid}")])
    btns.append([InlineKeyboardButton("📁 Download HTML File", callback_data=f"send_file_only_{uid}")])
    msg_text = f"✅ **Blogger Code Ready!**\n\n"
    if link: msg_text += f"🔗 **Link:** `{link}`\n\n"
    else: msg_text += f"⚠️ **Paste সার্ভার ডাউন!** কিন্তু নিচের বাটনগুলো ব্যবহার করুন।\n\n"
    await cb.message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(btns), disable_web_page_preview=True)

@__main__.bot.on_callback_query(filters.regex("^get_raw_text_"))
async def get_raw_text_handler(client, cb):
    uid = int(cb.data.split("_")[-1])
    data = __main__.user_conversations.get(uid); code = data["final"]["html"]
    if len(code) < 3800: await cb.message.reply_text(f"👇 **কপি করুন:**\n\n<code>{code}</code>", parse_mode="html")
    else:
        parts = [code[i:i+3800] for i in range(0, len(code), 3800)]
        for part in parts: await cb.message.reply_text(f"<code>{part}</code>", parse_mode="html"); await asyncio.sleep(0.5)
    await cb.answer("কোড পাঠানো হয়েছে!")

async def send_file_handler(client, cb):
    uid = int(cb.data.split("_")[-1]); data = __main__.user_conversations.get(uid)
    if data and "final" in data:
        file = io.BytesIO(data["final"]["html"].encode('utf-8')); file.name = "blogger_code.html"
        await client.send_document(cb.message.chat.id, file, caption="📄 ব্লগার পোস্টের HTML কোড ফাইল।")
        await cb.answer("ফাইল পাঠানো হয়েছে!")

# ====================================================================
# 🔥 ৪. প্লাগইন রেজিস্ট্রেশন (মেইন বটের সাথে কানেকশন)
# ====================================================================

async def register(bot):
    # মেইন বটের ফাংশনগুলোকে প্লাগইন ফাংশন দিয়ে ওভাররাইড (Patch) করা হচ্ছে
    __main__.create_paste_link = enhanced_paste_service
    __main__.process_file_upload = plugin_process_upload
    
    # হ্যান্ডলার অ্যাড করা
    bot.add_handler(handlers.CallbackQueryHandler(patched_get_code, filters.regex("^get_code_")), group=-1)
    bot.add_handler(handlers.CallbackQueryHandler(send_file_handler, filters.regex("^send_file_only_")), group=-1)
    
    print("✅ Multi-Server Uploader & Paste System Integrated Successfully!")
