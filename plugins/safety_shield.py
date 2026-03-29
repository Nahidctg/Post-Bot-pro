# plugins/safety_shield.py
import __main__
import json

# --- 🔞 ১৮+ মুভি চেনার জন্য কিওয়ার্ড লিস্ট ---
ADULT_KEYWORDS = ["erotic", "porn", "sexy", "nudity", "adult", "18+", "uncut", "kink", "sex"]

def is_content_adult(data):
    # ১. TMDB এর অফিসিয়াল অ্যাডাল্ট ফ্ল্যাগ চেক করা
    if data.get('adult') is True or data.get('force_adult') is True:
        return True
    
    # ২. টাইটেল বা ওভারভিউতে খারাপ শব্দ আছে কি না চেক করা
    title = (data.get("title") or data.get("name") or "").lower()
    overview = (data.get("overview") or "").lower()
    
    for word in ADULT_KEYWORDS:
        if word in title or word in overview:
            return True
    return False

# --- 🛡️ ANTI-COPYRIGHT & BLUR UI ---
def get_safety_shield_code(is_adult):
    blur_css = ""
    if is_adult:
        blur_css = """
        <style>
            .nsfw-wrapper { position: relative; cursor: pointer; border-radius: 10px; overflow: hidden; display: block; }
            .nsfw-blur { filter: blur(50px); transition: filter 0.4s ease; pointer-events: none; }
            .nsfw-overlay { 
                position: absolute; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.85); color: #ff5252; 
                display: flex; align-items: center; justify-content: center;
                flex-direction: column; z-index: 50; transition: 0.3s;
                border: 2px solid #ff5252; border-radius: 10px;
                text-align: center; padding: 15px; box-sizing: border-box;
            }
            .nsfw-overlay b { font-size: 20px; text-shadow: 0 0 10px #ff5252; margin-bottom: 8px; }
            .nsfw-overlay span { font-size: 14px; color: #eee; }
            .revealed .nsfw-blur { filter: blur(0px) !important; pointer-events: auto; }
            .revealed .nsfw-overlay { display: none !important; }
            
            /* স্ক্রিনশট গ্রিডের জন্য বিশেষ স্টাইল */
            .screenshot-grid.nsfw-blur-grid { filter: blur(40px); pointer-events: none; }
            .revealed-grid { filter: blur(0px) !important; pointer-events: auto !important; }
        </style>
        """
    
    disclaimer_html = """
    <div style="margin-top: 50px; padding: 20px; background: rgba(255,255,255,0.02); border-top: 1px solid #333; font-size: 12px; color: #888; text-align: justify; line-height: 1.6; font-family: sans-serif;">
        <b style="color:#bbb;">DMCA & Copyright Disclaimer:</b> This website is an online metadata database and review portal. We do not host any copyrighted files or videos on our servers. All content provided here is for educational and informational purposes only. All links are indexed from third-party sources. If you believe your copyrighted work has been linked without permission, please contact us for immediate removal. 
        <br><br>
        <center><a href="https://t.me/CineZoneBD1" style="color:#E50914; text-decoration: none; font-weight: bold; border: 1px solid #E50914; padding: 5px 15px; border-radius: 5px;">Report Content / DMCA Request</a></center>
    </div>
    """
    
    reveal_js = """
    <script>
    function revealNSFW(el) {
        el.classList.add('revealed');
    }
    function revealScreenshots(el) {
        el.parentElement.querySelector('.screenshot-grid').classList.add('revealed-grid');
        el.style.display = 'none';
    }
    </script>
    """
    return blur_css + disclaimer_html + reveal_js

# ==========================================================
# 🔥 MONKEY PATCH: HTML GENERATOR (FINAL FIXED VERSION)
# ==========================================================

if not hasattr(__main__, 'shield_old_html'):
    __main__.shield_old_html = __main__.generate_html_code

def safety_shield_generator(data, links, user_ads, owner_ads, share):
    # ১. মুভিটি ১৮+ কি না চেক করা
    is_adult = is_content_adult(data)
    
    # ২. অরিজিনাল HTML কোড নেওয়া
    html = __main__.shield_old_html(data, links, user_ads, owner_ads, share)
    
    # ৩. যদি ১৮+ হয়, তবে শুধুমাত্র পোস্টার এবং স্ক্রিনশট ব্লার করা
    if is_adult:
        # মেইন পোস্টার ব্লার করা (info-poster ক্লাস টার্গেট করে)
        poster_search = '<div class="info-poster">'
        poster_replace = (
            '<div class="info-poster">'
            '<div class="nsfw-wrapper" onclick="revealNSFW(this)">'
            '<div class="nsfw-overlay"><b>🔞 18+ Content</b><br><span>Click to Reveal Poster</span></div>'
            '<div class="nsfw-blur">'
        )
        if poster_search in html:
            html = html.replace(poster_search, poster_replace)
            # পোস্টার ইমেজের ট্যাগ শেষ হলে ব্লার ডিভ ক্লোজ করা
            html = html.replace('alt="Poster">', 'alt="Poster"></div></div>')

        # স্ক্রিনশট গ্রিড ব্লার করা
        ss_search = '<div class="screenshot-grid">'
        ss_replace = (
            '<div style="position:relative;">'
            '<div class="nsfw-overlay" onclick="revealScreenshots(this)" style="cursor:pointer; height:200px;"><b>🔞 18+ Screenshots</b><br><span>Click to Reveal</span></div>'
            '<div class="screenshot-grid nsfw-blur-grid">'
        )
        if ss_search in html:
            html = html.replace(ss_search, ss_replace)
            # স্ক্রিনশট সেকশন শেষ হলে ডিভ ক্লোজ করা (আপনার কোডের স্ট্রাকচার অনুযায়ী)
            # সাধারণত স্ক্রিনশট শেষ হয় </div> এর পর, আমরা একটি অতিরিক্ত </div> দেব
            if '<!-- SCREENSHOT_END -->' in html:
                html = html.replace('<!-- SCREENSHOT_END -->', '</div></div>')
            else:
                # যদি কমেন্ট না থাকে, তবে গ্রিডের শেষে ক্লোজ করার চেষ্টা করবে
                # এটি আপনার মূল কোডের HTML ফরমেটের ওপর নির্ভর করবে
                pass

    # ৪. সেফটি কোড এবং ডিসক্লেইমার যুক্ত করা
    safety_code = get_safety_shield_code(is_adult)
    
    return f"{html}\n{safety_code}"

__main__.generate_html_code = safety_shield_generator

async def register(bot):
    print("🛡️ Safety Shield & Adult Blur Plugin: Activated!")

print("✅ Safety Shield Plugin Loaded Successfully!")
