# plugins/speed_booster.py
import asyncio
import aiohttp
import os
import __main__
import base64
import time
from pyrogram import filters

# --- 🚀 REFINED UPLOAD FUNCTIONS (WITH ERROR HANDLING) ---

async def safe_upload(func, file_path):
    """এটি চেক করবে আপলোড আসলেও হয়েছে কি না"""
    try:
        res = await func(file_path)
        if res and isinstance(res, str) and res.startswith("http"):
            return res
    except: pass
    return None

async def upload_to_streamwish(file_path):
    api_key = await __main__.get_server_api("streamwish")
    if not api_key: return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.streamwish.com/api/upload/server?key={api_key}") as resp:
                data = await resp.json()
                upload_url = data['result']
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                form.add_field('key', api_key)
                async with session.post(upload_url, data=form) as upload_resp:
                    result = await upload_resp.json()
                    return f"https://streamwish.to/e/{result['result'][0]['filecode']}"
    except: return None

async def upload_to_vidhide(file_path):
    api_key = await __main__.get_server_api("vidhide")
    if not api_key: return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://vidhideapi.com/api/upload/server?key={api_key}") as resp:
                data = await resp.json()
                upload_url = data['result']
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                form.add_field('key', api_key)
                async with session.post(upload_url, data=form) as upload_resp:
                    result = await upload_resp.json()
                    return f"https://vidhidepro.com/v/{result['result'][0]['filecode']}"
    except: return None

# --- 🛠️ MONKEY PATCH: PROCESS FILE UPLOAD ---

async def speed_enhanced_upload(client, message, uid, temp_name):
    convo = __main__.user_conversations.get(uid)
    if not convo: return
    convo["pending_uploads"] = convo.get("pending_uploads", 0) + 1
    status_msg = await message.reply_text(f"🚀 **সার্ভার বুস্ট অ্যাক্টিভেটেড!**\n({temp_name})", quote=True)
    uploader = __main__.worker_client if (__main__.worker_client and __main__.worker_client.is_connected) else client
    
    try:
        async with asyncio.Semaphore(3): 
            await status_msg.edit_text(f"⏳ **১/৩: ডাটাবেসে সেভ হচ্ছে...**")
            copied_msg = await message.copy(chat_id=__main__.DB_CHANNEL_ID)
            bot_username = (await client.get_me()).username
            tg_link = f"https://t.me/{bot_username}?start=get-{copied_msg.id}"
            
            start_time, last_update_time = time.time(), [time.time()]
            file_path = await uploader.download_media(message, progress=__main__.down_progress, progress_args=(status_msg, start_time, last_update_time))

            await status_msg.edit_text(f"⚡ **২/৩: ১০+ সার্ভারে আপলোড হচ্ছে...**")
            
            # প্যারালাল আপলোড উইথ সেফটি চেক
            results = await asyncio.gather(
                safe_upload(__main__.upload_to_gofile, file_path),
                safe_upload(__main__.upload_to_fileditch, file_path),
                safe_upload(__main__.upload_to_tmpfiles, file_path),
                safe_upload(__main__.upload_to_pixeldrain, file_path),
                safe_upload(__main__.upload_to_doodstream, file_path),
                safe_upload(__main__.upload_to_streamtape, file_path),
                safe_upload(__main__.upload_to_filemoon, file_path),
                safe_upload(__main__.upload_to_mixdrop, file_path),
                safe_upload(upload_to_streamwish, file_path),
                safe_upload(upload_to_vidhide, file_path)
            )

            if os.path.exists(file_path): os.remove(file_path)
            
            # ডেটা সেভ
            convo["links"].append({
                "label": temp_name, "tg_url": tg_link, 
                "gofile_url": results[0], "fileditch_url": results[1],
                "tmpfiles_url": results[2], "pixel_url": results[3],
                "dood_url": results[4], "stape_url": results[5],
                "filemoon_url": results[6], "mixdrop_url": results[7],
                "wish_url": results[8], "hide_url": results[9],
                "is_grouped": True
            })
            
            # সাকসেস রিপোর্ট জেনারেট করা
            success_count = sum(1 for r in results if r)
            report = f"✅ **আপলোড সম্পন্ন:** {temp_name}\n📊 **সাকসেস:** {success_count}/10 সার্ভার\n\n"
            if not results[0]: report += "❌ GoFile Failed\n"
            if not results[3]: report += "❌ PixelDrain Failed\n"
            
            await status_msg.edit_text(report)
            
    except Exception as e:
        await status_msg.edit_text(f"❌ আপলোড ফেইলড: {e}")
    finally:
        convo["pending_uploads"] = max(0, convo.get("pending_uploads", 0) - 1)

__main__.process_file_upload = speed_enhanced_upload

# --- 🛠️ HTML UI FIX: SHOW ONLY WORKING LINKS ---

def fixed_html_generator(data, links, user_ads, owner_ads, share):
    import __main__ as m
    # অরিজিনাল জেনারেটর কল করা
    html = m.original_generate_html(data, links, user_ads, owner_ads, share)
    
    for link in links:
        if link.get("is_grouped"):
            new_btns = ""
            # StreamWish & VidHide বাটন যোগ করা
            if link.get('wish_url'):
                b64 = base64.b64encode(link['wish_url'].encode()).decode()
                new_btns += f'<button class="final-server-btn stream-btn" onclick="goToLink(\'{b64}\')" style="background:#E91E63;">🎬 StreamWish HD</button>'
            if link.get('hide_url'):
                b64 = base64.b64encode(link['hide_url'].encode()).decode()
                new_btns += f'<button class="final-server-btn stream-btn" onclick="goToLink(\'{b64}\')" style="background:#673AB7;">⚡ VidHide Fast</button>'
            
            if new_btns:
                html = html.replace('</div>\n\n            </div>', f'{new_btns}</div>\n\n            </div>')
    
    # ডিজাইন এনহ্যান্সমেন্ট
    speed_css = """
    <style>
    .badge-fast { background:#00e676; color:#000; font-size:10px; padding:2px 6px; border-radius:4px; margin-left:5px; font-weight:bold; }
    .badge-high { background:#00bcd4; color:#fff; font-size:10px; padding:2px 6px; border-radius:4px; margin-left:5px; font-weight:bold; }
    </style>
    """
    html = html.replace("▶️ GoFile Fast", '▶️ GoFile <span class="badge-fast">ULTRA FAST</span>')
    html = html.replace("☁️ Direct Cloud", '☁️ Direct Cloud <span class="badge-high">HIGH SPEED</span>')
    
    return speed_css + html

# মেইন জেনারেটর রিপ্লেস (সেফটি সহ)
if hasattr(__main__, 'enhanced_html_code'):
    original_pro_gen = __main__.enhanced_html_code
    def super_gen(*args, **kwargs):
        return fixed_html_generator(args[0], args[1], args[2], args[3], args[4])
    __main__.generate_html_code = super_gen
else:
    __main__.generate_html_code = fixed_html_generator

async def register(bot):
    print("🚀 Speed Booster Master Fix: Applied Successfully!")

print("✅ Speed Booster Plugin Master Fix Loaded!")
