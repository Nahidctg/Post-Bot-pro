# plugins/safety_shield.py
import __main__
import base64
import re

# --- 🔞 ১৮+ মুভি চেনার জন্য কিওয়ার্ড লিস্ট ---
ADULT_KEYWORDS = ["erotic", "porn", "sexy", "nudity", "adult", "18+", "uncut", "kink", "sex", "brazzers", "web series"]

# গুগল বটের জন্য একটি সেফ ইমেজ (এটি গুগল দেখবে)
SAFE_PLACEHOLDER = "https://i.ibb.co/L9hV1nB/18-plus-warning.png"

def is_content_adult(data):
    if data.get('adult') is True or data.get('force_adult') is True:
        return True
    
    title = (data.get("title") or data.get("name") or "").lower()
    overview = (data.get("overview") or "").lower()
    
    for word in ADULT_KEYWORDS:
        if word in title or word in overview:
            return True
    return False

# ইউআরএল এনকোড করার ফাংশন
def encode_b64(text):
    return base64.b64encode(text.encode()).decode()

# --- 🛡️ SAFETY UI (CSS & JS) ---
def get_safety_shield_code(is_adult):
    if not is_adult:
        return "" 

    return f"""
    <style>
        /* ব্লার কন্টেইনার স্টাইল */
        .nsfw-masked {{
            position: relative !important;
            overflow: hidden !important;
            cursor: pointer !important;
            background: #000 !important;
            min-height: 200px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        /* ইমেজ ব্লার এবং হাইড */
        .nsfw-masked img {{
            filter: blur(60px) !important;
            opacity: 0.3 !important;
            transition: 0.5s ease-in-out !important;
        }}
        /* ওপরে টেক্সট লেয়ার */
        .nsfw-masked::after {{
            content: "🔞 18+ CONTENT\\nClick to Reveal";
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.7);
            color: #ff5252; display: flex; align-items: center; justify-content: center;
            text-align: center; font-weight: bold; font-size: 16px;
            white-space: pre; z-index: 5; transition: 0.3s;
            border: 2px solid #ff5252;
        }}
        /* আনলক হওয়ার পর স্টাইল */
        .nsfw-unmasked img {{
            filter: blur(0px) !important;
            opacity: 1 !important;
        }}
        .nsfw-unmasked::after {{
            opacity: 0 !important;
            visibility: hidden !important;
        }}
    </style>
    <script>
        function revealNSFW(el) {{
            // কন্টেইনারের ভেতরের সব ইমেজ খুঁজে বের করা
            const imgs = el.querySelectorAll('img');
            imgs.forEach(img => {{
                const encodedUrl = img.getAttribute('data-src');
                if (encodedUrl) {{
                    // Base64 ডিকোড করে আসল ইমেজ সেট করা
                    img.src = atob(encodedUrl);
                    img.removeAttribute('data-src');
                }}
            }});
            el.classList.add('nsfw-unmasked');
            el.onclick = null; // একবার ক্লিক করলে ফাংশন বন্ধ
        }}
    </script>
    <div style="margin-top: 50px; padding: 20px; background: rgba(255,255,255,0.02); border-top: 1px solid #333; font-size: 12px; color: #777; text-align: justify; line-height: 1.6;">
        <b>DMCA Disclaimer:</b> This website is a metadata portal. We do not host any copyrighted files. All content is for educational purposes.
        <center><br><a href="https://t.me/CineZoneBD1" style="color:#E50914; text-decoration:none;">Report / DMCA Request</a></center>
    </div>
    """

# ==========================================================
# 🔥 MONKEY PATCH: HTML GENERATOR (SECURE CLOAKING)
# ==========================================================

if not hasattr(__main__, 'shield_old_html'):
    __main__.shield_old_html = __main__.generate_html_code

def safety_shield_generator(data, links, user_ads, owner_ads, share):
    is_adult = is_content_adult(data)
    # ১. অরিজিনাল HTML জেনারেট করা
    html = __main__.shield_old_html(data, links, user_ads, owner_ads, share)
    
    if is_adult:
        # ২. রেজেক্স (Regex) ব্যবহার করে ইমেজের src পাল্টে দেওয়া
        # এটি পোস্টার এবং স্ক্রিনশট উভয় ক্ষেত্রেই কাজ করবে
        
        def secure_img_tags(match):
            full_tag = match.group(0)
            img_src = match.group(1)
            
            # যদি ইমেজটি অলরেডি টেলিগ্রাম বাটন না হয় (BTN_TELEGRAM এড়িয়ে যাওয়া)
            if "photo-2025-12-23" in img_src:
                return full_tag
            
            encoded_url = encode_b64(img_src)
            # আসল src এ সেফ ইমেজ দেওয়া হচ্ছে, আর data-src এ এনকোড করা আসল লিংক
            return f'src="{SAFE_PLACEHOLDER}" data-src="{encoded_url}"'

        # ইমেজ ট্যাগ খুঁজে রিপ্লেস করা
        html = re.sub(r'src="([^"]+)"', secure_img_tags, html)

        # ৩. কন্টেইনারে ক্লিক ফাংশন এবং মাস্কিং ক্লাস যোগ করা
        if '<div class="info-poster">' in html:
            html = html.replace(
                '<div class="info-poster">', 
                '<div class="info-poster nsfw-masked" onclick="revealNSFW(this)">'
            )
        
        if '<div class="screenshot-grid">' in html:
            html = html.replace(
                '<div class="screenshot-grid">', 
                '<div class="screenshot-grid nsfw-masked" onclick="revealNSFW(this)">'
            )
            
        # যদি অন্য কোনো DIV থাকে যেখানে ইমেজ ব্লার করা দরকার (যেমন manual posters)
        html = html.replace('<div class="nsfw-container" onclick="revealNSFW(this)">', '<div class="nsfw-container nsfw-masked" onclick="revealNSFW(this)">')

    # ৪. সিএসএস এবং জেএস কোড যুক্ত করা
    safety_code = get_safety_shield_code(is_adult)
    return f"{html}\n{safety_code}"

__main__.generate_html_code = safety_shield_generator

async def register(bot):
    print("🛡️ Advanced Safety Shield (Base64 Cloaking) Plugin: Activated!")

print("✅ Safety Shield Plugin with Google Bypass Loaded!")
