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

def extract_info_from_blog(content):
    """ব্লগের কন্টেন্ট (HTML) থেকে তথ্য বের করার ফাংশন"""
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
    print("🎬 Smart Multi-Autopost: Link Detector Activated!")

    @bot.on_message(filters.command("myconfig") & filters.private, group=-1)
    async def check_config(client, message):
        configs = await user_setup_col.find({"user_id": message.from_user.id}).to_list(None)
        if configs:
            msg_text = "⚙️ **Your Active Configurations:**\n\n"
            for i, cfg in enumerate(configs, 1):
                msg_text += (f"{i}. 📢 **Channel:** `{cfg.get('channel')}`\n"
                             f"🌐 **Feed:** {cfg.get('feed')}\n"
                             f"🔗 **Tutorial:** {cfg.get('tutorial')}\n\n")
            msg_text += "🗑️ To delete any, use: `/delsetup @channel_username`"
            await message.reply_text(msg_text, disable_web_page_preview=True)
        else:
            await message.reply_text("❌ No config found. Use `/setup` to add one.")

    @bot.on_message(filters.command("setup") & filters.private, group=-1)
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
            await message.reply_text(f"✅ **Setup Successful for {channel}!**")
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}")

    # --- স্মার্ট রিপোস্ট কমান্ড (লিংক ডিটেক্টর সহ) ---
    @bot.on_message(filters.command("repost") & filters.private)
    async def smart_repost(client, message):
        try:
            parts = message.text.split()
            if len(parts) < 2:
                return await message.reply_text("⚠️ **Format:** `/repost https://yourbloglink.com/...`")
            
            input_link = parts[1].strip()
            # ইনপুট লিংকের ডোমেইন বের করা (যেমন: movies.com)
            domain = urlparse(input_link).netloc
            if not domain:
                return await message.reply_text("❌ Invalid URL!")

            # ডাটাবেসে এই ডোমেইন বা ফিড মিল আছে এমন সব কনফিগ খোঁজা
            configs = await user_setup_col.find({"user_id": message.from_user.id}).to_list(None)
            
            target_configs = []
            for cfg in configs:
                if domain in cfg.get("feed"):
                    target_configs.append(cfg)

            if not target_configs:
                return await message.reply_text(f"❌ ডোমেইন `{domain}` এর জন্য কোনো চ্যানেল সেটআপ পাওয়া যায়নি। প্রথমে `/setup` করুন।")

            status_msg = await message.reply_text("🔍 Matching site found! Scraping info...")

            async with aiohttp.ClientSession() as session:
                async with session.get(input_link, timeout=15) as resp:
                    if resp.status != 200:
                        return await status_msg.edit("❌ লিঙ্কটি রিচ করা যাচ্ছে না।")
                    
                    html = await resp.text()
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

                    # ম্যাচ করা সব চ্যানেলে পোস্ট করা
                    for cfg in target_configs:
                        target_chat = cfg.get("channel")
                        tutorial = cfg.get("tutorial")

                        btns = InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔗 Watch & Download Now", url=input_link)],
                            [InlineKeyboardButton("📽️ How to Download (Video)", url=tutorial)]
                        ])

                        try:
                            if poster: await bot.send_photo(target_chat, poster, caption=caption, reply_markup=btns)
                            else: await bot.send_message(target_chat, caption, reply_markup=btns)
                        except Exception as e:
                            print(f"Error sending to {target_chat}: {e}")

                    await status_msg.edit(f"✅ Successfully Reposted to **{len(target_configs)}** channel(s) matching `{domain}`")

        except Exception as e:
            await message.reply_text(f"❌ Error: {str(e)}")

    async def monitor_feeds():
        while True:
            try:
                configs = await user_setup_col.find({}).to_list(None)
                async with aiohttp.ClientSession() as session:
                    for config in configs:
                        try:
                            f_url, l_id = config.get("feed"), config.get("last_post_id")
                            target_chat, tutorial = config.get("channel"), config.get("tutorial")
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
                                    content_node = latest.find('atom:content', ns)
                                    content = content_node.text if content_node is not None else ""
                                    
                                    blog_info = extract_info_from_blog(content)
                                    img_match = re.search(r'<img.*?src="(.*?)"', content)
                                    poster = img_match.group(1) if img_match else None
                                    
                                    caption = (
                                        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
                                        f"🎬 **NEW UPDATE: {title}**\n"
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

                                    btns = InlineKeyboardMarkup([
                                        [InlineKeyboardButton("🔗 Watch & Download Now", url=link)],
                                        [InlineKeyboardButton("📽️ How to Download (Video)", url=tutorial)]
                                    ])

                                    try:
                                        if poster: await bot.send_photo(target_chat, poster, caption=caption, reply_markup=btns)
                                        else: await bot.send_message(target_chat, caption, reply_markup=btns)
                                        await user_setup_col.update_one({"_id": doc_id}, {"$set": {"last_post_id": p_id}})
                                    except Exception as e:
                                        print(f"Error sending to {target_chat}: {e}")
                        except Exception:
                            continue
            except Exception:
                pass
            await asyncio.sleep(30)

    asyncio.create_task(monitor_feeds())
