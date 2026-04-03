# plugins/multi_paste_backup.py
import __main__
import aiohttp
import io
import logging
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

# --- 🚀 MULTI-SERVER PASTE LOGIC ---
async def enhanced_paste_service(content):
    """এটি একটির পর একটি সার্ভারে চেষ্টা করবে যদি dpaste ফেল করে"""
    if not content:
        return None

    # ১. dpaste.com (Original)
    try:
        url = "https://dpaste.com/api/"
        data = {"content": content, "syntax": "html", "expiry_days": 14}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, timeout=10) as resp:
                if resp.status in [200, 201]:
                    link = await resp.text()
                    return link.strip()
    except Exception as e:
        logger.error(f"dpaste failed: {e}")

    # ২. paste.rs (Backup 1)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://paste.rs", data=content.encode('utf-8'), timeout=10) as resp:
                if resp.status in [200, 201]:
                    return await resp.text()
    except Exception as e:
        logger.error(f"paste.rs failed: {e}")

    # ৩. spaceb.in (Backup 2)
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"content": content, "extension": "html"}
            async with session.post("https://spaceb.in/api/v1/documents", json=payload, timeout=10) as resp:
                if resp.status in [200, 201]:
                    res_json = await resp.json()
                    return f"https://spaceb.in/{res_json['payload']['id']}"
    except Exception as e:
        logger.error(f"spaceb.in failed: {e}")

    return None

# ==========================================================
# 🔥 SAFE PATCHING (অরিজিনাল ফাংশন ওভাররাইড)
# ==========================================================

# ১. create_paste_link ফাংশনটি রিপ্লেস করা (যাতে এটি মাল্টি-সার্ভার ব্যবহার করে)
__main__.create_paste_link = enhanced_paste_service


# ২. get_code কলব্যাক হ্যান্ডলার প্যাচিং
# আমরা অরিজিনাল হ্যান্ডলারকে রিমুভ না করে একটি নতুন কমান্ড বা লজিক দিয়ে রিপ্লেস করবো
# তবে সবচেয়ে সেফ হলো হ্যান্ডলারের ভেতরের লজিকটা বদলে দেওয়া

async def patched_get_code(client, cb):
    try:
        # ডেটা এক্সট্রাকশন (অরিজিনাল লজিক)
        _, _, uid = cb.data.rsplit("_", 2)
        uid = int(uid)
    except:
        return
        
    data = __main__.user_conversations.get(uid)
    if not data or "final" not in data:
        return await cb.answer("❌ Session Expired!", show_alert=True)
    
    await cb.answer("⏳ Generating Code (Trying Multi-Servers)...", show_alert=False)
    
    # আমাদের নতুন উন্নত সার্ভিস কল করা
    html_code = data["final"]["html"]
    link = await enhanced_paste_service(html_code)
    
    if link:
        # লিংক পাওয়া গেলে সুন্দর করে বাটনসহ পাঠানো
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Open Code Link", url=link)],
            [InlineKeyboardButton("📁 Download as File", callback_data=f"send_file_only_{uid}")]
        ])
        await cb.message.reply_text(
            f"✅ **Blogger Code Ready!**\n\n"
            f"🔗 **Paste Link:** `{link}`\n\n"
            f"💡 _লিংকটি কপি করে ব্লগারে পেস্ট করুন। লিংক কাজ না করলে নিচের ফাইল বাটনটি চাপুন।_",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    else:
        # যদি সব সার্ভার ফেল করে, অটোমেটিক ফাইল পাঠানো
        file = io.BytesIO(html_code.encode())
        file.name = "blogger_post_code.txt"
        await client.send_document(
            cb.message.chat.id, 
            file, 
            caption="⚠️ **All Paste Servers Failed!**\nএখানে আপনার ব্লকার পোস্টের কোড দেওয়া হলো (ফাইলটি ওপেন করে কোড কপি করুন)।"
        )

# ৩. অতিরিক্ত ফিচার: ফাইল ডাউনলোডের জন্য আলাদা হ্যান্ডলার
@__main__.bot.on_callback_query(filters.regex("^send_file_only_"))
async def send_file_handler(client, cb):
    uid = int(cb.data.split("_")[-1])
    data = __main__.user_conversations.get(uid)
    if data and "final" in data:
        file = io.BytesIO(data["final"]["html"].encode())
        file.name = "post_code.html"
        await client.send_document(cb.message.chat.id, file, caption="📄 Blogger Post HTML Code File.")
        await cb.answer("Sent!")

async def register(bot):
    # অরিজিনাল গেট কোড হ্যান্ডলারের জায়গায় আমাদের প্যাচ করা হ্যান্ডলারটি বসানো
    # Pyrogram-এ নতুন হ্যান্ডলার রেজিস্টার করলে সেটি আগে কাজ করে
    bot.add_handler(
        __main__.pyrogram.handlers.CallbackQueryHandler(
            patched_get_code, filters.regex("^get_code_")
        ), 
        group=-1 # Group -1 দিলে এটি মেইন কোডের আগের হ্যান্ডলারের আগে কাজ করবে
    )
    print("✅ Multi-Paste Backup Plugin Loaded with High Priority!")
