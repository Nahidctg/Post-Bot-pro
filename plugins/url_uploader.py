import os
import time
import asyncio
import aiohttp
import aiofiles
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# মেইন ফাইল থেকে প্রয়োজনীয় ভ্যারিয়েবল ইমপোর্ট করা
# (আপনার মেইন ফাইলের নাম যদি main.py হয় তবে সেভাবে ইমপোর্ট হবে)
try:
    from __main__ import (
        user_conversations, upload_semaphore, DB_CHANNEL_ID, 
        upload_to_gofile, upload_to_fileditch, upload_to_tmpfiles,
        upload_to_pixeldrain, upload_to_doodstream, upload_to_streamtape,
        upload_to_filemoon, upload_to_mixdrop, logger
    )
except ImportError:
    pass

async def download_progress(current, total, status_msg, start_time):
    now = time.time()
    # প্রতি ৩ সেকেন্ড পর পর আপডেট দিবে
    if not hasattr(download_progress, "last_update"):
        download_progress.last_update = 0
    
    if now - download_progress.last_update >= 3.0 or current == total:
        download_progress.last_update = now
        percent = (current / total) * 100 if total > 0 else 0
        speed = current / (now - start_time) if (now - start_time) > 0 else 1
        
        def hbytes(size):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0: return f"{size:.2f} {unit}"
                size /= 1024.0
            return f"{size:.2f} TB"
            
        filled = int(percent / 10)
        bar = "█" * filled + "░" * (10 - filled)
        try:
            await status_msg.edit_text(
                f"🌐 **URL থেকে ডাউনলোড হচ্ছে...**\n\n"
                f"📊 {bar} {percent:.1f}%\n"
                f"💾 {hbytes(current)} / {hbytes(total)}\n"
                f"🚀 স্পিড: {hbytes(speed)}/s"
            )
        except:
            pass

async def download_file_from_url(url, file_path, status_msg):
    start_time = time.time()
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=None) as response:
            if response.status != 200:
                return False
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            async with aiofiles.open(file_path, mode='wb') as f:
                async for chunk in response.content.iter_chunked(1024*1024): # 1MB chunks
                    if chunk:
                        await f.write(chunk)
                        downloaded += len(chunk)
                        await download_progress(downloaded, total_size, status_msg, start_time)
            return True

# এটি মেইন বটের text_handler এর আগে কাজ করবে (group=-1 দেওয়ার কারণে)
@Client.on_message(filters.private & filters.text & filters.incoming, group=-1)
async def url_upload_handler(client, message):
    uid = message.from_user.id
    text = message.text.strip()
    
    # চেক করা হচ্ছে ইউজার মুভি পোস্ট করার "wait_link_url" স্টেজে আছে কি না
    if uid not in user_conversations:
        return
    
    convo = user_conversations[uid]
    if convo.get("state") != "wait_link_url" or not text.startswith("http"):
        return # যদি সাধারণ মেসেজ হয় তবে মেইন হ্যান্ডলারে চলে যাবে

    # যদি ইউজার ডিরেক্ট লিংক দেয়, তবে আমরা তাকে অপশন দিব
    if text.startswith("http"):
        # মেইন হ্যান্ডলারের কাজ থামিয়ে দিবে যাতে এটি ডাবল প্রসেস না হয়
        message.stop_propagation()

        temp_name = convo.get("temp_name", "Remote File")
        status_msg = await message.reply_text("⏳ **লিংকটি যাচাই করা হচ্ছে...**", quote=True)
        
        # ফাইলের নাম নির্ধারণ (লিংকের শেষ অংশ অথবা ইউজারের দেওয়া নাম)
        file_extension = text.split('.')[-1].split('?')[0].split('#')[0]
        if len(file_extension) > 4: file_extension = "mp4" # ডিফল্ট
        local_filename = f"download_{uid}_{int(time.time())}.{file_extension}"
        
        try:
            async with upload_semaphore:
                # ১. ডিরেক্ট লিংক থেকে ডাউনলোড
                success = await download_file_from_url(text, local_filename, status_msg)
                
                if not success:
                    return await status_msg.edit_text("❌ লিংক থেকে ফাইল ডাউনলোড করা সম্ভব হয়নি। ডাইরেক্ট ডাউনলোড লিংক দিন।")

                await status_msg.edit_text("⏳ **ডাউনলোড সফল! এখন সার্ভারে আপলোড হচ্ছে...**")

                # ২. টেলিগ্রাম ডাটাবেসে সেভ (টেলিগ্রাম সার্ভারে আপলোড)
                tg_msg = await client.send_document(
                    chat_id=DB_CHANNEL_ID, 
                    document=local_filename,
                    caption=f"Uploaded via Remote URL\nName: {temp_name}"
                )
                bot_username = (await client.get_me()).username
                tg_link = f"https://t.me/{bot_username}?start=get-{tg_msg.id}"

                # ৩. মাল্টি-সার্ভারে আপলোড (প্যারালাল)
                await status_msg.edit_text("⏳ **মাল্টি-সার্ভার মিরর আপলোড শুরু হয়েছে...**")
                
                results = await asyncio.gather(
                    upload_to_gofile(local_filename), upload_to_fileditch(local_filename), 
                    upload_to_tmpfiles(local_filename), upload_to_pixeldrain(local_filename), 
                    upload_to_doodstream(local_filename), upload_to_streamtape(local_filename),
                    upload_to_filemoon(local_filename), upload_to_mixdrop(local_filename), 
                    return_exceptions=True
                )

                # লোকাল ফাইল ডিলিট করা
                if os.path.exists(local_filename):
                    os.remove(local_filename)

                # ডাটাবেসে লিংকগুলো সেভ করা
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

                if convo.get("post_id"):
                    convo["state"] = "edit_mode"
                    await status_msg.edit_text(
                        f"✅ **{temp_name}** URL থেকে আপলোড সম্পন্ন!\nএখন আপনি চাইলে আরও লিংক দিতে পারেন বা শেষ করতে পারেন।", 
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add Another Link", callback_data=f"add_lnk_edit_{uid}"), InlineKeyboardButton("✅ Finish", callback_data=f"gen_edit_{uid}")]])
                    )
                else:
                    convo["state"] = "ask_links"
                    await status_msg.edit_text(
                        f"✅ **{temp_name}** URL থেকে আপলোড সম্পন্ন!", 
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add Another", callback_data=f"lnk_yes_{uid}"), InlineKeyboardButton("🏁 Finish", callback_data=f"lnk_no_{uid}")]])
                    )

        except Exception as e:
            logger.error(f"URL Upload Error: {e}")
            if os.path.exists(local_filename): os.remove(local_filename)
            await status_msg.edit_text(f"❌ এরর: {str(e)}")
