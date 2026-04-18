# plugins/multi_paste_backup.py
import __main__
import aiohttp
import io
import logging
import asyncio
from pyrogram import filters, handlers
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

# --- প্রতিটি সার্ভারের জন্য আলাদা ফাংশন (Fast & Independent) ---

async def upload_dpaste(session, content):
    try:
        async with session.post("https://dpaste.com/api/", data={"content": content, "syntax": "html", "expiry_days": 1}, timeout=5) as resp:
            if resp.status in [200, 201]:
                return (await resp.text()).strip()
    except: return None

async def upload_pasters(session, content):
    try:
        async with session.post("https://paste.rs", data=content.encode('utf-8'), timeout=5) as resp:
            if resp.status in [200, 201]:
                return await resp.text()
    except: return None

async def upload_spacebin(session, content):
    try:
        async with session.post("https://spaceb.in/api/v1/documents", json={"content": content, "extension": "html"}, timeout=5) as resp:
            if resp.status in [200, 201]:
                res = await resp.json()
                return f"https://spaceb.in/{res['payload']['id']}"
    except: return None

async def upload_nekobin(session, content):
    try:
        async with session.post("https://nekobin.com/api/documents", json={"content": content}, timeout=5) as resp:
            if resp.status == 200:
                res = await resp.json()
                return f"https://nekobin.com/{res['result']['key']}"
    except: return None

# --- 🚀 প্যারালাল আপলোড লজিক (সবগুলো একসাথে ট্রাই করবে) ---
async def enhanced_paste_service(content):
    if not content: return None

    async with aiohttp.ClientSession() as session:
        # সব সার্ভারে একসাথে রিকোয়েস্ট পাঠানো হচ্ছে
        tasks = [
            upload_dpaste(session, content),
            upload_pasters(session, content),
            upload_spacebin(session, content),
            upload_nekobin(session, content)
        ]
        
        # যেটা আগে রেসপন্স দিবে সেটাই নিবে (Concurrent Execution)
        for completed_task in asyncio.as_completed(tasks):
            link = await completed_task
            if link:
                return link # যেকোনো একটা সফল হলে সেটাই রিটার্ন করবে
                
    return None

# --- 🛠️ প্যাচ করা মেইন ফাংশন ---
async def patched_get_code(client, cb):
    try:
        # ডেটা চেক
        data_parts = cb.data.rsplit("_", 1)
        uid = int(data_parts[-1])
    except: return
        
    data = __main__.user_conversations.get(uid)
    if not data or "final" not in data:
        return await cb.answer("❌ ডেটা পাওয়া যায়নি! নতুন করে পোস্ট করুন।", show_alert=True)
    
    await cb.answer("🚀 সার্ভারে আপলোড হচ্ছে (Fast Mode)...", show_alert=False)
    
    html_code = data["final"]["html"]
    
    # লিঙ্ক জেনারেট করা (এটি এখন অনেক ফাস্ট হবে)
    link = await enhanced_paste_service(html_code)
    
    btns = []
    if link:
        btns.append([InlineKeyboardButton("🌐 Open Blogger Code", url=link)])
    
    btns.append([InlineKeyboardButton("📝 Get Direct Code (Message)", callback_data=f"get_raw_text_{uid}")])
    btns.append([InlineKeyboardButton("📁 Download HTML File", callback_data=f"send_file_only_{uid}")])
    
    msg_text = f"✅ **Blogger Code Ready!**\n\n"
    if link:
        msg_text += f"🔗 **Link:** `{link}`\n\n"
    else:
        msg_text += f"⚠️ **সবগুলো সার্ভার বিজি!** নিচে থেকে ফাইল বা টেক্সট কপি করুন।\n\n"
    
    msg_text += "💡 _Direct Code বাটনে ক্লিক করলে মেসেজেই কোড পাবেন।_"

    await cb.message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(btns), disable_web_page_preview=True)

# --- সরাসরি মেসেজে কোড পাঠানো (Existing logic optimized) ---
@__main__.bot.on_callback_query(filters.regex("^get_raw_text_"))
async def get_raw_text_handler(client, cb):
    uid = int(cb.data.split("_")[-1])
    data = __main__.user_conversations.get(uid)
    if not data or "final" not in data:
        return await cb.answer("ডেটা নেই!", show_alert=True)
    
    code = data["final"]["html"]
    
    if len(code) < 3900:
        await cb.message.reply_text(f"<code>{code}</code>", parse_mode="html")
    else:
        parts = [code[i:i+3900] for i in range(0, len(code), 3900)]
        for part in parts:
            await cb.message.reply_text(f"<code>{part}</code>", parse_mode="html")
            await asyncio.sleep(0.3)
    await cb.answer()

# --- ফাইল হ্যান্ডলার ---
async def send_file_handler(client, cb):
    try:
        uid = int(cb.data.split("_")[-1])
        data = __main__.user_conversations.get(uid)
        if data and "final" in data:
            file = io.BytesIO(data["final"]["html"].encode('utf-8'))
            file.name = "blogger_code.html"
            await client.send_document(cb.message.chat.id, file, caption="📄 HTML Code File")
            await cb.answer()
    except: pass

# --- রেজিস্ট্রেশন ---
async def register(bot):
    __main__.create_paste_link = enhanced_paste_service
    bot.add_handler(handlers.CallbackQueryHandler(patched_get_code, filters.regex("^get_code_")), group=-1)
    bot.add_handler(handlers.CallbackQueryHandler(send_file_handler, filters.regex("^send_file_only_")), group=-1)
    print("✅ Ultra-Fast Multi-Paste Optimization Active!")
