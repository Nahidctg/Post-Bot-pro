import asyncio
import re
import aiohttp
import xml.etree.ElementTree as ET
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
import os

# ডাটাবাস কানেকশন
MONGO_URL = os.getenv("mongodb+srv://Filetolink270:Filetolink270@cluster0.tsr3api.mongodb.net/?appName=Cluster0")
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["movie_bot_db"]
user_setup_col = db["user_autopost_configs"]

# এই ফাংশনটি মেইন ফাইল থেকে কল হবে
async def register(bot: Client):
    print("🔌 Autopost Plugin Registered!") # এটি টার্মিনালে দেখা যাবে

    # --- কমান্ড: /setup ---
    @bot.on_message(filters.command("setup"))
    async def setup_autopost(client, message):
        print(f"📩 Setup command received from {message.from_user.id}") # লগ চেক
        
        try:
            parts = message.text.split(None, 3)
            if len(parts) < 4:
                return await message.reply_text(
                    "❌ **ভুল ফরম্যাট!**\n\nসঠিক নিয়ম:\n"
                    "`/setup @CineZoneBD1 https://yourblog.com/feeds/posts/default https://t.me/tutorial`"
                )
            
            channel = parts[1]
            feed_url = parts[2]
            tutorial = parts[3]
            uid = message.from_user.id

            # ডাটাবেসে সেভ করা
            await user_setup_col.update_one(
                {"user_id": uid},
                {"$set": {
                    "channel": channel,
                    "feed": feed_url,
                    "tutorial": tutorial,
                    "last_post_id": None
                }},
                upsert=True
            )
            
            await message.reply_text(
                f"✅ **সেটআপ সফল!**\n\n"
                f"📢 চ্যানেল: `{channel}`\n"
                f"🌐 ফিড: {feed_url}\n"
                f"🎥 টিউটোরিয়াল: {tutorial}\n\n"
                f"📌 *মনে রাখবেন:* বটকে অবশ্যই আপনার চ্যানেলে **Admin** বানাতে হবে।"
            )
            
        except Exception as e:
            print(f"❌ Setup Error: {e}")
            await message.reply_text(f"❌ এরর হয়েছে: {e}")

    # --- অটো মনিটর লুপ ---
    async def monitor_all_feeds():
        print("🚀 Autopost Monitor Task Started...")
        while True:
            try:
                all_configs = await user_setup_col.find({}).to_list(None)
                
                async with aiohttp.ClientSession() as session:
                    for config in all_configs:
                        try:
                            uid = config.get("user_id")
                            feed_url = config.get("feed")
                            channel = config.get("channel")
                            tutorial = config.get("tutorial")
                            last_id = config.get("last_post_id")

                            async with session.get(feed_url, timeout=15) as resp:
                                if resp.status != 200:
                                    continue
                                
                                xml_data = await resp.text()
                                root = ET.fromstring(xml_data)
                                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                                entries = root.findall('atom:entry', ns)

                                if not entries:
                                    continue

                                latest_entry = entries[0]
                                post_id = latest_entry.find('atom:id', ns).text
                                
                                if post_id != last_id:
                                    title = latest_entry.find('atom:title', ns).text
                                    link = latest_entry.find('atom:link[@rel="alternate"]', ns).attrib['href']
                                    content = latest_entry.find('atom:content', ns).text
                                    
                                    img_match = re.search(r'<img.*?src="(.*?)"', content)
                                    poster_url = img_match.group(1) if img_match else None
                                    
                                    categories = [c.attrib['term'] for c in latest_entry.findall('atom:category', ns)]
                                    genre_str = " | ".join(categories[:3]) if categories else "Movie/Series"

                                    caption = (
                                        f"🎬 **NEW MOVIE UPLOADED!**\n"
                                        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                        f"📝 **Name:** {title}\n"
                                        f"🎭 **Genre:** {genre_str}\n"
                                        f"🗣️ **Audio:** Dual Audio\n"
                                        f"🌟 **Quality:** 480p | 720p | 1080p\n\n"
                                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                        f"📥 **Download From Website Below 👇**"
                                    )

                                    btn = InlineKeyboardMarkup([
                                        [InlineKeyboardButton("🔗 Watch & Download Now", url=link)],
                                        [InlineKeyboardButton("📽️ How to Download (Video)", url=tutorial)]
                                    ])

                                    try:
                                        if poster_url:
                                            await bot.send_photo(channel, poster_url, caption=caption, reply_markup=btn)
                                        else:
                                            await bot.send_message(channel, caption, reply_markup=btn)
                                        
                                        await user_setup_col.update_one(
                                            {"user_id": uid}, 
                                            {"$set": {"last_post_id": post_id}}
                                        )
                                    except Exception as send_err:
                                        print(f"⚠️ Send Error User {uid}: {send_err}")

                        except Exception as user_err:
                            continue

            except Exception as e:
                print(f"⚠️ Global Monitor Error: {e}")

            await asyncio.sleep(300) 

    asyncio.create_task(monitor_all_feeds())
