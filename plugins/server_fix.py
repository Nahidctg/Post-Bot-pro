import os
import time
import math
import asyncio
import logging
import __main__ as main_mod 
from pyrogram.errors import FileReferenceExpired

logger = logging.getLogger(__name__)

# --- সাইজ ফরম্যাট করার ফাংশন (Bytes to MB/GB) ---
def get_readable_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0

# --- সুন্দর প্রসেস বার তৈরির ফাংশন ---
async def fancy_progress(current, total, status_msg, start_time, last_update):
    now = time.time()
    # ৩ সেকেন্ড পরপর আপডেট হবে যাতে টেলিগ্রাম থেকে ফ্লাড ওয়েট না দেয়
    if now - last_update[0] < 3.5 and current != total:
        return
    
    last_update[0] = now
    elapsed_time = now - start_time
    if elapsed_time <= 0: elapsed_time = 1
    
    percentage = current * 100 / total
    speed = current / elapsed_time # bytes per second
    eta = (total - current) / speed if speed > 0 else 0
    
    # ভিজ্যুয়াল বার তৈরি [■■■■■□□□□□]
    completed_steps = int(percentage / 10)
    bar = "■" * completed_steps + "□" * (10 - completed_steps)
    
    progress_text = (
        f"📥 **বট সার্ভারে ডাউনলোড হচ্ছে...**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏁 **প্রগ্রেস:** `{bar}` {percentage:.1f}%\n"
        f"📊 **সাইজ:** `{get_readable_size(current)}` / `{get_readable_size(total)}`\n"
        f"🚀 **স্পিড:** `{get_readable_size(speed)}/s`\n"
        f"⏱️ **বাকি সময়:** `{int(eta)}s`"
    )
    
    try:
        await status_msg.edit_text(progress_text)
    except:
        pass

# --- মিরর আপলোডার ---
async def mirror_uploads(file_path, status_msg):
    await status_msg.edit_text("⚡ **ডাউনলোড শেষ! এখন মিরর সার্ভারে আপলোড হচ্ছে...**")
    tasks = [
        main_mod.upload_to_doodstream(file_path),
        main_mod.upload_to_streamtape(file_path),
        main_mod.upload_to_pixeldrain(file_path),
        main_mod.upload_to_gofile(file_path)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

# --- মেইন ফাংশন (Process File) ---
async def movie_process_upload(client, message, uid, temp_name):
    convo = main_mod.user_conversations.get(uid)
    if not convo: return
    
    convo["pending_uploads"] = convo.get("pending_uploads", 0) + 1
    status_msg = await message.reply_text(f"🎬 **ফাইল রিসিভ হয়েছে:**\n`{temp_name}`\n\n⏳ প্রসেসিং শুরু হচ্ছে...", quote=True)
    
    try:
        async with main_mod.upload_semaphore:
            # ১. টোকেন রিফ্রেশ করার জন্য 'Saved Messages'-এ ফরোয়ার্ড
            try:
                refreshed_msg = await message.forward("me")
            except:
                refreshed_msg = message

            # ২. ডাউনলোড শুরু
            start_time = time.time()
            last_update = [0] # এটি রিফারেন্স হিসেবে লিস্টে রাখা হয়েছে
            
            file_path = await client.download_media(
                refreshed_msg,
                progress=fancy_progress,
                progress_args=(status_msg, start_time, last_update)
            )

            # ফরোয়ার্ড করা মেসেজ ডিলিট
            try: await refreshed_msg.delete()
            except: pass

            if not file_path or not os.path.exists(file_path):
                return await status_msg.edit_text("❌ **ডাউনলোড ফেইল হয়েছে!**")

            # ৩. মিরর আপলোড
            up_results = await mirror_uploads(file_path, status_msg)
            if os.path.exists(file_path): os.remove(file_path)

            # ৪. অরিজিনাল মেসেজ কপি টু ডিবি চ্যানেল (টেলিগ্রাম লিংকের জন্য)
            copied_msg = await message.copy(chat_id=main_mod.DB_CHANNEL_ID)
            bot_username = (await client.get_me()).username
            tg_link = f"https://t.me/{bot_username}?start=get-{copied_msg.id}"

            # ডাটা সেভ করা
            convo["links"].append({
                "label": temp_name, 
                "tg_url": tg_link, 
                "dood_url": up_results[0] if isinstance(up_results[0], str) else None,
                "stape_url": up_results[1] if isinstance(up_results[1], str) else None,
                "pixel_url": up_results[2] if isinstance(up_results[2], str) else None,
                "gofile_url": up_results[3] if isinstance(up_results[3], str) else None,
                "is_grouped": True
            })
            
            await status_msg.edit_text(f"✅ **মুভি আপলোড সাকসেস!**\n📂 `{temp_name}`")

    except Exception as e:
        logger.error(f"Ultimate Error: {e}")
        await status_msg.edit_text(f"❌ **এরর:** {str(e)}")
    finally:
        convo["pending_uploads"] = max(0, convo.get("pending_uploads", 0) - 1)

async def register(bot):
    main_mod.process_file_upload = movie_process_upload
    print("💎 Fancy Progress Bar & Server Fix Active!")
