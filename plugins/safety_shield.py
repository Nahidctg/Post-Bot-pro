# plugins/safety_shield.py
import __main__
import base64
import re

# --- ১. কনফিগারেশন ---
ADULT_KEYWORDS = [
    "erotic", "porn", "sexy", "nudity", "adult", "18+", "uncut", "kink", 
    "sex", "brazzers", "web series", "hot scenes", "softcore", "nsfw"
]

# গুগল বটের জন্য একটি সেফ ইমেজ
SAFE_PLACEHOLDER = "https://i.ibb.co/9TRmN8V/nsfw-placeholder.png"

# --- ২. গুগল বট ডিটেকশন ---
def is_google_bot():
    try:
        from flask import request
        ua = request.headers.get('User-Agent', '').lower()
        bots = ["googlebot", "bingbot", "yandexbot", "baiduspider", "slurp", "duckduckbot"]
        return any(bot in ua for bot in bots)
    except:
        return False

# --- ৩. অ্যাডাল্ট কন্টেন্ট চেক ---
def is_content_adult(data):
    if data.get('adult') is True or data.get('force_adult') is True:
        return True
    
    title = (data.get("title") or data.get("name") or "").lower()
    overview = (data.get("overview") or "").lower()
    
    for word in ADULT_KEYWORDS:
        if word in title or word in overview:
            return True
    return False

def encode_b64(text):
    return base64.b64encode(text.encode()).decode()

# --- ৪. আধুনিক ডিজাইন ও স্ক্রিপ্ট (Large View Fix) ---
def get_safety_shield_code(is_adult):
    if not is_adult:
        return "" 

    no_index = '<meta name="robots" content="noindex, nofollow, noarchive">' if is_adult else ""

    return f"""
    {no_index}
    <style>
        .nsfw-masked {{
            position: relative !important;
            overflow: hidden !important;
            cursor: pointer !important;
            border-radius: 12px;
            background: #111 !important;
            min-height: 250px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px solid rgba(255, 255, 255, 0.1);
            margin-bottom: 20px;
        }}
        .nsfw-masked img {{
            filter: blur(60px) grayscale(1) !important;
            opacity: 0.2 !important;
            transition: 0.5s ease !important;
            width: 100% !important;
            height: auto !important;
        }}
        .nsfw-overlay {{
            position: absolute; inset: 0;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(15px);
            display: flex; flex-direction: column;
            align-items: center; justify-content: center;
            z-index: 10; color: #fff; text-align: center;
        }}
        .nsfw-btn {{
            background: #ff4d4d; color: white; border: none;
            padding: 10px 20px; border-radius: 5px; font-weight: bold;
            margin-top: 10px; cursor: pointer; text-transform: uppercase;
        }}
        
        /* আনমাস্ক হওয়ার পর ছবি বড় দেখানোর জন্য */
        .nsfw-unmasked {{
            display: block !important;
            min-height: auto !important;
        }}
        .nsfw-unmasked img {{
            filter: none !important;
            opacity: 1 !important;
            width: 100% !important;
            height: auto !important;
            object-fit: contain !important;
            border-radius: 8px;
            margin-bottom: 15px;
        }}
        .screenshot-grid.nsfw-unmasked {{
            display: grid !important;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)) !important;
            gap: 15px;
        }}
        
        .dmca-footer {{
            margin-top: 40px; padding: 20px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 10px; border: 1px solid #333;
            font-size: 12px; color: #888; text-align: center;
        }}
    </style>
    <script>
        function revealNSFW(el) {{
            const imgs = el.querySelectorAll('img');
            imgs.forEach(img => {{
                const encodedUrl = img.getAttribute('data-raw');
                if (encodedUrl) {{
                    img.src = atob(encodedUrl);
                    img.removeAttribute('data-raw');
                }}
            }});
            el.classList.add('nsfw-unmasked');
            const overlay = el.querySelector('.nsfw-overlay');
            if(overlay) overlay.remove();
            el.onclick = null;
        }}
    </script>
    <div class="dmca-footer">
        <b>DMCA Disclaimer:</b> This website is a metadata portal. We do not host any copyrighted files. 
        <br><br>
        <a href="https://t.me/CineZoneBD1" style="color:#ff4d4d; text-decoration:none;">Report / DMCA Request</a>
    </div>
    """

# --- ৫. মেইন জেনারেটর (Logic Merging) ---
if not hasattr(__main__, 'shield_old_html'):
    __main__.shield_old_html = __main__.generate_html_code

def safety_shield_generator(data, links, user_ads, owner_ads, share):
    is_adult = is_content_adult(data)
    is_bot = is_google_bot()
    
    if is_adult and is_bot:
        data['title'] = "Restricted Content"
        data['overview'] = "This content is not available for preview due to safety policies."
        links = [] 

    html = __main__.shield_old_html(data, links, user_ads, owner_ads, share)
    
    if is_adult:
        def secure_img_tags(match):
            img_src = match.group(1)
            if any(x in img_src.lower() for x in ["logo", "icon", "telegram"]): return match.group(0)
            
            if is_bot:
                return f'src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"'
            
            encoded_url = encode_b64(img_src)
            return f'src="{SAFE_PLACEHOLDER}" data-raw="{encoded_url}"'

        html = re.sub(r'src="([^"]+)"', secure_img_tags, html)
        overlay_html = '<div class="nsfw-overlay"><div>🔞 18+ Content</div><button class="nsfw-btn">Reveal Content</button></div>'
        
        if '<div class="info-poster">' in html:
            html = html.replace('<div class="info-poster">', f'<div class="info-poster nsfw-masked" onclick="revealNSFW(this)">{overlay_html}')
        
        if '<div class="screenshot-grid">' in html:
            html = html.replace('<div class="screenshot-grid">', f'<div class="screenshot-grid nsfw-masked" onclick="revealNSFW(this)">{overlay_html}')

    return f"{html}\n{get_safety_shield_code(is_adult)}"

__main__.generate_html_code = safety_shield_generator

async def register(bot):
    print("🛡️ Safety Shield Original (Large View Fix) Activated!")
