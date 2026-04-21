import os
import time
import asyncio
import logging
import aiohttp
import __main__ as main_mod 
from pyrogram.errors import FileReferenceExpired, FloodWait

logger = logging.getLogger(__name__)

# --- সাইজ ফরম্যাট (MB/GB) ---
def get_readable_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0: return f"{bytes:.2f} {unit}"
        bytes /= 1024.0

# --- সুন্দর ভিজ্যুয়াল বার [■■■□□] ---
def make_progress_bar(percentage):
    completed = int(percentage / 10)
    return "■" * completed + "□" * (10 - completed)

# --- ডাউনলোড প্রসেস বার (TG to Bot) ---
async def fancy_progress(current, total, status_msg, start_time, last_update):
    now = time.time()
    # ৬ সেকেন্ড পরপর আপডেট হবে যাতে কানেকশন ড্রপ না করে (সেফটি)
    if now - last_update[0] < 6.0 and current != total: return
    last_update[0] = now
    elapsed = max(now - start_time, 1)
    percentage = current * 100 / total
    speed = current / elapsed
    
    txt = (f"📥 **বট সার্ভারে ডাউনলোড হচ্ছে...**\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"🏁 `{make_progress_bar(percentage)}` {percentage:.1f}%\n"
           f"📊 সাইজ: `{get_readable_size(current)}` / `{get_readable_size(total)}`\n"
           f"🚀 স্পিড: `{get_readable_size(speed)}/s`\n"
           f"⏱️ বাকি: `{int((total - current) / speed) if speed > 0 else 0}s`")
    try: await status_msg.edit_text(txt)
    except: pass

# --- GoFile API ফিক্সড আপলোডার ---
async def fixed_gofile_upload(file_path):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.gofile.io/servers", timeout=10) as resp:
                data = await resp.json()
                server = data['data']['servers'][0]['name']
            
            url = f"https://{server}.gofile.io/contents/uploadfile"
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form, timeout=None) as upload_resp:
                    res = await upload_resp.json()
                    return res['data']['downloadPage'] if res['status'] == 'ok' else None
    except: return None

# --- আপলোড প্রসেস ট্র্যাকার ম্যানেজার ---
upload_status = {}

async def live_upload_ui(status_msg, temp_name):
    """এটি আপলোড চলাকালীন লাইভ স্ট্যাটাস আপডেট করবে"""
    last_edit = 0
    while True:
        now = time.time()
        if now - last_edit > 7.5: # ৭.৫ সেকেন্ড গ্যাপ (কানেকশন সেফটি)
            msg_txt = f"🎬 **ফাইল:** `{temp_name[:25]}...`\n\n☁️ **সার্ভার আপলোড স্ট্যাটাস:**\n━━━━━━━━━━━━━━━━━━━━\n"
            all_done = True
            for server, data in upload_status.items():
                msg_txt += f"🔘 **{server}:** `{data['status']}`\n"
                if data['status'] == "running": all_done = False
            
            try: await status_msg.edit_text(msg_txt)
            except: pass
            last_edit = now
            if all_done: break
        await asyncio.sleep(2)

# --- ইনডিভিজুয়াল সার্ভার আপলোড লজিক ---
async def run_upload(server_name, func, file_path):
    upload_status[server_name] = {'status': 'running'}
    try:
        res = await func(file_path)
        if res:
            upload_status[server_name]['status'] = '✅ Success'
            return res
        else:
            upload_status[server_name]['status'] = '❌ Failed'
            return None
    except:
        upload_status[server_name]['status'] = '❌ Error'
        return None

# --- মূল মুভি প্রসেসিং ইঞ্জিন ---
async def movie_process_upload(client, message, uid, temp_name):
    convo = main_mod.user_conversations.get(uid)
    if not convo: return
    
    convo["pending_uploads"] = convo.get("pending_uploads", 0) + 1
    status_msg = await message.reply_text(f"⏳ **কানেক্টিং:** `{temp_name}`", quote=True)
    
    try:
        async with main_mod.upload_semaphore:
            # ১. ফাইল রেফারেন্স রিফ্রেশ (Saved Message Forward Trick)
            try: refreshed_msg = await message.forward("me")
            except: refreshed_msg = message

            # ২. ডাউনলোড শুরু
            start_t = time.time()
            f_path = await client.download_media(
                refreshed_msg, 
                progress=fancy_progress, 
                progress_args=(status_msg, start_t, [0])
            )
            
            try: await refreshed_msg.delete()
            except: pass

            if not f_path or not os.path.exists(f_path):
                return await status_msg.edit_text("❌ **ডাউনলোড ফেইল!** টেলিগ্রাম কানেকশন দিচ্ছে না।")

            # ৩. লাইভ আপলোড ট্র্যাকিং শুরু
            global upload_status
            upload_status = {}
            ui_task = asyncio.create_task(live_upload_ui(status_msg, temp_name))
            
            # ৪টি সার্ভারে প্যারালাল আপলোড
            up_tasks = [
                run_upload("DoodStream", main_mod.upload_to_doodstream, f_path),
                run_upload("Streamtape", main_mod.upload_to_streamtape, f_path),
                run_upload("PixelDrain", main_mod.upload_to_pixeldrain, f_path),
                run_upload("GoFile", fixed_gofile_upload, f_path)
            ]
            
            results = await asyncio.gather(*up_tasks, return_exceptions=True)
            await ui_task # UI শেষ হওয়া পর্যন্ত অপেক্ষা

            if os.path.exists(f_path): os.remove(f_path)

            # ৪. রেজাল্ট সেভ ও ফিনিশিং
            copied = await message.copy(chat_id=main_mod.DB_CHANNEL_ID)
            tg_link = f"https://t.me/{(await client.get_me()).username}?start=get-{copied.id}"
            
            convo["links"].append({
                "label": temp_name, "tg_url": tg_link, 
                "dood_url": results[0] if isinstance(results[0], str) else None,
                "stape_url": results[1] if isinstance(results[1], str) else None,
                "pixel_url": results[2] if isinstance(results[2], str) else None,
                "gofile_url": results[3] if isinstance(results[3], str) else None,
                "is_grouped": True
            })
            
            # সাকসেস রিপোর্ট
            server_list = [s for s, r in zip(["Dood", "Stape", "Pixel", "GoFile"], results) if isinstance(r, str)]
            await status_msg.edit_text(f"✅ **মুভি আপলোড সফল!**\n📂 `{temp_name}`\n🚀 সার্ভার: {', '.join(server_list) if server_list else 'Only Telegram'}")

    except Exception as e:
        logger.error(f"Ultimate Final Error: {e}")
        await status_msg.edit_text(f"❌ **এরর:** {str(e)}")
    finally:
        convo["pending_uploads"] = max(0, convo.get("pending_uploads", 0) - 1)

# প্লাগইন রেজিস্টার
async def register(bot):
    main_mod.process_file_upload = movie_process_upload
    main_mod.upload_to_gofile = fixed_gofile_upload
    print("💎 FINAL MOVIE ENGINE: All systems stable and optimized.")
