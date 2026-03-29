import asyncio
import re
import aiohttp
import xml.etree.ElementTree as ET
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
import os

# ডাটাবাস কানেকশন (মেইন ফাইল থেকে অটো কানেক্ট হবে)
MONGO_URL = os.getenv("MONGO_URL")
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["movie_bot_db"]
# প্রতিটি ইউজারের আলাদা সেটিংস সেভ করার কালেকশন
user_setup_col = db["user_autopost_configs"]

async def register(bot: Client):
    
    # --- কমান্ড: /setup @channel feed_url tutorial_link ---
    @bot.on_message(filters.command("setup") & filters.private)
    async def setup_autopost(client, message):
        uid = message.from_user.id
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

            # ডাটাবাসে ইউজারের আইডি অনুযায়ী সেটিংস সেভ করা
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
                f"👤 ইউজার: {message.from_user.first_name}\n"
                f"📢 চ্যানেল: `{channel}`\n"
                f"🌐 ফিড: {feed_url}\n"
                f"🎥 টিউটোরিয়াল: {tutorial}\n\n"
                f"📌 *মনে রাখবেন:* বটকে অবশ্যই আপনার চ্যানেলে **Admin** বানাতে হবে।"
            )
            
        except Exception as e:
            await message.reply_text(f"❌ এরর: {e}")

    # --- অটো মনিটর লুপ (সবার ওয়েবসাইট চেক করবে) ---
    async def monitor_all_feeds():
        while True:
            try:
                # ডাটাবাস থেকে সবার সেটআপ খুঁজে বের করা
                all_configs = await user_setup_col.find({}).to_list(None)
                
                async with aiohttp.ClientSession() as session:
                    for config in all_configs:
                        try:
                            uid = config.get("user_id")
                            feed_url = config.get("feed")
                            channel = config.get("channel")
                            tutorial = config.get("tutorial")
                            last_id = config.get("last_post_id")

                            async with session.get(feed_url, timeout=10) as resp:
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
                                
                                # চেক করুন এটি নতুন পোস্ট কি না
                                if post_id != last_id:
                                    title = latest_entry.find('atom:title', ns).text
                                    link = latest_entry.find('atom:link[@rel="alternate"]', ns).attrib['href']
                                    content = latest_entry.find('atom:content', ns).text
                                    
                                    # ইমেজ (পোস্টার) এক্সট্রাক্ট করা
                                    img_match = re.search(r'<img.*?src="(.*?)"', content)
                                    poster_url = img_match.group(1) if img_match else None
                                    
                                    # ট্যাগ/জনরা
                                    categories = [c.attrib['term'] for c in latest_entry.findall('atom:category', ns)]
                                    genre_str = " | ".join(categories[:3]) if categories else "Movie/Series"

                                    # প্রফেশনাল টেমপ্লেট ডিজাইন
                                    caption = (
                                        f"🎬 **NEW MOVIE UPLOADED!**\n"
                                        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                        f"📝 **Name:** {title}\n"
                                        f"🎭 **Genre:** {genre_str}\n"
                                        f"🗣️ **Audio:** Hindi | English | Bangla\n"
                                        f"🌟 **Quality:** 480p | 720p | 1080p\n\n"
                                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                        f"📥 **Download From Website Below 👇**"
                                    )

                                    btn = InlineKeyboardMarkup([
                                        [InlineKeyboardButton("🔗 Watch & Download Now", url=link)],
                                        [InlineKeyboardButton("📽️ How to Download (Video)", url=tutorial)]
                                    ])

                                    # চ্যানেলে পোস্ট করা
                                    try:
                                        if poster_url:
                                            await bot.send_photo(channel, poster_url, caption=caption, reply_markup=btn)
                                        else:
                                            await bot.send_message(channel, caption, reply_markup=btn)
                                        
                                        # ডাটাবেসে এই ইউজারের জন্য লাস্ট পোস্ট আপডেট করা
                                        await user_setup_col.update_one(
                                            {"user_id": uid}, 
                                            {"$set": {"last_post_id": post_id}}
                                        )
                                        print(f"✅ Posted for User {uid}: {title}")
                                    except Exception as send_err:
                                        print(f"⚠️ Channel Post Error (User {uid}): {send_err}")

                        except Exception as user_err:
                            print(f"⚠️ Feed parsing error for one user: {user_err}")
                            continue

            except Exception as e:
                print(f"⚠️ Global Monitor Error: {e}")

            # প্রতি ৫ মিনিট অন্তর সব ওয়েবসাইট চেক করবে
            await asyncio.sleep(300) 

    # ব্যাকগ্রাউন্ডে মনিটর টাস্কটি চালানো
    asyncio.create_task(monitor_all_feeds())
