import __main__
import asyncio
import re
import aiohttp
import xml.etree.ElementTree as ET
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# মেইন ফাইল থেকে প্রয়োজনীয় জিনিস নেওয়া
db = __main__.db
TMDB_API_KEY = __main__.TMDB_API_KEY
user_setup_col = db["user_autopost_configs"]

async def get_tmdb_info(query):
    """TMDB থেকে মুভির ডিটেইলস নিয়ে আসার ফাংশন"""
    try:
        # টাইটেল থেকে বছর এবং বাড়তি লেখা বাদ দিয়ে ক্লিন করা (সার্চের সুবিধার জন্য)
        clean_name = re.sub(r'\(?\d{4}\)?|720p|1080p|480p|HDRip|WEB-DL|Dual Audio|Hindi|Bangla|English', '', query).strip()
        url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={clean_name}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                if data.get('results'):
                    res = data['results'][0]
                    m_type = res.get('media_type', 'movie')
                    m_id = res.get('id')
                    # আরও ডিটেইলস আনা
                    detail_url = f"https://api.themoviedb.org/3/{m_type}/{m_id}?api_key={TMDB_API_KEY}"
                    async with session.get(detail_url) as d_resp:
                        d_data = await d_resp.json()
                        return {
                            "rating": f"{d_data.get('vote_average', 0):.1f}/10",
                            "genres": ", ".join([g['name'] for g in d_data.get('genres', [])[:3]]),
                            "year": (d_data.get('release_date') or d_data.get('first_air_date') or "N/A")[:4],
                            "runtime": f"{d_data.get('runtime') or d_data.get('episode_run_time', [0])[0]} min"
                        }
    except:
        pass
    return None

def detect_language(text):
    """টাইটেল থেকে ল্যাঙ্গুয়েজ খুঁজে বের করার লজিক"""
    text = text.lower()
    if "dual audio" in text or "multi" in text: return "Dual Audio (Hindi-Eng)"
    if "hindi" in text: return "Hindi Dubbed"
    if "bangla" in text: return "Bangla"
    if "english" in text: return "English"
    if "tamil" in text: return "Tamil"
    if "telugu" in text: return "Telugu"
    return "Dual Audio"

async def register(bot):
    print("🎬 Advanced Autopost with TMDB & Box UI: Activated!")

    @bot.on_message(filters.command("myconfig") & filters.private, group=-1)
    async def check_config(client, message):
        config = await user_setup_col.find_one({"user_id": message.from_user.id})
        if config:
            await message.reply_text(f"⚙️ **Your Current Config:**\n\n📢 Channel: `{config.get('channel')}`\n🌐 Feed: {config.get('feed')}\n🎥 Tutorial: {config.get('tutorial')}")
        else:
            await message.reply_text("❌ No config found. Use `/setup`.")

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
            await message.reply_text("✅ **Setup Successful!** TMDB & Box Layout applied.")
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
                                    
                                    # ডাটা এক্সট্রাকশন
                                    tmdb = await get_tmdb_info(title)
                                    lang = detect_language(title)
                                    img_match = re.search(r'<img.*?src="(.*?)"', content)
                                    poster = img_match.group(1) if img_match else None
                                    
                                    # প্রিমিয়াম বক্স টেমপ্লেট
                                    if tmdb:
                                        caption = (
                                            f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
                                            f"🎬 **NEW UPDATE: {title[:40]}**\n"
                                            f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
                                            f"⭐️ **Rating:** {tmdb['rating']}\n"
                                            f"🎭 **Genres:** {tmdb['genres']}\n"
                                            f"📅 **Year:** {tmdb['year']}\n"
                                            f"⏱ **Runtime:** {tmdb['runtime']}\n"
                                            f"🗣 **Language:** {lang}\n"
                                            f"💎 **Quality:** 480p | 720p | 1080p\n\n"
                                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                                            f"📥 **ডাউনলোড করতে নিচের লিংকে ক্লিক করুন 👇**"
                                        )
                                    else:
                                        caption = (
                                            f"🎬 **NEW UPDATE: {title}**\n"
                                            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                            f"🗣 **Language:** {lang}\n"
                                            f"💎 **Quality:** High Quality\n\n"
                                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                            f"📥 **ডাউনলোড লিংক নিচে দেওয়া হলো 👇**"
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
