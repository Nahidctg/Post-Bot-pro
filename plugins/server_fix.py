import os
import aiohttp
import logging
import asyncio
import time
import __main__ as main_mod 
from pyrogram.errors import FileReferenceExpired, FloodWait, RPCError

logger = logging.getLogger(__name__)

# --- মিরর আপলোডার্স (ফিক্সড ডুডস্ট্রিম এরর) ---

async def upload_to_doodstream(file_path):
    api_key = await main_mod.get_server_api("doodstream")
    if not api_key or not os.path.exists(file_path): return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://doodapi.com/api/upload/server?key={api_key}", timeout=20) as resp:
                data = await resp.json()
                if not data or 'result' not in data: 
                    logger.error(f"Dood API Error: {data}")
                    return None
                upload_url = data['result']
            
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                form.add_field('api_key', api_key)
                async with session.post(upload_url, data=form, timeout=None) as upload_resp:
                    result = await upload_resp.json()
                    if result and 'result' in result:
                        return result['result'][0]['protected_embed']
    except Exception as e:
        logger.error(f"DoodStream Logic Error: {e}")
    return None

async def upload_to_streamtape(file_path):
    api_credentials = await main_mod.get_server_api("streamtape")
    if not api_credentials or not os.path.exists(file_path): return None
    try:
        login_id, api_key = api_credentials.split(":")
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.streamtape.com/file/ul?login={login_id}&key={api_key}") as resp:
                data = await resp.json()
                upload_url = data['result']['url']
            
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(upload_url, data=form, timeout=None) as upload_resp:
                    result = await upload_resp.json()
                    return result['result']['url']
    except: return None

# --- ডাউনলোড ইঞ্জিন (ডাবল রিফ্রেশ মেকানিজম) ---

async def movie_process_upload(client, message, uid, temp_name):
    convo = main_mod.user_conversations.get(uid)
    if not convo: return
    
    convo["pending_uploads"] = convo.get("pending_uploads", 0) + 1
    status_msg = await message.reply_text(f"🎬 **প্রসেসিং:** {temp_name}", quote=True)
    
    # মিরর ফাংশন লিস্ট
    mirrors = {
        "DoodStream": upload_to_doodstream,
        "Streamtape": upload_to_streamtape,
        "PixelDrain": main_mod.upload_to_pixeldrain,
        "GoFile": main_mod.upload_to_gofile
    }
    
    try:
        async with main_mod.upload_semaphore:
            # ১. ডাটাবেস কপি
            copied_msg = await message.copy(chat_id=main_mod.DB_CHANNEL_ID)
            tg_link = f"https://t.me/{(await client.get_me()).username}?start=get-{copied_msg.id}"
            
            await status_msg.edit_text("🔄 **ফাইল রিফ্রেশ করা হচ্ছে... (চেষ্টা ১)**")
            
            # ২. ৩বার রিফ্রেশ ট্রাই (Retry logic to beat 400 Expired error)
            file_path = None
            for attempt in range(1, 4):
                try:
                    # মেসেজ একদম নতুন করে ফেচ করা
                    fresh_msg = await client.get_messages(message.chat.id, message.id)
                    
                    # ডাউনলোড করার জন্য ওয়ার্কার বা বট ইউজ করা
                    uploader = main_mod.worker_client if (main_mod.worker_client and main_mod.worker_client.is_connected) else client
                    
                    start_time = time.time()
                    last_update =[start_time]
                    
                    file_path = await uploader.download_media(
                        fresh_msg, 
                        progress=main_mod.down_progress, 
                        progress_args=(status_msg, start_time, last_update)
                    )
                    if file_path: break 
                except FileReferenceExpired:
                    await status_msg.edit_text(f"⚠️ টোকেন এক্সপায়ার (চেষ্টা {attempt}/3)...")
                    await asyncio.sleep(2) # একটু ওয়েট করে আবার ট্রাই
                except Exception as e:
                    logger.error(f"Attempt {attempt} failed: {e}")

            if not file_path or not os.path.exists(file_path):
                raise Exception("টেলিগ্রাম ফাইলটি ডাউনলোড করতে দিচ্ছে না। দয়া করে ফাইলটি আবার ফরোয়ার্ড করুন।")

            await status_msg.edit_text("✅ **ডাউনলোড শেষ! মিরর আপলোড হচ্ছে...**")
            
            # ৩. আপলোড প্রসেস
            results_dict = {}
            for name, func in mirrors.items():
                try:
                    res = await func(file_path)
                    results_dict[name] = res
                except:
                    results_dict[name] = None

            if os.path.exists(file_path): os.remove(file_path)
            
            # ৪. ডাটা সেভ
            convo["links"].append({
                "label": temp_name, 
                "tg_url": tg_link, 
                "dood_url": results_dict.get("DoodStream"),
                "stape_url": results_dict.get("Streamtape"),
                "pixel_url": results_dict.get("PixelDrain"),
                "gofile_url": results_dict.get("GoFile"),
                "is_grouped": True
            })
            
            success_servers = [k for k, v in results_dict.items() if v]
            if not success_servers:
                await status_msg.edit_text(f"⚠️ {temp_name}: শুধু টেলিগ্রাম লিংক সেভ হয়েছে। মিরর আপলোড ফেল।")
            else:
                await status_msg.edit_text(f"✅ **সাকসেস:** {temp_name}\n🚀 সার্ভার: {', '.join(success_servers)}")
            
    except Exception as e:
        logger.error(f"Ultimate Error: {e}")
        await status_msg.edit_text(f"❌ এরর: {str(e)}")
    finally:
        convo["pending_uploads"] = max(0, convo.get("pending_uploads", 0) - 1)

# --- প্লাগইন রেজিস্ট্রেশন ---
async def register(bot):
    main_mod.process_file_upload = movie_process_upload
    print("🛠️ Extreme Robust Fix Applied. Double-check your Channel ID and Worker Session.")
