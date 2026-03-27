import os
import urllib.parse
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# আপনার ওয়েবসাইটের মেইন লিঙ্ক এখানে দিন
# উদাহরণ: https://www.moviezone.com.bd
YOUR_WEBSITE_URL = "https://banglaflix4k.blogspot.com" 

# ডাটাবেস ইমপোর্ট
try:
    from bot import posts_col
except ImportError:
    from __main__ import posts_col

@Client.on_message(filters.private & filters.text & filters.incoming, group=5)
async def website_traffic_handler(client, message):
    query = message.text.strip()
    
    # ৩ অক্ষরের নিচে বা কমান্ড হলে ইগনোর করবে
    if len(query) < 3 or query.startswith("/"):
        return

    # ডাটাবেসে চেক করা (মুভিটি আপনার সাইটে আছে কিনা)
    # আমরা মুভির টাইটেল অথবা অরিজিনাল নামের সাথে ম্যাচ করবো
    post = await posts_col.find_one({
        "$or": [
            {"details.title": {"$regex": f"^{query}", "$options": "i"}},
            {"details.name": {"$regex": f"^{query}", "$options": "i"}}
        ]
    })

    if post:
        # মুভির সঠিক নাম এবং বছর বের করা
        title = post['details'].get('title') or post['details'].get('name')
        year = str(post['details'].get('release_date') or post['details'].get('first_air_date') or "----")[:4]
        
        # ব্লগার বা ওয়ার্ডপ্রেসের জন্য সঠিক সার্চ কিউয়েরি তৈরি (টাইটেল + সাল)
        # এতে সার্চ রেজাল্টে শুধু ওই মুভিটিই আসবে
        exact_search_term = f"{title} {year}"
        search_query = urllib.parse.quote(exact_search_term)
        
        # ব্লগারের জন্য সার্চ ইউআরএল (এটি ইউজারকে সঠিক মুভির কাছে নিয়ে যাবে)
        final_website_link = f"{YOUR_WEBSITE_URL}/search?q={search_query}"

        # সুন্দর একটি কার্ড মেসেজ
        text = (
            f"🎬 **{title} ({year})**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌟 **রেটিং:** {post['details'].get('vote_average', 'N/A')}/10\n"
            f"🎭 **জনরা:** {', '.join([g['name'] for g in post['details'].get('genres', [])[:2]])}\n\n"
            f"✅ মুভিটি আমাদের সার্ভারে পাওয়া গেছে!\n"
            f"নিচের বাটনে ক্লিক করে ওয়েবসাইট থেকে সরাসরি **Download** করে নিন। 👇"
        )
        
        btns = [[InlineKeyboardButton("📥 সরাসরি ওয়েবসাইট থেকে ডাউনলোড করুন", url=final_website_link)]]
        
        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(btns),
            quote=True
        )
    else:
        # মুভি না পাওয়া গেলে কোনো মেসেজ দিবে না
        pass
