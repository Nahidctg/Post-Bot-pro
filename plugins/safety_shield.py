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
            .nsfw-container { position: relative; cursor: pointer; overflow: hidden; display: inline-block; width: 100%; }
            .nsfw-blur { filter: blur(40px); transition: filter 0.3s ease; }
            .nsfw-overlay { 
                position: absolute; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.7); color: #ff5252; 
                display: flex; align-items: center; justify-content: center;
                flex-direction: column; z-index: 10; transition: 0.3s;
                border: 2px solid #ff5252; border-radius: 10px;
                text-align: center; padding: 10px; box-sizing: border-box;
            }
            .nsfw-overlay b { font-size: 18px; text-shadow: 0 0 10px #ff5252; }
            .revealed .nsfw-blur { filter: blur(0px) !important; }
            .revealed .nsfw-overlay { display: none !important; }
        </style>
        """
    
    disclaimer_html = """
    <div style="margin-top: 50px; padding: 20px; background: rgba(255,255,255,0.02); border-top: 1px solid #333; font-size: 12px; color: #666; text-align: justify; line-height: 1.6;">
        <b>DMCA & Copyright Disclaimer:</b> This website is an online metadata database and review portal. We do not host any copyrighted files or videos on our servers. All content provided here is for educational and informational purposes only. All links are indexed from third-party sources. If you believe your copyrighted work has been linked without permission, please contact us for immediate removal. 
        <br><br>
        <center><a href="https://t.me/CineZoneBD1" style="color:#E50914;">Report Content / DMCA Request</a></center>
    </div>
    """
    
    reveal_js = """
    <script>
    function revealNSFW(el) {
        el.classList.add('revealed');
    }
    </script>
    """
    return blur_css + disclaimer_html + reveal_js

# ==========================================================
# 🔥 MONKEY PATCH: HTML GENERATOR (SAFETY VERSION)
# ==========================================================

if not hasattr(__main__, 'shield_old_html'):
    __main__.shield_old_html = __main__.generate_html_code

def safety_shield_generator(data, links, user_ads, owner_ads, share):
    # ১. মুভিটি ১৮+ কি না চেক করা
    is_adult = is_content_adult(data)
    
    # ২. অরিজিনাল HTML কোড নেওয়া
    html = __main__.shield_old_html(data, links, user_ads, owner_ads, share)
    
    # ৩. যদি ১৮+ হয়, তবে ইমেজগুলো ব্লার করা
    if is_adult:
        # মেইন পোস্টার ব্লার করা
        old_poster_tag = '<div class="info-poster">'
        new_poster_tag = (
            '<div class="info-poster">'
            '<div class="nsfw-container" onclick="revealNSFW(this)">'
            '<div class="nsfw-overlay"><b>🔞 18+ Content</b><br>Click to Reveal</div>'
        )
        html = html.replace(old_poster_tag, new_poster_tag)
        # পোস্টার ইমেজে ক্লাস যোগ করা
        html = html.replace('alt="Poster">', 'alt="Poster" class="nsfw-blur"></div>')
        
        # স্ক্রিনশটগুলো ব্লার করা (যদি স্ক্রিনশট গ্রিড থাকে)
        html = html.replace(
            '<div class="screenshot-grid">', 
            '<div class="screenshot-grid"><style>.screenshot-item { position:relative; overflow:hidden; }</style>'
        )
        # প্রতিটি ইমেজের জন্য ব্লার ইফেক্ট
        html = html.replace(
            '<img src="', 
            '<div class="nsfw-container" onclick="revealNSFW(this)"><div class="nsfw-overlay" style="font-size:10px;">🔞 Click</div><img class="nsfw-blur" src="'
        )
        # ডিভ ক্লোজ করা (এটি আপনার মেইন কোডের স্ট্রাকচারের ওপর নির্ভর করবে)
        html = html.replace('class="screenshot-img">', 'class="screenshot-img"></div>')

    # ৪. সেফটি কোড এবং ডিসক্লেইমার যুক্ত করা
    safety_code = get_safety_shield_code(is_adult)
    
    return f"{html}\n{safety_code}"

__main__.generate_html_code = safety_shield_generator

async def register(bot):
    print("🛡️ Safety Shield & Adult Blur Plugin: Activated!")

print("✅ Safety Shield Plugin Loaded Successfully!")
