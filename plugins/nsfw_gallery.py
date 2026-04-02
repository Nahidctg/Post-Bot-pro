import os
import sys
import asyncio
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import render_template_string

# মেইন মডিউল রেফারেন্স (আপনার মেইন ফাইলটি যদি main.py হয়)
# যদি মেইন ফাইলের নাম অন্য কিছু হয়, তবে 'main' পরিবর্তন করে সেই নাম দিন
import main 

# --- ১. গ্যালারি টেমপ্লেট ---
GALLERY_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - NSFW Gallery</title>
    <style>
        body { background: #0f0f13; color: white; font-family: 'Segoe UI', sans-serif; text-align: center; padding: 20px; margin: 0; }
        .container { max-width: 800px; margin: auto; }
        img { width: 100%; border-radius: 12px; margin-bottom: 20px; border: 2px solid #1a1a24; box-shadow: 0 5px 25px rgba(0,0,0,0.5); transition: 0.3s; }
        img:hover { transform: scale(1.02); border-color: #ff5252; }
        h2 { color: #ff5252; margin-bottom: 30px; text-transform: uppercase; letter-spacing: 1.5px; }
        .footer { margin-top: 40px; color: #555; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🔞 {{ title }}</h2>
        <div style="border-bottom: 2px solid #1a1a24; margin-bottom: 30px;"></div>
        {% for img in images %}
            <img src="{{ img }}" alt="Screenshot">
        {% endfor %}
        <div class="footer">Securely Hosted by SPA Bot System</div>
    </div>
</body>
</html>
"""

# --- ২. HTML জেনারেটর প্যাচ (Monkey Patching) ---
# এটি আপনার মেইন কোডের generate_html_code ফাংশনকে রিপ্লেস করে দেবে রানটাইমে
original_generate_html = main.generate_html_code

def patched_generate_html(data, links, user_ad_links, owner_ad_links, admin_share=20):
    is_adult = data.get('adult', False) or data.get('force_adult', False)
    
    # আপনার অ্যাপের হোস্ট ইউআরএল (Render/Heroku/VPS)
    # এটি ডাইনামিকভাবে মেইন ফাইলের কনফিগ থেকেও নেওয়া সম্ভব
    base_url = "https://gorgeous-donetta-nahidcrk-7b84dba9.koyeb.app" # এখানে আপনার অরিজিনাল লিঙ্ক দিন

    if is_adult:
        # ১৮+ হলে ডাটা থেকে স্ক্রিনশট রিমুভ করে দেওয়া হবে যাতে ব্লগারে সরাসরি না যায়
        temp_data = data.copy()
        post_id = data.get('post_id', 'temp')
        
        # ব্লগারে যাওয়ার জন্য ডাটা ক্লিন করা
        temp_data['manual_screenshots'] = []
        temp_data['images'] = {'backdrops': []}
        
        # অরিজিনাল ফাংশন দিয়ে ক্লিন HTML জেনারেট করা
        html = original_generate_html(temp_data, links, user_ad_links, owner_ad_links, admin_share)
        
        # এবার সেই HTML এ গ্যালারি বাটন ইনজেক্ট করা
        gallery_btn_html = f'''
        <div class="section-title">📸 Screenshots (18+)</div>
        <div style="background: rgba(255, 82, 82, 0.1); padding: 25px; border-radius: 12px; text-align: center; border: 2px dashed #ff5252; margin: 20px 0;">
            <p style="color: #ff5252; font-weight: bold; font-size: 16px; margin-bottom: 8px;">🔞 Content is Restricted</p>
            <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 15px;">Due to Blogger's strict policy, adult screenshots are moved to our private gallery.</p>
            <a href="{base_url}/gallery/{post_id}" target="_blank" 
               style="display: inline-block; background: #E50914; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: bold; box-shadow: 0 4px 15px rgba(229, 9, 20, 0.4); transition: 0.3s;">
               🔓 VIEW PRIVATE GALLERY
            </a>
        </div>
        '''
        
        if "<!-- Screenshots Section -->" in html:
            html = html.replace("<!-- Screenshots Section -->", gallery_btn_html)
        else:
            html = html.replace('<!-- Download Section -->', f'{gallery_btn_html}\n<!-- Download Section -->')
            
        return html
    else:
        # সাধারণ মুভি হলে আগের মতোই কাজ করবে (Direct Images)
        return original_generate_html(data, links, user_ad_links, owner_ad_links, admin_share)

# --- ৩. প্লাগইন রেজিস্ট্রেশন ---
async def register(bot):
    
    # ফ্লাস্ক গ্যালারি রুট অ্যাড করা
    @main.app.route('/gallery/<post_id>')
    def adult_gallery(post_id):
        # ডাটাবেস থেকে পোস্ট রিড করা
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        post = loop.run_until_complete(main.posts_col.find_one({"_id": post_id}))
        
        if not post or 'manual_screenshots' not in post['details']:
            return "<h3>❌ Gallery empty or post not found.</h3>", 404
            
        title = post['details'].get('title', 'Gallery')
        ss_list = post['details'].get('manual_screenshots', [])
        return render_template_string(GALLERY_HTML, title=title, images=ss_list)

    # মেইন ফাংশনকে প্যাচ করা
    main.generate_html_code = patched_generate_html

    # ৪. ১৮+ মুভির ক্ষেত্রে ম্যানুয়াল স্ক্রিনশট অপশন (Callback Handler)
    @bot.on_callback_query(filters.regex("^ask_nsfw_ss_"))
    async def handle_nsfw_ss_choice(client, cb):
        action, uid = cb.data.replace("ask_nsfw_ss_", "").split("_")
        uid = int(uid)
        
        if action == "yes":
            main.user_conversations[uid]["state"] = "wait_screenshots"
            main.user_conversations[uid]["details"]["manual_screenshots"] = []
            await cb.message.edit_text("📸 **১৮+ স্ক্রিনশটগুলো পাঠান।**\nএকটি করে ছবি পাঠান, সব পাঠানো শেষ হলে **DONE** বাটনে ক্লিক করুন।")
        else:
            main.user_conversations[uid]["state"] = "wait_lang"
            await cb.message.edit_text("🗣️ Enter **Language** (e.g. Hindi):")

    # টেস্ট কমান্ড
    @bot.on_message(filters.command("nsfw_status"))
    async def nsfw_status(client, message):
        await message.reply_text("✅ **NSFW Safety Plugin is Active!**\nBlogger anti-ban logic enabled.")

    print("🔌 Plugin Loaded: NSFW Safety Manager (Gallery System)")
