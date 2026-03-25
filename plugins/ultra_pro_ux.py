# plugins/ultra_pro_ux.py
import __main__
import base64
import json

# --- 🎭 ADVANCED UX & UI INJECTOR (THUMBNAIL & PREVIEW FIX) ---
async def register(bot):
    print("🚀 Ultra UX & Blogger Thumbnail Fix: Activated!")

# এই ফাংশনটি HTML এর একদম নিচে ডিজাইন কোডগুলো বসাবে
def get_ux_footer_code(data):
    backdrop = data.get('backdrop_path')
    bg_url = f"https://image.tmdb.org/t/p/original{backdrop}" if backdrop else ""
    
    return f"""
    <style>
        /* 🌌 ইমারসিভ ব্যাকগ্রাউন্ড */
        body {{ 
            background: #05060a !important; 
            background-image: linear-gradient(to bottom, rgba(5,6,10,0.8), #05060a), url('{bg_url}') !important;
            background-attachment: fixed !important;
            background-size: cover !important;
            background-position: center !important;
        }}
        
        /* 🏷️ মিডিয়া ব্যাজ */
        .media-badges {{ display: flex; gap: 8px; justify-content: center; margin-bottom: 20px; flex-wrap: wrap; }}
        .badge {{ background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: #fff; font-size: 11px; padding: 3px 10px; border-radius: 4px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }}
        .badge-4k {{ color: #ffd700; border-color: #ffd700; }}
        .badge-hdr {{ color: #00d1b2; border-color: #00d1b2; }}

        /* 📱 ফ্লোটিং বার */
        .floating-bar {{ position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(25, 27, 34, 0.9); backdrop-filter: blur(15px); padding: 10px 25px; border-radius: 50px; display: flex; gap: 25px; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 10px 30px rgba(0,0,0,0.5); z-index: 1000; }}
        .floating-bar a {{ color: #fff; text-decoration: none; font-size: 13px; display: flex; align-items: center; gap: 8px; font-weight: 500; }}
        
        /* ⏳ গ্লোয়িং প্রগ্রেস */
        #unlock-timer {{ width: 0%; height: 4px; background: linear-gradient(90deg, #E50914, #ff5252); position: absolute; bottom: 0; left: 0; transition: width 5s linear; box-shadow: 0 0 10px #E50914; }}
    </style>
    <script>
    function startUnlock(btn, type) {{
        let randomAd = AD_LINKS[Math.floor(Math.random() * AD_LINKS.length)];
        window.open(randomAd, '_blank'); 
        btn.style.position = 'relative';
        btn.innerHTML += '<div id="unlock-timer"></div>';
        btn.disabled = true;
        let timeLeft = 5;
        let timer = setInterval(function() {{
            btn.innerHTML = "⏳ UNLOCKING " + timeLeft + "s";
            if (timeLeft < 0) {{
                clearInterval(timer);
                document.getElementById('view-details').style.display = 'none';
                document.getElementById('view-links').style.display = 'block';
                window.scrollTo({{top: 0, behavior: 'smooth'}});
            }}
            timeLeft--;
        }}, 1000);
        setTimeout(() => {{ document.getElementById('unlock-timer').style.width = '100%'; }}, 10);
    }}
    </script>
    """

# ==========================================================
# 🔥 MONKEY PATCH: HTML GENERATOR (THUMBNAIL FIX)
# ==========================================================

original_html_generator = __main__.generate_html_code

def blogger_friendly_generator(data, links, user_ads, owner_ads, share):
    # মেইন জেনারেটর থেকে HTML নেওয়া
    html = original_html_generator(data, links, user_ads, owner_ads, share)
    
    title = data.get("title") or data.get("name")
    plot = data.get("overview", "")[:150]
    poster = data.get('manual_poster_url') or f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}"
    
    # ১. 🖼️ ইনভিজিবল থাম্বনেইল (ব্লগার ড্যাশবোর্ডের জন্য)
    # এটি কোডের একদম শুরুতে থাকবে যাতে ব্লগার ছবি খুঁজে পায়
    thumbnail_html = f'<div style="height:0px;width:0px;overflow:hidden;visibility:hidden;display:none;float:left;"><img src="{poster}" alt="{title} Thumbnail" /></div>'
    
    # ২. 📝 ইনভিজিবল প্রিভিউ টেক্সট
    preview_snippet = f'<div style="display:none;font-size:1px;color:rgba(0,0,0,0);line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">🎬 {title} - {plot}... Download now.</div>'
    
    # ৩. 🏷️ মিডিয়া ব্যাজ তৈরি
    quality = data.get('custom_quality', '').upper()
    badges_html = '<div class="media-badges">'
    badges_html += '<div class="badge">Dual Audio</div>'
    if '1080P' in quality: badges_html += '<div class="badge badge-hdr">1080p Full HD</div>'
    badges_html += '<div class="badge">Dolby 5.1</div><div class="badge">HEVC</div></div>'
    
    # ৪. 📱 ফ্লোটিং বার
    floating_menu = f"""
    <div class="floating-bar">
        <a href="https://t.me/{( __main__.bot.me).username}" target="_blank">💬 Report Link</a>
        <a href="https://t.me/{( __main__.bot.me).username}" target="_blank">✈️ Join Group</a>
    </div>
    """
    
    # ৫. 💎 এসইও স্কিমা
    schema_code = f'<script type="application/ld+json">{json.dumps({"@context": "https://schema.org","@type": "Movie","name": title,"image": poster,"description": plot})}</script>'
    
    # ৬. 🎨 সিএসএস এবং জেএস (যা নিচে থাকবে)
    footer_code = get_ux_footer_code(data)
    
    # ব্যাজগুলো টাইটেলের ঠিক নিচে বসানো
    html = html.replace('<div class="movie-title">', badges_html + '<div class="movie-title">')
    
    # 🏁 ফাইনাল আউটপুট সাজানো: থাম্বনেইল সবার আগে থাকবে!
    return f"{thumbnail_html}\n{preview_snippet}\n{schema_code}\n{html}\n{floating_menu}\n{footer_code}"

# মেইন জেনারেটর রিপ্লেস করা
__main__.generate_html_code = blogger_friendly_generator

print("✅ Blogger Thumbnail Fix Applied Successfully!")
