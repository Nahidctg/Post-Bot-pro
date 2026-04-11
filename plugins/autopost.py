import __main__
import asyncio
import re
import aiohttp
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# মেইন ফাইল থেকে ডাটাবেস কালেকশন নেওয়া
db = __main__.db
user_setup_col = db["user_autopost_configs"]

# --- হেল্পার ফাংশনস ---

def is_valid_url(url):
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return all([parsed.scheme, parsed.netloc])

def get_clean_domain(url):
    """লিঙ্ক থেকে ডোমেইন বের করে www. রিমুভ করে দেয়"""
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.replace("www.", "")
    except:
        return ""

def extract_info_from_blog(content):
    if not content:
        return {'rating': 'N/A', 'genres': 'Movie', 'lang': 'Dual Audio', 'runtime': 'N/A', 'year': 'N/A'}
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

# --- মূল প্লাগইন রেজিস্টার ---

async def register(bot):
    print("🎬 Smart Repost V2 (Domain Fix) Activated!")

    @bot.on_message(filters.command("repost") & filters.private, group=-1)
    async def smart_repost(client, message):
        try:
            parts = message.text.split()
            if len(parts) < 2:
                return await message.reply_text("⚠️ **Format:** `/repost লিঙ্ক`")
            
            input_link = parts[1].strip()
            if not is_valid_url(input_link):
                return await message.reply_text("❌ ভুল লিঙ্ক! `https://` সহ দিন।")

            status_msg = await message.reply_text("🔎 ম্যাচিং চ্যানেল খোঁজা হচ্ছে...")
            
            # ইনপুট লিঙ্কের ডোমেইন
            input_domain = get_clean_domain(input_link)
            
            # ডাটাবেস থেকে ইউজারের সব কনফিগ আনা
            configs = await user_setup_col.find({"user_id": message.from_user.id}).to_list(None)
            
            target_configs = []
            for cfg in configs:
                # সেভ করা ফিড লিঙ্কের ডোমেইন
                feed_domain = get_clean_domain(cfg.get("feed", ""))
                # যদি ডোমেইন মিলে যায়
                if input_domain == feed_domain or input_domain in cfg.get("feed", ""):
                    target_configs.append(cfg)

            if not target_configs:
                # কোনো ম্যাচ না পাওয়া গেলে ইউজারকে তার সেভ করা ডোমেইনগুলো দেখাবে (ডিবাগ করার জন্য)
                saved_domains = [get_clean_domain(c.get("feed", "")) for c in configs]
                error_txt = f"❌ কোনো ম্যাচিং চ্যানেল পাওয়া যায়নি!\n\nআপনার ইনপুট ডোমেইন: `{input_domain}`\nআপনার সেভ করা ডোমেইনগুলো: `{saved_domains}`\n\nদয়া করে `/setup` করার সময় ডোমেইন ঠিকভাবে দিন।"
                return await status_msg.edit(error_txt)

            await status_msg.edit(f"✅ ডোমেইন ম্যাচ করেছে!\n🌐 `{input_domain}` থেকে তথ্য সংগ্রহ করা হচ্ছে...")
            
            headers = {"User-Agent": "Mozilla/5.0"}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(input_link, timeout=20) as resp:
                    if resp.status != 200:
                        return await status_msg.edit(f"❌ এরর: ওয়েবসাইট থেকে রেসপন্স নেই ({resp.status})")
                    
                    html = await resp.text()
                    title_match = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
                    title = title_match.group(1).split('|')[0].split('-')[0].strip() if title_match else "Movie Update"
                    info = extract_info_from_blog(html)
                    img_match = re.search(r'<img.*?src="(.*?)"', html)
                    poster = img_match.group(1) if img_match else None
                    
                    caption = get_caption(title, info)
                    success_count = 0
                    
                    for cfg in target_configs:
                        target_chat = cfg.get("channel")
                        tutorial = cfg.get("tutorial")
                        btns = [[InlineKeyboardButton("🔗 Watch & Download Now", url=input_link)]]
                        if is_valid_url(tutorial):
                            btns.append([InlineKeyboardButton("📽️ How to Download", url=tutorial)])

                        try:
                            if poster: await client.send_photo(target_chat, poster, caption=caption, reply_markup=InlineKeyboardMarkup(btns))
                            else: await client.send_message(target_chat, caption, reply_markup=InlineKeyboardMarkup(btns))
                            success_count += 1
                        except Exception as e:
                            print(f"Error sending to {target_chat}: {e}")

                    await status_msg.edit(f"✅ সফলভাবে **{success_count}** টি চ্যানেলে রিপোস্ট করা হয়েছে!")

        except Exception as e:
            await message.reply_text(f"❌ এরর: {str(e)}")

    # --- অন্য কমান্ডগুলো আগের মতোই থাকবে (setup, delsetup, myconfig, monitor_feeds) ---

    @bot.on_message(filters.command("setup") & filters.private, group=-1)
    async def setup_handler(client, message):
        try:
            parts = message.text.split(None, 3)
            if len(parts) < 4: return await message.reply_text("⚠️ `/setup @channel feed tutorial`")
            channel, feed, tutorial = parts[1], parts[2], parts[3]
            await user_setup_col.update_one(
                {"user_id": message.from_user.id, "channel": channel}, 
                {"$set": {"feed": feed, "tutorial": tutorial, "last_post_id": None}},
                upsert=True
            )
            await message.reply_text(f"✅ Setup Successful for {channel}")
        except Exception as e: await message.reply_text(f"❌ Error: {e}")

    @bot.on_message(filters.command("myconfig") & filters.private, group=-1)
    async def config_handler(client, message):
        configs = await user_setup_col.find({"user_id": message.from_user.id}).to_list(None)
        if not configs: return await message.reply_text("❌ No config found.")
        txt = "⚙️ **Your Active Configs:**\n\n"
        for i, cfg in enumerate(configs, 1):
            txt += f"{i}. 📢 `{cfg['channel']}`\n🌐 {cfg['feed']}\n\n"
        await message.reply_text(txt, disable_web_page_preview=True)

    @bot.on_message(filters.command("delsetup") & filters.private, group=-1)
    async def del_handler(client, message):
        try:
            parts = message.text.split()
            if len(parts) < 2: return await message.reply_text("⚠️ `/delsetup @channel`")
            res = await user_setup_col.delete_one({"user_id": message.from_user.id, "channel": parts[1]})
            await message.reply_text("✅ Deleted" if res.deleted_count > 0 else "❌ Not found")
        except Exception as e: await message.reply_text(f"❌ Error: {e}")

    async def monitor_feeds():
        while True:
            try:
                configs = await user_setup_col.find({}).to_list(None)
                headers = {"User-Agent": "Mozilla/5.0"}
                async with aiohttp.ClientSession(headers=headers) as session:
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
                                    btns = [[InlineKeyboardButton("🔗 Watch & Download Now", url=link)]]
                                    if is_valid_url(tutorial): btns.append([InlineKeyboardButton("📽️ How to Download", url=tutorial)])
                                    try:
                                        if poster: await bot.send_photo(target_chat, poster, caption=caption, reply_markup=InlineKeyboardMarkup(btns))
                                        else: await bot.send_message(target_chat, caption, reply_markup=InlineKeyboardMarkup(btns))
                                        await user_setup_col.update_one({"_id": config["_id"]}, {"$set": {"last_post_id": p_id}})
                                    except: pass
                        except: continue
            except: pass
            await asyncio.sleep(45)

    asyncio.create_task(monitor_feeds())
