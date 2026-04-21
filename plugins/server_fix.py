import os
import aiohttp
import logging
import asyncio
import time
import __main__ as main_mod 
from pyrogram.errors import FileReferenceExpired, FloodWait

logger = logging.getLogger(__name__)

# --- মিরর আপলোডার্স ---

async def upload_to_doodstream(file_path):
    api_key = await main_mod.get_server_api("doodstream")
    if not api_key or not os.path.exists(file_path): return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://doodapi.com/api/upload/server?key={api_key}", timeout=15) as resp:
                data = await resp.json()
                if data.get('msg') != 'OK': return None
                upload_url = data['result']
            
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                form.add_field('api_key', api_key)
                async with session.post(upload_url, data=form, timeout=None) as upload_resp:
                    result = await upload_resp.json()
                    return result['result'][0]['protected_embed']
    except Exception as e:
        logger.error(f"Dood Error: {e}")
        return None

async def upload_to_streamtape(file_path):
    api_credentials = await main_mod.get_server_api("streamtape")
    if not api_credentials or ":" not in api_credentials or not os.path.exists(file_path): return None
    try:
        login_id, api_key = api_credentials.split(":")
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.streamtape.com/file/ul?login={login_id}&key={api_key}", timeout=15) as resp:
                data = await resp.json()
                upload_url = data['result']['url']
            
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(upload_url, data=form, timeout=None) as upload_resp:
                    result = await upload_resp.json()
                    return result['result']['url']
    except Exception as e:
        logger.error(f"Stape Error: {e}")
        return None

async def upload_to_pixeldrain(file_path):
    if not os.path.exists(file_path): return None
    try:
        url = "https://pixeldrain.com/api/file"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form, timeout=None) as resp:
                    result = await resp.json()
                    if result.get('success'):
                        return f"https://pixeldrain.com/u/{result['id']}"
    except: return None

# --- মেইন প্রসেসর (স্মার্ট ডাউনলোড ইঞ্জিন) ---

async def movie_process_upload(client, message, uid, temp_name):
    convo = main_mod.user_conversations.get(uid)
    if not convo: return
    
    convo["pending_uploads"] = convo.get("pending_uploads", 0) + 1
    status_msg = await message.reply_text(f"🚀 **প্রসেসিং শুরু:** {temp_name}", quote=True)
    
    # প্রথমে ওয়ার্কার দিয়ে ট্রাই করবে, না হলে মেইন বট
    uploader = main_mod.worker_client if (main_mod.worker_client and main_mod.worker_client.is_connected) else client
    
    try:
        async with main_mod.upload_semaphore:
            # ১. ডাটাবেস চ্যানেলে কপি
            copied_msg = await message.copy(chat_id=main_mod.DB_CHANNEL_ID)
            tg_link = f"https://t.me/{(await client.get_me()).username}?start=get-{copied_msg.id}"
            
            await status_msg.edit_text("🔄 **টেলিগ্রাম থেকে নতুন টোকেন নেওয়া হচ্ছে...**")
            
            # ২. ফাইল রিফ্রেশ (Fresh Message Fetch)
            # এটিই সেই ৪০০ এরর ফিক্স করার মেইন পয়েন্ট
            try:
                fresh_msg = await client.get_messages(message.chat.id, message.id)
            except:
                fresh_msg = message

            # ৩. ডাউনলোড শুরু
            start_time = time.time()
            last_update =[start_time]
            
            file_path = None
            try:
                file_path = await uploader.download_media(
                    fresh_msg, 
                    progress=main_mod.down_progress, 
                    progress_args=(status_msg, start_time, last_update)
                )
            except FileReferenceExpired:
                # যদি ওয়ার্কার ফেল করে, মেইন বট দিয়ে শেষ চেষ্টা
                await status_msg.edit_text("⚠️ ওয়ার্কার ফেল করেছে, মেইন বট দিয়ে চেষ্টা করছি...")
                file_path = await client.download_media(
                    fresh_msg, 
                    progress=main_mod.down_progress, 
                    progress_args=(status_msg, start_time, last_update)
                )

            if not file_path or not os.path.exists(file_path):
                raise Exception("ডাউনলোড ব্যর্থ হয়েছে! টেলিগ্রাম ফাইলটি রিড করতে দিচ্ছে না।")

            await status_msg.edit_text("✅ **ডাউনলোড সফল! এখন মিরর সাইটে পাঠানো হচ্ছে...**")
            
            # ৪. প্যারালাল আপলোড
            tasks = [
                upload_to_doodstream(file_path),
                upload_to_streamtape(file_path),
                upload_to_pixeldrain(file_path),
                main_mod.upload_to_gofile(file_path)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            if os.path.exists(file_path): os.remove(file_path)
            
            # রেজাল্ট চেক ও সেভ
            dood = results[0] if isinstance(results[0], str) else None
            stape = results[1] if isinstance(results[1], str) else None
            pixel = results[2] if isinstance(results[2], str) else None
            gofile = results[3] if isinstance(results[3], str) else None

            convo["links"].append({
                "label": temp_name, 
                "tg_url": tg_link, 
                "dood_url": dood,
                "stape_url": stape,
                "pixel_url": pixel,
                "gofile_url": gofile,
                "is_grouped": True
            })
            
            if not any([dood, stape, pixel, gofile]):
                await status_msg.edit_text(f"⚠️ {temp_name}: শুধু টেলিগ্রাম লিংক সেভ হয়েছে। মিরর আপলোড ফেইল।")
            else:
                await status_msg.edit_text(f"✅ **সাকসেস:** {temp_name}\n(সার্ভার: {' Dood' if dood else ''}{' Stape' if stape else ''}{' Pixel' if pixel else ''})")
            
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await status_msg.edit_text("❌ FloodWait এরর। একটু পর আবার ট্রাই করুন।")
    except Exception as e:
        logger.error(f"Ultimate Error: {e}")
        await status_msg.edit_text(f"❌ এরর: {str(e)}")
    finally:
        convo["pending_uploads"] = max(0, convo.get("pending_uploads", 0) - 1)

# --- প্লাগইন রেজিস্ট্রেশন ---
async def register(bot):
    main_mod.process_file_upload = movie_process_upload
    print("🛠️ Fixed Server Plugin Activated. Emergency Token Refresher Online.")
