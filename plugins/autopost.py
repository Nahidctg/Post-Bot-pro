import __main__
import asyncio
import re
import aiohttp
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
from pyrogram import filters, Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# মেইন ফাইল থেকে ডাটাবেস কালেকশন নেওয়া
db = __main__.db
user_setup_col = db["user_autopost_configs"]

def is_valid_url(url):
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return all([parsed.scheme, parsed.netloc])

def extract_info_from_blog(content):
    text = re.sub(r'<[^>]+>', ' ', content)
    info = {}
    rating = re.search(r'RATING:\s*([\d\./]+)', text, re.I)
    genre = re.search(r'GENRE:\s*([^📅🗣⏱]+)', text, re.I)
    lang = re.search(r'LANGUAGE:\s*([^📅🎭⏱]+)', text, re.I)
    runtime = re.search(r'RUNTIME:\s*([\d\s\w]+)', text, re.I)
    year = re.search(r'RELEASE:\s*(\d{4})', text, re.I)
    info['rating'] = rating.group(1).strip() if rating else "N/A"
    info['genres'] = genre.group(1).strip() if genre else "Movie"
    info['lang'] = lang.group(1).strip() if lang else "Dual Audio"
    info['runtime'] = runtime.group(1).strip() if runtime else "N/A"
    info['year'] = year.group(1).strip() if year else "N/A"
    return info

def get_caption(title, info):
    return (
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"🎬 **NEW UPDATE: {title}**\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"⭐️ **Rating:** {info['rating']}\n"
        f"🎭 **Genres:** {info['genres']}\n"
        f"📅 **Year:** {info['year']}\n"
        f"⏱ **Runtime:** {info['runtime']}\n"
        f"🗣 **Language:** {info['lang']}\n"
        f"💎 **Quality:** 480p | 720p | 1080p\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📥 **ডাউনলোড করতে নিচের লিংকে ক্লিক করুন 👇**"
    )

async def register(bot):
    print("🎬 Professional Autopost Plugin: Monitoring Commands...")

    # --- কমান্ড হ্যান্ডলার (Group -1 দেওয়া হয়েছে যাতে সবার আগে এটি রান হয়) ---

    @bot.on_message(filters.command("repost") & filters.private, group=-1)
    async def smart_repost(client, message):
        print(f"DEBUG: Repost command received from {message.from_user.id}")
        message.stop_propagation() # অন্য কোনো হ্যান্ডলার যাতে এটি ডিস্টার্ব না করে
        
        try:
            parts = message.text.split()
            if len(parts) < 2:
                return await message.reply_text("⚠️ **ব্যবহার:** `/repost লিঙ্ক`")
            
            input_link = parts[1].strip()
            status_msg = await message.reply_text("🔍 matching database...")
            
            domain = urlparse(input_link).netloc
            configs = await user_setup_col.find({"user_id": message.from_user.id}).to_list(None)
            
            target_configs = [cfg for cfg in configs if domain in cfg.get("feed", "")]
            if not target_configs:
                return await status_msg.edit(f"❌ `{domain}` এর জন্য কোনো চ্যানেল পাওয়া যায়নি।")

            await status_msg.edit("🌐 Scraping details...")
            headers = {"User-Agent": "Mozilla/5.0"}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(input_link, timeout=20) as resp:
                    if resp.status != 200:
                        return await status_msg.edit(f"❌ এরর: {resp.status}")
                    
                    html = await resp.text()
                    title_match = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
                    title = title_match.group(1).split('|')[0].split('-')[0].strip() if title_match else "Movie Update"
                    info = extract_info_from_blog(html)
                    img_match = re.search(r'<img.*?src="(.*?)"', html)
                    poster = img_match.group(1) if img_match else None
                    
                    caption = get_caption(title, info)
                    for cfg in target_configs:
                        btns = [[InlineKeyboardButton("🔗 Watch & Download Now", url=input_link)]]
                        if is_valid_url(cfg.get("tutorial")):
                            btns.append([InlineKeyboardButton("📽️ How to Download", url=cfg.get("tutorial"))])
                        
                        try:
                            if poster: await client.send_photo(cfg['channel'], poster, caption=caption, reply_markup=InlineKeyboardMarkup(btns))
                            else: await client.send_message(cfg['channel'], caption, reply_markup=InlineKeyboardMarkup(btns))
                        except Exception as e: print(f"Error: {e}")
            await status_msg.edit("✅ সফলভাবে রিপোস্ট করা হয়েছে!")
        except Exception as e:
            await message.reply_text(f"❌ এরর: {e}")

    @bot.on_message(filters.command("setup") & filters.private, group=-1)
    async def setup_handler(client, message):
        print(f"DEBUG: Setup command received")
        message.stop_propagation()
        try:
            parts = message.text.split(None, 3)
            if len(parts) < 4: return await message.reply_text("⚠️ `/setup @channel feed tutorial`")
            channel, feed, tutorial = parts[1], parts[2], parts[3]
            await user_setup_col.update_one(
                {"user_id": message.from_user.id, "channel": channel}, 
                {"$set": {"feed": feed, "tutorial": tutorial, "last_post_id": None}},
                upsert=True
            )
            await message.reply_text(f"✅ Setup Done for {channel}")
        except Exception as e: await message.reply_text(f"Error: {e}")

    @bot.on_message(filters.command("myconfig") & filters.private, group=-1)
    async def config_handler(client, message):
        print(f"DEBUG: Myconfig command received")
        message.stop_propagation()
        configs = await user_setup_col.find({"user_id": message.from_user.id}).to_list(None)
        if not configs: return await message.reply_text("❌ No config.")
        txt = "⚙️ **Configs:**\n\n"
        for cfg in configs: txt += f"📢 `{cfg['channel']}`\n🌐 {cfg['feed']}\n\n"
        await message.reply_text(txt)

    @bot.on_message(filters.command("delsetup") & filters.private, group=-1)
    async def del_handler(client, message):
        print(f"DEBUG: Delsetup command received")
        message.stop_propagation()
        try:
            parts = message.text.split()
            if len(parts) < 2: return await message.reply_text("⚠️ `/delsetup @channel`")
            res = await user_setup_col.delete_one({"user_id": message.from_user.id, "channel": parts[1]})
            await message.reply_text("✅ Deleted" if res.deleted_count > 0 else "❌ Not found")
        except Exception as e: await message.reply_text(f"Error: {e}")

    # --- অটো পোস্ট মনিটর ---
    async def monitor_feeds():
        while True:
            try:
                configs = await user_setup_col.find({}).to_list(None)
                async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
                    for config in configs:
                        try:
                            f_url, l_id = config.get("feed"), config.get("last_post_id")
                            target_chat, tutorial = config.get("channel"), config.get("tutorial")
                            async with session.get(f_url, timeout=15) as resp:
                                if resp.status != 200: continue
                                xml_data = await resp.text()
                                root = ET.fromstring(xml_data)
                                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                                entries = root.findall('atom:entry', ns)
                                if not entries: continue
                                latest = entries[0]
                                p_id = latest.find('atom:id', ns).text
                                if p_id != l_id:
                                    title = latest.find('atom:title', ns).text
                                    link = latest.find('atom:link[@rel="alternate"]', ns).attrib['href']
                                    content = latest.find('atom:content', ns).text or ""
                                    info = extract_info_from_blog(content)
                                    img_match = re.search(r'<img.*?src="(.*?)"', content)
                                    poster = img_match.group(1) if img_match else None
                                    caption = get_caption(title, info)
                                    btns = [[InlineKeyboardButton("🔗 Watch & Download", url=link)]]
                                    if is_valid_url(tutorial): btns.append([InlineKeyboardButton("📽️ How to Download", url=tutorial)])
                                    if poster: await bot.send_photo(target_chat, poster, caption=caption, reply_markup=InlineKeyboardMarkup(btns))
                                    else: await bot.send_message(target_chat, caption, reply_markup=InlineKeyboardMarkup(btns))
                                    await user_setup_col.update_one({"_id": config["_id"]}, {"$set": {"last_post_id": p_id}})
                        except: continue
            except: pass
            await asyncio.sleep(40)

    asyncio.create_task(monitor_feeds())
