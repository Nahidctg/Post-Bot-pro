import __main__
import asyncio
import re
import aiohttp
import xml.etree.ElementTree as ET
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# মেইন ফাইল থেকে ডাটাবেস কালেকশন নেওয়া
db = __main__.db
user_setup_col = db["user_autopost_configs"]

def extract_info_from_blog(content):
    """ব্লগের কন্টেন্ট (HTML) থেকে তথ্য বের করার ফাংশন"""
    # HTML ট্যাগগুলো পরিষ্কার করে শুধু টেক্সট নেওয়া
    text = re.sub(r'<[^>]+>', ' ', content)
    
    info = {}
    # আপনার ওয়েবসাইটের ফরম্যাট অনুযায়ী Regex (রেগুলার এক্সপ্রেশন)
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
    print("🎬 Professional Autopost: Blog Scraper UI Activated!")

    @bot.on_message(filters.command("myconfig") & filters.private, group=-1)
    async def check_config(client, message):
        config = await user_setup_col.find_one({"user_id": message.from_user.id})
        if config:
            await message.reply_text(f"⚙️ **Your Config:**\n\n📢 Channel: `{config.get('channel')}`\n🌐 Feed: {config.get('feed')}")
        else:
            await message.reply_text("❌ No config found.")

    @bot.on_message(filters.command("setup") & filters.private, group=-1)
    async def setup_handler(client, message):
        try:
            parts = message.text.split(None, 3)
            if len(parts) < 4:
                return await message.reply_text("⚠️ **Format:** `/setup @channel feed_url tutorial_url`")
            channel, feed, tutorial = parts[1], parts[2], parts[3]
            await user_setup_col.update_one(
                {"user_id": message.from_user.id},
                {"$set": {"channel": channel, "feed": feed, "tutorial": tutorial, "last_post_id": None}},
                upsert=True
            )
            await message.reply_text("✅ **Setup Successful!** Now bot will extract info from your blog posts.")
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}")

    async def monitor_feeds():
        while True:
            try:
                configs = await user_setup_col.find({}).to_list(None)
                async with aiohttp.ClientSession() as session:
                    for config in configs:
                        try:
                            f_url, l_id = config.get("feed"), config.get("last_post_id")
                            target_chat, tutorial, uid = config.get("channel"), config.get("tutorial"), config.get("user_id")

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
                                    content = latest.find('atom:content', ns).text
                                    
                                    # ব্লগের কন্টেন্ট থেকে তথ্য নেওয়া
                                    blog_info = extract_info_from_blog(content)
                                    img_match = re.search(r'<img.*?src="(.*?)"', content)
                                    poster = img_match.group(1) if img_match else None
                                    
                                    # প্রিমিয়াম বক্স টেমপ্লেট (আপনার ব্লগের তথ্য দিয়ে সাজানো)
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

                                    if poster: await bot.send_photo(target_chat, poster, caption=caption, reply_markup=btns)
                                    else: await bot.send_message(target_chat, caption, reply_markup=btns)
                                    
                                    await user_setup_col.update_one({"user_id": uid}, {"$set": {"last_post_id": p_id}})
                        except: continue
            except: pass
            await asyncio.sleep(10)

    asyncio.create_task(monitor_feeds())
