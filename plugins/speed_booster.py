# plugins/speed_booster.py
import asyncio
import aiohttp
import os
import __main__
import base64
import time
from pyrogram import filters

# --- 🚀 NEW PUBLIC UPLOAD FUNCTIONS ---

async def upload_catbox(file_path):
    try:
        url = "https://catbox.moe/user/api.php"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('reqtype', 'fileupload')
                form.add_field('fileToUpload', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form) as resp:
                    res_text = await resp.text()
                    return res_text.strip() if res_text.startswith("http") else None
    except: return None

async def upload_transfersh(file_path):
    try:
        url = f"https://transfer.sh/{os.path.basename(file_path)}"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                async with session.put(url, data=f) as resp:
                    res_text = await resp.text()
                    return res_text.strip() if res_text.startswith("http") else None
    except: return None

# --- 🛠️ MONKEY PATCH: PROCESS FILE UPLOAD (MERGED SERVERS) ---

async def speed_enhanced_upload(client, message, uid, temp_name):
    convo = __main__.user_conversations.get(uid)
    if not convo: return
    convo["pending_uploads"] = convo.get("pending_uploads", 0) + 1
    status_msg = await message.reply_text(f"🚀 **১০টি সার্ভার বুস্ট অ্যাক্টিভেটেড!**\n({temp_name})", quote=True)
    uploader = __main__.worker_client if (__main__.worker_client and __main__.worker_client.is_connected) else client
    
    try:
        async with asyncio.Semaphore(3): 
            await status_msg.edit_text(f"⏳ **১/৩: টেলিগ্রাম থেকে ফাইল ডাউনলোড হচ্ছে...**")
            copied_msg = await message.copy(chat_id=__main__.DB_CHANNEL_ID)
            bot_username = (await client.get_me()).username
            tg_link = f"https://t.me/{bot_username}?start=get-{copied_msg.id}"
            
            start_time, last_update_time = time.time(), [time.time()]
            file_path = await uploader.download_media(message, progress=__main__.down_progress, progress_args=(status_msg, start_time, last_update_time))

            await status_msg.edit_text(f"⚡ **২/৩: ১০টি সার্ভারে (Original + Public) আপলোড হচ্ছে...**")
            
            # আপনার অরিজিনাল সার্ভার + নতুন পাবলিক সার্ভার একসাথে মিশিয়ে দেওয়া হলো
            tasks = [
                __main__.upload_to_gofile(file_path),      # 1. Original
                __main__.upload_to_fileditch(file_path),    # 2. Original
                __main__.upload_to_tmpfiles(file_path),    # 3. Original
                __main__.upload_to_pixeldrain(file_path),   # 4. Original
                __main__.upload_to_doodstream(file_path),   # 5. Original (API)
                __main__.upload_to_streamtape(file_path),   # 6. Original (API)
                __main__.upload_to_filemoon(file_path),     # 7. Original (API)
                __main__.upload_to_mixdrop(file_path),      # 8. Original (API)
                upload_catbox(file_path),                   # 9. New Public
                upload_transfersh(file_path)                # 10. New Public
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            if os.path.exists(file_path): os.remove(file_path)
            
            # ডেটা ফিল্টারিং (সাকসেস লিংকগুলো নেওয়া)
            v = []
            for r in results:
                if isinstance(r, str) and r.startswith("http"):
                    v.append(r)
                else:
                    v.append(None)

            # সব ডেটা লিংকে সেভ করা
            convo["links"].append({
                "label": temp_name, "tg_url": tg_link, 
                "gofile_url": v[0], "fileditch_url": v[1],
                "tmpfiles_url": v[2], "pixel_url": v[3],
                "dood_url": v[4], "stape_url": v[5],
                "filemoon_url": v[6], "mixdrop_url": v[7],
                "catbox_url": v[8], "transfer_url": v[9],
                "is_grouped": True
            })
            
            success_count = sum(1 for r in v if r)
            await status_msg.edit_text(f"✅ **আপলোড সম্পন্ন:** {temp_name}\n📊 **সাকসেস:** {success_count}/10 সার্ভার")
            
    except Exception as e:
        await status_msg.edit_text(f"❌ এরর: {e}")
    finally:
        convo["pending_uploads"] = max(0, convo.get("pending_uploads", 0) - 1)

__main__.process_file_upload = speed_enhanced_upload

# --- 🛠️ HTML UI ENHANCER (MERGED) ---

def ultimate_html_generator(data, links, user_ads, owner_ads, share):
    import __main__ as m
    
    # আপনার অরিজিনাল জেনারেটর কল করা
    try:
        html = m.base_html_func(data, links, user_ads, owner_ads, share)
    except:
        return "❌ HTML জেনারেশনে এরর। বট রিস্টার্ট দিন।"
    
    # নতুন বাটনগুলো আপনার অরিজিনাল বাটনগুলোর সাথে যুক্ত করা
    for link in links:
        if link.get("is_grouped"):
            new_btns = ""
            if link.get('catbox_url'):
                b64 = base64.b64encode(link['catbox_url'].encode()).decode()
                new_btns += f'<button class="final-server-btn cloud-btn" onclick="goToLink(\'{b64}\')" style="background:#4CAF50;">📂 Catbox Fast</button>'
            if link.get('transfer_url'):
                b64 = base64.b64encode(link['transfer_url'].encode()).decode()
                new_btns += f'<button class="final-server-btn cloud-btn" onclick="goToLink(\'{b64}\')" style="background:#2196F3;">🚀 Transfer.sh High-Speed</button>'
            
            if new_btns:
                # আপনার অরিজিনাল বাটনগুলোর ঠিক পাশে নতুনগুলো বসবে
                html = html.replace('</div>\n\n            </div>', f'{new_btns}</div>\n\n            </div>')
    
    speed_css = """<style>.badge-fast{background:#00e676;color:#000;font-size:10px;padding:2px 6px;border-radius:4px;margin-left:5px;font-weight:bold;}.badge-high{background:#00bcd4;color:#fff;font-size:10px;padding:2px 6px;border-radius:4px;margin-left:5px;font-weight:bold;}</style>"""
    html = html.replace("▶️ GoFile Fast", '▶️ GoFile <span class="badge-fast">ULTRA FAST</span>')
    html = html.replace("✈️ Telegram Fast", '✈️ Telegram <span class="badge-high">NO WAIT</span>')
    
    return speed_css + html

# মেইন জেনারেটর রিপ্লেস (ব্যাকআপ সহ)
if not hasattr(__main__, 'base_html_func'):
    __main__.base_html_func = __main__.generate_html_code

__main__.generate_html_code = ultimate_html_generator

async def register(bot):
    print("🚀 Speed Booster (Merged 10 Servers): Ready!")

print("✅ Speed Booster Plugin Loaded Successfully!")
