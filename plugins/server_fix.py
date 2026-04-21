import os
import aiohttp
import logging
import asyncio
import time
import __main__ as main_mod 
from pyrogram.errors import FileReferenceExpired

logger = logging.getLogger(__name__)

# --- মিরর সার্ভার ফাংশনস (উন্নত এরর হ্যান্ডলিং সহ) ---

async def upload_to_doodstream(file_path):
    api_key = await main_mod.get_server_api("doodstream")
    if not api_key or not os.path.exists(file_path): return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://doodapi.com/api/upload/server?key={api_key}", timeout=10) as resp:
                data = await resp.json()
                upload_url = data['result']
            
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                form.add_field('api_key', api_key)
                async with session.post(upload_url, data=form) as upload_resp:
                    result = await upload_resp.json()
                    return result['result'][0]['protected_embed']
    except Exception as e:
        logger.error(f"DoodStream Error: {e}")
        return None

async def upload_to_streamtape(file_path):
    api_credentials = await main_mod.get_server_api("streamtape")
    if not api_credentials or ":" not in api_credentials or not os.path.exists(file_path): return None
    try:
        login_id, api_key = api_credentials.split(":")
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.streamtape.com/file/ul?login={login_id}&key={api_key}", timeout=10) as resp:
                data = await resp.json()
                upload_url = data['result']['url']
            
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(upload_url, data=form) as upload_resp:
                    result = await upload_resp.json()
                    return result['result']['url']
    except Exception as e:
        logger.error(f"Streamtape Error: {e}")
        return None

async def upload_to_pixeldrain(file_path):
    if not os.path.exists(file_path): return None
    try:
        url = "https://pixeldrain.com/api/file"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form) as resp:
                    result = await resp.json()
                    if result.get('success'):
                        return f"https://pixeldrain.com/u/{result['id']}"
    except Exception as e:
        logger.error(f"PixelDrain Error: {e}")
        return None

# --- মেইন প্রসেসর (FileReferenceExpired ফিক্স সহ) ---

async def movie_process_upload(client, message, uid, temp_name):
    convo = main_mod.user_conversations.get(uid)
    if not convo: return
    
    convo["pending_uploads"] = convo.get("pending_uploads", 0) + 1
    status_msg = await message.reply_text(f"⏳ **ফাইল প্রসেসিং শুরু হচ্ছে...**\n📦 {temp_name}", quote=True)
    
    # ওয়ার্কার বা মেইন ক্লায়েন্ট সিলেক্ট করা
    uploader = main_mod.worker_client if (main_mod.worker_client and main_mod.worker_client.is_connected) else client
    
    try:
        async with main_mod.upload_semaphore:
            # ১. প্রথমে টেলিগ্রাম চ্যানেলে কপি করে রাখা (যাতে এটা অন্তত মিস না হয়)
            copied_msg = await message.copy(chat_id=main_mod.DB_CHANNEL_ID)
            bot_username = (await client.get_me()).username
            tg_link = f"https://t.me/{bot_username}?start=get-{copied_msg.id}"
            
            await status_msg.edit_text("🔄 **টেলিগ্রাম থেকে ফাইল রিফ্রেশ করা হচ্ছে...**")
            
            # 🔥 ফাইল এক্সপায়ার সমস্যা সমাধান: মেসেজটি আবার নতুন করে ফেচ করা
            try:
                fresh_message = await client.get_messages(message.chat.id, message.id)
            except Exception:
                fresh_message = message

            # ২. ডাউনলোড শুরু (Fresh Message ব্যবহার করে)
            start_time = time.time()
            last_update =[start_time]
            
            await status_msg.edit_text("⏳ **বট সার্ভারে ডাউনলোড হচ্ছে... (০%)**")
            
            file_path = await uploader.download_media(
                fresh_message, 
                progress=main_mod.down_progress, 
                progress_args=(status_msg, start_time, last_update)
            )

            if not file_path or not os.path.exists(file_path):
                raise Exception("ফাইলটি বট সার্ভারে ডাউনলোড করা সম্ভব হয়নি।")

            await status_msg.edit_text("☁️ **মিরর সার্ভারগুলোতে আপলোড হচ্ছে...**")
            
            # ৩. প্যারালাল আপলোড (Dood, Streamtape, PixelDrain)
            tasks = [
                upload_to_doodstream(file_path),
                upload_to_streamtape(file_path),
                upload_to_pixeldrain(file_path)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # ফাইল ডিলিট করা
            if os.path.exists(file_path): os.remove(file_path)
            
            # ৪. রেজাল্ট সেভ
            convo["links"].append({
                "label": temp_name, 
                "tg_url": tg_link, 
                "dood_url": results[0] if isinstance(results[0], str) else None,
                "stape_url": results[1] if isinstance(results[1], str) else None,
                "pixel_url": results[2] if isinstance(results[2], str) else None,
                "is_grouped": True
            })
            await status_msg.edit_text(f"✅ **সফলভাবে আপলোড হয়েছে!**\n🎞️ {temp_name}")
            
    except FileReferenceExpired:
        await status_msg.edit_text("❌ **টেলিগ্রাম ফাইল রেফারেন্স এক্সপায়ার হয়ে গেছে।** অনুগ্রহ করে ফাইলটি আবার ফরোয়ার্ড করুন।")
    except Exception as e:
        logger.error(f"Upload Error: {e}")
        await status_msg.edit_text(f"❌ **আপলোড এরর:** {str(e)}")
    finally:
        convo["pending_uploads"] = max(0, convo.get("pending_uploads", 0) - 1)

# --- প্লাগইন রেজিস্ট্রেশন ---
async def register(bot):
    main_mod.process_file_upload = movie_process_upload
    print("🚀 [Fix Active] Movie Server Plugin: Fresh Reference Mode Enabled.")
