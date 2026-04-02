import os
import asyncio
import main # আপনার মেইন ফাইল ইমপোর্ট করা হচ্ছে
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import render_template_string

# --- ১. গ্যালারি ইউআরএল সেটআপ ---
# আপনার হোস্ট করা অ্যাপের লিঙ্ক (যেমন: https://my-bot.onrender.com)
SERVER_URL = "https://gorgeous-donetta-nahidcrk-7b84dba9.koyeb.app" 

# --- ২. ফ্লাস্ক গ্যালারি পেজ ডিজাইন ---
GALLERY_HTML = """
<html>
<head>
    <title>{{ title }} - Gallery</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { background: #0b0b0e; color: white; font-family: sans-serif; text-align: center; padding: 20px; }
        .container { max-width: 800px; margin: auto; }
        img { width: 100%; border-radius: 12px; margin-bottom: 20px; border: 1px solid #333; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        h2 { color: #ff5252; text-transform: uppercase; letter-spacing: 1px; }
        .footer { margin-top: 30px; color: #555; font-size: 13px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🔞 {{ title }}</h2>
        <div style="border-bottom: 1px solid #222; margin-bottom: 25px;"></div>
        {% for img in images %}
            <img src="{{ img }}">
        {% endfor %}
        <div class="footer">Securely Hosted Gallery</div>
    </div>
</body>
</html>
"""

# --- ৩. মেইন ফাংশন প্যাচিং (HTML & Selection Logic) ---
original_generate_html = main.generate_html_code

# HTML জেনারেটর পরিবর্তন (十八禁 মুভির জন্য বাটন বসানো)
def patched_generate_html(data, links, user_ads, owner_ads, share_percent=20):
    is_nsfw = data.get('adult', False) or data.get('force_adult', False)
    
    if is_nsfw:
        temp_data = data.copy()
        post_id = data.get('post_id', 'temp')
        gallery_link = f"{SERVER_URL}/gallery/{post_id}"
        
        # ব্লগারে যাওয়ার জন্য ইমেজ ডাটা রিমুভ করা
        temp_data['manual_screenshots'] = []
        temp_data['images'] = {'backdrops': []}
        
        html = original_generate_html(temp_data, links, user_ads, owner_ads, share_percent)
        
        # ব্লগার কোডে গ্যালারি বাটন ঢুকানো
        gallery_button = f'''
        <div class="section-title">📸 Screenshots (18+)</div>
        <div style="background: rgba(229, 9, 20, 0.1); padding: 25px; border-radius: 12px; text-align: center; border: 2px dashed #ff5252; margin: 20px 0;">
            <p style="color: #ff5252; font-weight: bold; font-size: 16px; margin-bottom: 10px;">🔞 Content Restricted!</p>
            <p style="color: #ccc; font-size: 13px; margin-bottom: 15px;">Due to policy, adult screenshots are hosted in our private gallery.</p>
            <a href="{gallery_link}" target="_blank" 
               style="display: inline-block; background: #E50914; color: white; padding: 14px 30px; border-radius: 8px; text-decoration: none; font-weight: bold; box-shadow: 0 4px 20px rgba(229, 9, 20, 0.5);">
               🔓 VIEW PRIVATE GALLERY
            </a>
        </div>
        '''
        if "<!-- Screenshots Section -->" in html:
            html = html.replace("<!-- Screenshots Section -->", gallery_button)
        else:
            html = html.replace('<!-- Download Section -->', f'{gallery_button}\n<!-- Download Section -->')
        return html
    else:
        return original_generate_html(data, links, user_ads, owner_ads, share_percent)

# --- ৪. সিলেকশন লজিক ইন্টারসেপ্টর ---
# যখন আপনি মুভি সিলেক্ট করেন, তখন এই ফাংশনটি রান হবে
async def new_on_select(client, cb):
    try:
        _, m_type, m_id = cb.data.split("_")
        details = await main.get_tmdb_details(m_type, m_id)
        if not details:
            return await cb.message.edit_text("❌ Details not found.")
            
        uid = cb.from_user.id
        main.user_conversations[uid] = { "details": details, "links":[], "state": "" }
        
        # ১৮+ চেক করা হচ্ছে
        is_adult = details.get('adult', False)
        
        if is_adult:
            # যদি ১৮+ হয়, তবে আলাদা বাটন দেখাবে
            btns = [
                [InlineKeyboardButton("✅ Yes, Add SS", callback_data=f"nsfw_ask_ss_yes_{uid}")],
                [InlineKeyboardButton("⏭️ No, Skip (No SS)", callback_data=f"nsfw_ask_ss_no_{uid}")]
            ]
            await cb.message.edit_text(
                f"🔞 **NSFW Content Detected!**\nSelected: **{details.get('title') or details.get('name')}**\n\nআপনি কি এই মুভির জন্য ম্যানুয়ালি স্ক্রিনশট অ্যাড করতে চান?", 
                reply_markup=InlineKeyboardMarkup(btns)
            )
        else:
            # সাধারণ মুভি হলে সরাসরি ল্যাঙ্গুয়েজ চাইবে
            main.user_conversations[uid]["state"] = "wait_lang"
            await cb.message.edit_text(f"✅ Selected: **{details.get('title') or details.get('name')}**\n\n🗣️ Enter **Language**:")
            
    except Exception as e:
        print(f"Error in Selection: {e}")

# --- ৫. প্লাগইন রেজিস্ট্রেশন ---
async def register(bot):
    # ১. HTML জেনারেটর রিপ্লেস
    main.generate_html_code = patched_generate_html
    
    # ২. মেইন বটের সিলেকশন হ্যান্ডলার রিপ্লেস (Monkey Patching)
    # এটি মেইন ফাইলের on_select ফাংশনটিকে এই নতুন লজিক দিয়ে বদলে দেবে
    main.on_select = new_on_select 

    # ৩. ১৮+ স্ক্রিনশট চয়েস হ্যান্ডলার
    @bot.on_callback_query(filters.regex("^nsfw_ask_ss_"))
    async def nsfw_choice_handler(client, cb):
        _, _, _, choice, uid = cb.data.split("_")
        uid = int(uid)
        
        if choice == "yes":
            main.user_conversations[uid]["state"] = "wait_screenshots"
            main.user_conversations[uid]["details"]["manual_screenshots"] = []
            await cb.message.edit_text("📸 **১৮+ স্ক্রিনশটগুলো পাঠান।**\nএকটি একটি করে ছবি পাঠান, সব পাঠানো শেষ হলে **DONE** এ ক্লিক করুন।")
        else:
            main.user_conversations[uid]["state"] = "wait_lang"
            await cb.message.edit_text("🗣️ Enter **Language** (e.g. Hindi):")

    # ৪. ফ্লাস্ক রুট সেটআপ
    @main.app.route('/gallery/<post_id>')
    def show_nsfw_gallery(post_id):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        post = loop.run_until_complete(main.posts_col.find_one({"_id": post_id}))
        
        if not post or 'manual_screenshots' not in post['details']:
            return "<h3>❌ Gallery not found.</h3>", 404
            
        title = post['details'].get('title', 'Gallery')
        images = post['details'].get('manual_screenshots', [])
        return render_template_string(GALLERY_HTML, title=title, images=images)

    print("✅ Plugin Loaded: NSFW Safety Manager (Advanced Selection Flow)")
