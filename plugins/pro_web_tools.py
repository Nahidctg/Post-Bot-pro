# plugins/pro_web_tools.py
import json
import base64
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- 💎 SEO & SCHEMA MARKUP GENERATOR ---
def get_seo_schema(data):
    title = data.get("title") or data.get("name")
    poster = data.get('manual_poster_url') or f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}"
    overview = data.get("overview", "No plot available.")[:160]
    rating = data.get('vote_average', 0)
    
    schema = {
        "@context": "https://schema.org",
        "@type": "Movie",
        "name": title,
        "image": poster,
        "description": overview,
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": rating,
            "bestRating": "10",
            "ratingCount": "150"
        }
    }
    return f'<script type="application/ld+json">{json.dumps(schema)}</script>'

# --- 🛡️ ANTI-ADBLOCK SCRIPT ---
def get_anti_adblock_js():
    return """
    <script>
    async function detectAdBlock() {
      let adBlockEnabled = false;
      const googleAdUrl = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js';
      try {
        await fetch(new Request(googleAdUrl)).catch(_ => adBlockEnabled = true);
      } catch (e) { adBlockEnabled = true; }
      
      if (adBlockEnabled) {
        const linkView = document.getElementById('view-links');
        if(linkView) {
            linkView.innerHTML = `
            <div style="background:rgba(255,82,82,0.1); color:#ff5252; padding:30px; border:2px dashed #ff5252; border-radius:15px; font-family:sans-serif; text-align:center;">
                <h2 style="margin:0 0 10px;">⚠️ Ad-Blocker Detected!</h2>
                <p>Our server costs are covered by ads. Please <b>Disable Ad-Blocker</b> and Refresh the page to see download links.</p>
                <button onclick="window.location.reload()" style="background:#ff5252; color:#fff; border:none; padding:10px 20px; border-radius:5px; cursor:pointer; font-weight:bold; margin-top:10px;">I have disabled it, Refresh!</button>
            </div>`;
            linkView.style.display = 'block';
            document.getElementById('view-details').style.display = 'none';
        }
      }
    }
    window.onload = function() { detectAdBlock(); };
    </script>
    """

# --- 🎨 PREMIUM THEME: ANIME GLASS (Style 1) ---
def get_anime_theme_css():
    return """
    <style>
    :root { --glass: rgba(255, 255, 255, 0.1); --primary: #ff79c6; --bg: #282a36; }
    .app-wrapper { background: var(--bg) !important; border: none !important; backdrop-filter: blur(10px); color: #f8f8f2 !important; box-shadow: 0 0 40px rgba(0,0,0,0.8) !important; }
    .movie-title { color: var(--primary) !important; text-transform: uppercase; letter-spacing: 2px; }
    .info-box { background: var(--glass) !important; border: 1px solid rgba(255,255,255,0.1) !important; }
    .main-btn { border-radius: 50px !important; text-shadow: 1px 1px 2px #000; }
    .btn-watch { background: linear-gradient(45deg, #ff79c6, #bd93f9) !important; }
    .quality-title { background: #44475a !important; color: #50fa7b !important; border-left: 5px solid #50fa7b !important; }
    </style>
    """

# --- 🎨 PREMIUM THEME: MINIMAL DARK (Style 2) ---
def get_minimal_theme_css():
    return """
    <style>
    :root { --primary: #00d1b2; --bg: #121212; }
    .app-wrapper { background: var(--bg) !important; border-radius: 0px !important; border: 1px solid #333 !important; }
    .movie-title { font-family: 'Oswald', sans-serif; font-size: 30px !important; }
    .info-poster img { border-radius: 4px !important; filter: grayscale(0.3); }
    .plot-box { background: transparent !important; border: none !important; border-left: 2px solid var(--primary) !important; font-style: italic; }
    .main-btn { border: 1px solid var(--primary) !important; background: transparent !important; color: var(--primary) !important; }
    .main-btn:hover { background: var(--primary) !important; color: #000 !important; }
    </style>
    """

# --- 🔌 PLUGIN REGISTRATION ---
async def register(bot):
    
    @bot.on_callback_query(filters.regex("^theme_"))
    async def theme_selection_handler(client, cb):
        # এই হ্যান্ডলারটি মেইন কোডের থিম সিলেকশনকে ইন্টারসেপ্ট করবে
        try:
            _, theme_name, uid = cb.data.split("_")
            uid = int(uid)
        except: return

        # মেইন কোড থেকে ইউজার কনভারসেশন ডাটা নেওয়া
        import __main__
        if uid not in __main__.user_conversations:
            return await cb.answer("Session Expired!", show_alert=True)
        
        convo = __main__.user_conversations[uid]
        convo["details"]["theme"] = theme_name
        
        await cb.answer(f"🎨 {theme_name.title()} Theme Applied!")
        
        # জেনারেট প্রসেস শুরু
        await generate_enhanced_post(client, uid, cb.message)

async def generate_enhanced_post(client, uid, message):
    import __main__
    convo = __main__.user_conversations.get(uid)
    if not convo: return
    
    status_msg = await message.edit_text("💎 **Enhancing with SEO & Anti-Adblock...**")
    
    try:
        # মেইন বটের ফাংশন ব্যবহার করে বেসিক ডাটা তৈরি
        pid = await __main__.save_post_to_db(convo["details"], convo["links"])
        
        # মেইন জেনারেটর থেকে বেসিক HTML নেওয়া
        html = __main__.generate_html_code(
            convo["details"], convo["links"], 
            await __main__.get_user_ads(uid), 
            await __main__.get_owner_ads(), 
            await __main__.get_admin_share()
        )
        
        # --- নতুন ফিচারগুলো ইনজেক্ট করা ---
        seo_code = get_seo_schema(convo["details"])
        anti_adblock_code = get_anti_adblock_js()
        
        theme = convo["details"].get("theme", "netflix")
        theme_css = ""
        if theme == "light": # Light theme কে আমরা 'Anime' থিমে রূপান্তর করছি
            theme_css = get_anime_theme_css()
        elif theme == "prime": # Prime theme কে 'Minimal Dark' এ রূপান্তর করছি
            theme_css = get_minimal_theme_css()
            
        # HTML এর একদম শেষে আমাদের নতুন কোডগুলো জুড়ে দেওয়া
        enhanced_html = f"{seo_code}\n{theme_css}\n{anti_adblock_code}\n{html}"
        
        convo["final"] = {"html": enhanced_html}
        caption = __main__.generate_formatted_caption(convo["details"], pid)
        caption += "\n\n🚀 **Status:** Enhanced with SEO & Anti-Adblock!"
        
        # ইমেজ জেনারেশন (মেইন কোড থেকে)
        import asyncio
        loop = asyncio.get_running_loop()
        img_io, _ = await loop.run_in_executor(None, __main__.generate_image, convo["details"])
        
        btns = [[InlineKeyboardButton("📄 Get Enhanced Code", callback_data=f"get_code_{uid}")]]
        
        if img_io:
            await client.send_photo(message.chat.id, img_io, caption=caption, reply_markup=InlineKeyboardMarkup(btns))
            await status_msg.delete()
        else:
            await client.send_message(message.chat.id, caption, reply_markup=InlineKeyboardMarkup(btns))
            await status_msg.delete()
            
    except Exception as e:
        await status_msg.edit_text(f"❌ Error in Plugin: {e}")

print("✅ Pro Web Tools Plugin Loaded Successfully!")
