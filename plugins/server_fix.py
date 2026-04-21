import os
import aiohttp
import logging
import asyncio
import time
import __main__ as main_mod 
from pyrogram.errors import FileReferenceExpired, FloodWait, RPCError

logger = logging.getLogger(__name__)

# --- মিরর আপলোডার্স ---

async def upload_to_doodstream(file_path):
    api_key = await main_mod.get_server_api("doodstream")
    if not api_key or not os.path.exists(file_path): return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://doodapi.com/api/upload/server?key={api_key}", timeout=20) as resp:
                data = await resp.json()
                if not data or 'result' not in data: return None
                upload_url = data['result']
            
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                form.add_field('api_key', api_key)
                async with session.post(upload_url, data=form, timeout=None) as upload_resp:
                    result = await upload_resp.json()
                    if result and 'result' in result:
                        return result['result'][0]['protected_embed']
    except: return None

# --- ডাউনলোড ইঞ্জিন (Forward-to-Self Method) ---

async def movie_process_upload(client, message, uid, temp_name):
    convo = main_mod.user_conversations.get(uid)
    if not convo: return
    
    convo["pending_uploads"] = convo.get("pending_uploads", 0) + 1
    status_msg = await message.reply_text(f"🎬 **প্রসেসিং:** {temp_name}", quote=True)
    
    try:
        async with main_mod.upload_semaphore:
            # ১. ডাটাবেস চ্যানেলে ফাইল কপি (টেলিগ্রাম লিংকের জন্য)
            copied_msg = await message.copy(chat_id=main_mod.DB_CHANNEL_ID)
            tg_link = f"https://t.me/{(await client.get_me()).username}?start=get-{copied_msg.id}"
            
            await status_msg.edit_text("🔄 **টেলিগ্রাম থেকে ফ্রেশ টোকেন নেওয়া হচ্ছে...**")

            # ২. স্পেশাল ফিক্স: ফাইলটি বটের নিজের ইনবক্সে ফরোয়ার্ড করা (Saved Messages)
            # এটি করলে টেলিগ্রাম বাধ্য হয় নতুন 'file_reference' দিতে
            try:
                self_forward = await message.forward("me")
                target_msg = self_forward
            except:
                target_msg = message # ফরোয়ার্ড না হলে অরিজিনাল মেসেজ ট্রাই করবে

            # ৩. ডাউনলোড শুরু
            start_time = time.time()
            last_update =[start_time]
            
            # সরাসরি মেইন বট দিয়ে ডাউনলোড ট্রাই করা (ওয়ার্কার মাঝে মাঝে এরর দেয়)
            await status_msg.edit_text("⏳ **বট সার্ভারে মুভি ডাউনলোড হচ্ছে...**")
            
            file_path = await client.download_media(
                target_msg, 
                progress=main_mod.down_progress, 
                progress_args=(status_msg, start_time, last_update)
            )

            # ফরোয়ার্ড করা মেসেজ ডিলিট করা
            try: await target_msg.delete()
            except: pass

            if not file_path or not os.path.exists(file_path):
                raise Exception("টেলিগ্রাম ফাইলটি রিড করতে দিচ্ছে না। দয়া করে কিছুক্ষণ পর আবার ট্রাই করুন।")

            await status_msg.edit_text("✅ **ডাউনলোড শেষ! এখন মিরর আপলোড হচ্ছে...**")
            
            # ৪. মিরর সাইটে আপলোড (Dood, Streamtape, Gofile)
            tasks = [
                upload_to_doodstream(file_path),
                main_mod.upload_to_streamtape(file_path),
                main_mod.upload_to_pixeldrain(file_path),
                main_mod.upload_to_gofile(file_path)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            if os.path.exists(file_path): os.remove(file_path)
            
            # ডাটা সেভ
            convo["links"].append({
                "label": temp_name, "tg_url": tg_link, 
                "dood_url": results[0] if isinstance(results[0], str) else None,
                "stape_url": results[1] if isinstance(results[1], str) else None,
                "pixel_url": results[2] if isinstance(results[2], str) else None,
                "gofile_url": results[3] if isinstance(results[3], str) else None,
                "is_grouped": True
            })
            await status_msg.edit_text(f"✅ **মুভি আপলোড সফল:** {temp_name}")
            
    except Exception as e:
        logger.error(f"Ultimate Error: {e}")
        await status_msg.edit_text(f"❌ **এরর:** {str(e)}")
    finally:
        convo["pending_uploads"] = max(0, convo.get("pending_uploads", 0) - 1)

async def register(bot):
    main_mod.process_file_upload = movie_process_upload
    print("🛠️ Forward-to-Self Method Active. Autopost Error must be fixed.")
