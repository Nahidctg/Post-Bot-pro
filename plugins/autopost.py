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

def is_valid_url(url):
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return all([parsed.scheme, parsed.netloc])

def extract_info_from_blog(content):
    """HTML কন্টেন্ট থেকে মুভির তথ্য বের করা"""
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

async def register(bot):
    print("🎬 Smart Repost System: Fully Activated!")

    @bot.on_message(filters.command("repost") & filters.private)
    async def smart_repost(client, message):
        status_msg = None
        try:
            # ইনপুট চেক
            parts = message.text.split()
            if len(parts) < 2:
                return await message.reply_text("⚠️ **ব্যবহার নিয়ম:** `/repost https://yourlink.com`")
            
            input_link = parts[1].strip()
            if not is_valid_url(input_link):
                return await message.reply_text("❌ লিঙ্কটি সঠিক নয়! অবশ্যই `https://` সহ দিন।")

            status_msg = await message.reply_text("🔍 আপনার ডাটাবেস চেক করা হচ্ছে...")

            # ডোমেইন বের করা (যেমন: adultmovieserieshd.blogspot.com)
            domain = urlparse(input_link).netloc
            
            # ইউজারের সব সেটআপ খোঁজা
            configs = await user_setup_col.find({"user_id": message.from_user.id}).to_list(None)
            
            if not configs:
                return await status_msg.edit("❌ আপনার কোনো চ্যানেল সেটআপ পাওয়া যায়নি। প্রথমে `/setup` করুন।")

            # ডোমেইন ম্যাচিং করা (লিংকের ডোমেইন কি ফিড ইউআরএল এর মধ্যে আছে?)
            target_configs = [cfg for cfg in configs if domain in cfg.get("feed", "")]

            if not target_configs:
                return await status_msg.edit(f"❌ ডোমেইন `{domain}` এর জন্য কোনো ম্যাচিং চ্যানেল পাওয়া যায়নি। আপনার `/myconfig` চেক করুন।")

            await status_msg.edit(f"🌐 `{domain}` সাইটটি পাওয়া গেছে!\nতথ্য সংগ্রহ করা হচ্ছে...")

            # ওয়েবসাইট থেকে তথ্য স্ক্র্যাপ করা
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(input_link, timeout=20) as resp:
                    if resp.status != 200:
                        return await status_msg.edit(f"❌ ওয়েবসাইট থেকে তথ্য নেওয়া সম্ভব হয়নি। এরর কোড: {resp.status}")
                    
                    html = await resp.text()
                    
                    # টাইটেল এবং পোস্টার খোজা
                    title_match = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
                    full_title = title_match.group(1).split('|')[0].split('-')[0].strip() if title_match else "Movie Update"
                    
                    blog_info = extract_info_from_blog(html)
                    img_match = re.search(r'<img.*?src="(.*?)"', html)
                    poster = img_match.group(1) if img_match else None
                    
                    caption = (
                        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
                        f"🎬 **NEW UPDATE: {full_title}**\n"
                        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
                        f"⭐️ **Rating:** {blog_info['rating']}\n"
                        f"🎭 **Genres:** {blog_info['genres']}\n"
                        f"📅 **Year:** {blog_info['year']}\n"
                        f"⏱ **Runtime:** {blog_info['runtime']}\n"
                        f"🗣 **Language:** {blog_info['lang']}\n"
                        f"💎 **Quality:** 480p | 720p | 1080p\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📥 **ডাউনলোড করতে নিচের লিংকে ক্লিক করুন 👇**"
                    )

                    success_count = 0
                    for cfg in target_configs:
                        target_chat = cfg.get("channel")
                        tutorial = cfg.get("tutorial")

                        btns = [[InlineKeyboardButton("🔗 Watch & Download Now", url=input_link)]]
                        if is_valid_url(tutorial):
                            btns.append([InlineKeyboardButton("📽️ How to Download (Video)", url=tutorial)])

                        try:
                            if poster:
                                await bot.send_photo(target_chat, poster, caption=caption, reply_markup=InlineKeyboardMarkup(btns))
                            else:
                                await bot.send_message(target_chat, caption, reply_markup=InlineKeyboardMarkup(btns))
                            success_count += 1
                        except Exception as e:
                            print(f"Post Error to {target_chat}: {e}")

                    await status_msg.edit(f"✅ সফলভাবে **{success_count}** টি চ্যানেলে রিপোস্ট করা হয়েছে!")

        except Exception as e:
            if status_msg:
                await status_msg.edit(f"❌ একটি সমস্যা হয়েছে: {str(e)}")
            else:
                await message.reply_text(f"❌ একটি সমস্যা হয়েছে: {str(e)}")

    # --- Setup & Config Commands ---
    @bot.on_message(filters.command("setup") & filters.private)
    async def setup_handler(client, message):
        try:
            parts = message.text.split(None, 3)
            if len(parts) < 4:
                return await message.reply_text("⚠️ **Format:** `/setup @channel feed_url tutorial_url`")
            
            channel, feed, tutorial = parts[1], parts[2], parts[3]
            await user_setup_col.update_one(
                {"user_id": message.from_user.id, "channel": channel}, 
                {"$set": {"feed": feed, "tutorial": tutorial, "last_post_id": None}},
                upsert=True
            )
            await message.reply_text(f"✅ **{channel}** এর জন্য সেটআপ সম্পন্ন হয়েছে।")
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}")

    @bot.on_message(filters.command("myconfig") & filters.private)
    async def check_config(client, message):
        configs = await user_setup_col.find({"user_id": message.from_user.id}).to_list(None)
        if not configs: return await message.reply_text("❌ কোনো কনফিগ পাওয়া যায়নি।")
        msg = "⚙️ **আপনার কনফিগ লিস্ট:**\n\n"
        for i, cfg in enumerate(configs, 1):
            msg += f"{i}. 📢 `{cfg['channel']}`\n🌐 {cfg['feed']}\n\n"
        await message.reply_text(msg)

    # --- অটো পোস্ট মনিটর (Background Task) ---
    async def monitor_feeds():
        while True:
            try:
                configs = await user_setup_col.find({}).to_list(None)
                async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
                    for config in configs:
                        try:
                            f_url = config.get("feed")
                            l_id = config.get("last_post_id")
                            target_chat = config.get("channel")
                            tutorial = config.get("tutorial")
                            doc_id = config.get("_id")

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
                                    
                                    blog_info = extract_info_from_blog(content)
                                    img_match = re.search(r'<img.*?src="(.*?)"', content)
                                    poster = img_match.group(1) if img_match else None
                                    
                                    caption = f"🎬 **NEW UPDATE: {title}**\n\n⭐️ Rating: {blog_info['rating']}\n🎭 Genres: {blog_info['genres']}\n\n📥 ডাউনলোড করতে নিচের লিংকে ক্লিক করুন 👇"
                                    
                                    btns = [[InlineKeyboardButton("🔗 Watch & Download Now", url=link)]]
                                    if is_valid_url(tutorial):
                                        btns.append([InlineKeyboardButton("📽️ How to Download (Video)", url=tutorial)])

                                    if poster: await bot.send_photo(target_chat, poster, caption=caption, reply_markup=InlineKeyboardMarkup(btns))
                                    else: await bot.send_message(target_chat, caption, reply_markup=InlineKeyboardMarkup(btns))
                                    
                                    await user_setup_col.update_one({"_id": doc_id}, {"$set": {"last_post_id": p_id}})
                        except: continue
            except: pass
            await asyncio.sleep(40)

    asyncio.create_task(monitor_feeds())
