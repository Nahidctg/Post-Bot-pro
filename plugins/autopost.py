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

# --- 🚀 AUTO-POST MONITOR PLUGIN ---
async def register(bot):
    print("🎬 Auto-Post Monitor Plugin Registered Successfully!")

    # ১. সেটআপ কমান্ড হ্যান্ডলার
    @bot.on_message(filters.command("setup") & filters.private)
    async def setup_handler(client, message):
        try:
            # ইউজার আইডি এবং মেসেজ স্প্লিট করা
            uid = message.from_user.id
            parts = message.text.split(None, 3)
            
            if len(parts) < 4:
                return await message.reply_text(
                    "❌ **ভুল ফরম্যাট!**\n\n"
                    "**সঠিক নিয়ম:**\n"
                    "`/setup @channel feed_url tutorial_url`"
                )
            
            channel = parts[1]
            feed_url = parts[2]
            tutorial = parts[3]

            # ডাটাবাসে সেভ করা
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
                f"✅ **সেটআপ সম্পন্ন!**\n\n"
                f"📢 চ্যানেল: `{channel}`\n"
                f"🌐 ফিড: {feed_url}\n"
                f"🎥 টিউটোরিয়াল: {tutorial}\n\n"
                f"💡 এখন থেকে এই ব্লগে পোস্ট করলেই অটোমেটিক আপনার চ্যানেলে চলে যাবে।"
            )
        except Exception as e:
            await message.reply_text(f"❌ এরর: {e}")

    # ২. অটো মনিটর লুপ (ব্যাকগ্রাউন্ডে চলবে)
    async def monitor_feeds():
        print("🔍 Feed Monitor Loop Started...")
        while True:
            try:
                # ডাটাবাস থেকে সব ইউজারের কনফিগ নেওয়া
                configs = await user_setup_col.find({}).to_list(None)
                
                async with aiohttp.ClientSession() as session:
                    for config in configs:
                        try:
                            f_url = config.get("feed")
                            l_id = config.get("last_post_id")
                            target_chat = config.get("channel")
                            tutorial = config.get("tutorial")
                            uid = config.get("user_id")

                            async with session.get(f_url, timeout=10) as resp:
                                if resp.status != 200: continue
                                
                                xml_data = await resp.text()
                                root = ET.fromstring(xml_data)
                                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                                entries = root.findall('atom:entry', ns)

                                if not entries: continue
                                
                                latest = entries[0]
                                p_id = latest.find('atom:id', ns).text

                                # নতুন পোস্ট চেক
                                if p_id != l_id:
                                    title = latest.find('atom:title', ns).text
                                    link = latest.find('atom:link[@rel="alternate"]', ns).attrib['href']
                                    content = latest.find('atom:content', ns).text
                                    
                                    # পোস্টার ইমেজRegex
                                    img_match = re.search(r'<img.*?src="(.*?)"', content)
                                    poster = img_match.group(1) if img_match else None
                                    
                                    # ক্যাটাগরি/জনরা
                                    cats = [c.attrib['term'] for c in latest.findall('atom:category', ns)]
                                    genre = " | ".join(cats[:3]) if cats else "Movie"

                                    # টেমপ্লেট ডিজাইন
                                    caption = (
                                        f"🎬 **NEW UPDATE: {title}**\n"
                                        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                        f"🎭 **Genre:** {genre}\n"
                                        f"🔊 **Language:** Dual Audio\n"
                                        f"💎 **Quality:** 480p | 720p | 1080p\n\n"
                                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                        f"📥 **ডাউনলোড করতে নিচের লিংকে ক্লিক করুন**"
                                    )

                                    btns = InlineKeyboardMarkup([
                                        [InlineKeyboardButton("🔗 Watch / Download", url=link)],
                                        [InlineKeyboardButton("📽️ How to Download", url=tutorial)]
                                    ])

                                    # চ্যানেলে পাঠানো
                                    try:
                                        if poster:
                                            await bot.send_photo(target_chat, poster, caption=caption, reply_markup=btns)
                                        else:
                                            await bot.send_message(target_chat, caption, reply_markup=btns)
                                        
                                        # আইডি আপডেট
                                        await user_setup_col.update_one({"user_id": uid}, {"$set": {"last_post_id": p_id}})
                                    except:
                                        pass
                        except:
                            continue
            except:
                pass
            
            await asyncio.sleep(10) # ৫ মিনিট পর পর চেক

    # লুপটি ব্যাকগ্রাউন্ডে স্টার্ট করা
    asyncio.create_task(monitor_feeds())
