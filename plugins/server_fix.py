# plugins/movie_server_plugin.py
import os
import aiohttp
import logging
import asyncio
import __main__ as main_mod 

logger = logging.getLogger(__name__)

# --- মুভি সার্ভার আপলোড ফাংশনস ---

async def upload_to_doodstream(file_path):
    """DoodStream Upload (Unlimited Size)"""
    api_key = await main_mod.get_server_api("doodstream")
    if not api_key: return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://doodapi.com/api/upload/server?key={api_key}") as resp:
                data = await resp.json()
                upload_url = data['result']
            
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                form.add_field('api_key', api_key)
                async with session.post(upload_url, data=form) as upload_resp:
                    result = await upload_resp.json()
                    return result['result'][0]['protected_embed']
    except: return None

async def upload_to_streamtape(file_path):
    """Streamtape Upload (Unlimited Size)"""
    api_credentials = await main_mod.get_server_api("streamtape")
    if not api_credentials: return None
    try:
        login_id, api_key = api_credentials.split(":")
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.streamtape.com/file/ul?login={login_id}&key={api_key}") as resp:
                data = await resp.json()
                upload_url = data['result']['url']
            
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(upload_url, data=form) as upload_resp:
                    result = await upload_resp.json()
                    return result['result']['url']
    except: return None

async def upload_to_pixeldrain(file_path):
    """PixelDrain (5GB Limit)"""
    try:
        url = "https://pixeldrain.com/api/file"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form) as resp:
                    result = await resp.json()
                    return f"https://pixeldrain.com/u/{result['id']}"
    except: return None

# --- মেইন প্রসেসর ওভাররাইড (বড় ফাইলের জন্য অপ্টিমাইজড) ---

async def movie_process_upload(client, message, uid, temp_name):
    convo = main_mod.user_conversations.get(uid)
    if not convo: return
    
    convo["pending_uploads"] = convo.get("pending_uploads", 0) + 1
    status_msg = await message.reply_text(f"🎬 **মুভি আপলোড শুরু হয়েছে...**\n📦 ফাইল: {temp_name}", quote=True)
    
    uploader = main_mod.worker_client if (main_mod.worker_client and main_mod.worker_client.is_connected) else client
    
    try:
        async with main_mod.upload_semaphore:
            # ১. ফাইল কপি টু ডিবি চ্যানেল
            copied_msg = await message.copy(chat_id=main_mod.DB_CHANNEL_ID)
            tg_link = f"https://t.me/{(await client.get_me()).username}?start=get-{copied_msg.id}"
            
            # ২. বড় ফাইল ডাউনলোড (প্রগ্রেস বারসহ)
            import time
            start_time = time.time()
            last_update =[start_time]
            
            file_path = await uploader.download_media(
                message, 
                progress=main_mod.down_progress, 
                progress_args=(status_msg, start_time, last_update)
            )

            await status_msg.edit_text("⚡ **ডাউনলোড শেষ! এখন প্রিমিয়াম সার্ভারে আপলোড হচ্ছে...**")
            
            # ৩. প্যারালাল আপলোড (DoodStream, Streamtape, PixelDrain)
            # এগুলো ৫জিবি পর্যন্ত ফাইল সাপোর্ট করবে অনায়াসেই
            tasks = [
                upload_to_doodstream(file_path),
                upload_to_streamtape(file_path),
                upload_to_pixeldrain(file_path),
                main_mod.upload_to_gofile(file_path)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            if os.path.exists(file_path): os.remove(file_path)
            
            # ৪. ডাটা সেভ করা
            convo["links"].append({
                "label": temp_name, 
                "tg_url": tg_link, 
                "dood_url": results[0] if not isinstance(results[0], Exception) else None,
                "stape_url": results[1] if not isinstance(results[1], Exception) else None,
                "pixel_url": results[2] if not isinstance(results[2], Exception) else None,
                "gofile_url": results[3] if not isinstance(results[3], Exception) else None,
                "is_grouped": True
            })
            await status_msg.edit_text(f"✅ **মুভি আপলোড সাকসেস!**\n🎞️ {temp_name}")
            
    except Exception as e:
        logger.error(f"Movie Upload Error: {e}")
        await status_msg.edit_text(f"❌ এরর: {str(e)}")
    finally:
        convo["pending_uploads"] = max(0, convo.get("pending_uploads", 0) - 1)

# --- প্লাগইন একটিভেশন ---
async def register(bot):
    main_mod.process_file_upload = movie_process_upload
    print("🎬 Movie Server Plugin Loaded! High-capacity servers active.")
