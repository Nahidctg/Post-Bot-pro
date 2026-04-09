import __main__
import base64
import re
import os
import requests
import logging

# --- ১. কনফিগারেশন ও লগিং ---
logger = logging.getLogger(__name__)
ADULT_KEYWORDS = [
    "erotic", "porn", "sexy", "nudity", "adult", "18+", "uncut", "kink", 
    "sex", "brazzers", "web series", "hot scenes", "softcore", "nsfw"
]

# ImgBB API Key (অবশ্যই .env ফাইলে IMGBB_API_KEY থাকতে হবে)
IMGBB_API_KEY = os.getenv("1821270072482fb07921cfd72d31c37e") 
SAFE_PLACEHOLDER = "https://i.ibb.co/9TRmN8V/nsfw-placeholder.png"

# --- ২. ইমেজ আপলোড ফিক্স (Server Fail সমাধান) ---
def improved_upload_core(file_content, is_bytes=False):
    """ImgBB (Primary) এবং Catbox (Fallback) ব্যবহারের মাধ্যমে আপলোড নিশ্চিত করা"""
    
    # ২.১ প্রথমে ImgBB-তে চেষ্টা করবে
    if IMGBB_API_KEY:
        try:
            url = "https://api.imgbb.com/1/upload"
            data = {"key": IMGBB_API_KEY}
            files = {"image": ("image.png", file_content)}
            resp = requests.post(url, data=data, files=files, timeout=15)
            if resp.status_code == 200:
                return resp.json()['data']['url']
        except Exception as e:
            logger.error(f"ImgBB Upload Failed: {e}")

    # ২.২ ImgBB ফেইল করলে Catbox-এ চেষ্টা করবে
    try:
        url = "https://catbox.moe/user/api.php"
        data = {"reqtype": "fileupload", "userhash": ""}
        files = {"fileToUpload": ("image.png", file_content)}
        resp = requests.post(url, data=data, files=files, timeout=15)
        if resp.status_code == 200:
            return resp.text.strip()
    except Exception as e:
        logger.error(f"Catbox Fallback Failed: {e}")

    return None

# মেইন বটের ফাংশনগুলোকে ওভাররাইড (Monkey Patching)
def patched_upload_to_catbox(file_path):
    try:
        with open(file_path, "rb") as f:
            return improved_upload_core(f.read())
    except: return None

def patched_upload_to_catbox_bytes(img_bytes):
    try:
        if hasattr(img_bytes, 'read'):
            img_bytes.seek(0)
            return improved_upload_core(img_bytes.read())
        return improved_upload_core(img_bytes)
    except: return None

# মেইন বটের ফাংশন রিপ্লেস করা
__main__.upload_to_catbox = patched_upload_to_catbox
__main__.upload_to_catbox_bytes = patched_upload_to_catbox_bytes
__main__.upload_image_core = improved_upload_core


# --- ৩. গুগল বট ডিটেকশন ---
def is_google_bot():
    try:
        from flask import request
        ua = request.headers.get('User-Agent', '').lower()
        bots = ["googlebot", "bingbot", "yandexbot", "baiduspider", "slurp", "duckduckbot"]
        return any(bot in ua for bot in bots)
    except:
        return False

# --- ৪. অ্যাডাল্ট কন্টেন্ট চেক ---
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

# --- ৫. আধুনিক ডিজাইন ও স্ক্রিপ্ট ---
def get_safety_shield_code(is_adult):
    if not is_adult:
        return "" 
    no_index = '<meta name="robots" content="noindex, nofollow, noarchive">'
    return f"""
    {no_index}
    <style>
        .nsfw-masked {{
            position: relative !important;
            overflow: hidden !important;
            cursor: pointer !important;
            border-radius: 12px;
            background: #000 !important;
            min-height: 280px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid rgba(255, 77, 77, 0.2);
            margin-bottom: 20px;
        }}
        .nsfw-masked img {{
            filter: blur(70px) grayscale(1) !important;
            opacity: 0.3 !important;
            transition: 0.5s ease-in-out !important;
            width: 100% !important;
            height: auto !important;
        }}
        .nsfw-unmasked {{ display: block !important; cursor: default !important; background: transparent !important; border: none !important; }}
        .nsfw-unmasked img {{ filter: blur(0px) grayscale(0) !important; opacity: 1 !important; width: 100% !important; border-radius: 8px; box-shadow: 0 5px 15px rgba(0,0,0,0.5); }}
        .nsfw-overlay {{ position: absolute; inset: 0; background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(20px); display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 100; color: #fff; text-align: center; padding: 20px; }}
        .nsfw-btn {{ background: #ff4d4d; color: white; border: none; padding: 12px 24px; border-radius: 50px; font-weight: bold; margin-top: 15px; cursor: pointer; text-transform: uppercase; }}
        .dmca-footer {{ margin-top: 40px; padding: 20px; background: rgba(255, 255, 255, 0.03); border-radius: 10px; border: 1px solid #333; font-size: 12px; color: #888; text-align: center; }}
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
    """

# --- ৬. মেইন জেনারেটর (Logic Merging) ---
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
            if any(x in img_src.lower() for x in ["logo", "icon", "telegram", "banner"]): 
                return match.group(0)
            if is_bot:
                return f'src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"'
            encoded_url = encode_b64(img_src)
            return f'src="{SAFE_PLACEHOLDER}" data-raw="{encoded_url}"'

        html = re.sub(r'src="([^"]+)"', secure_img_tags, html)
        overlay_html = '<div class="nsfw-overlay"><div>🔞 Adult Content</div><button class="nsfw-btn">Reveal Content</button></div>'
        
        # বিভিন্ন সেকশনে মাস্কিং অ্যাপ্লাই
        targets = ['<div class="info-poster">', '<div class="screenshot-grid">', '<div class="screenshots">']
        for target in targets:
            if target in html:
                html = html.replace(target, f'{target[:-1]} nsfw-masked" onclick="revealNSFW(this)">{overlay_html}')

    return f"{html}\n{get_safety_shield_code(is_adult)}"

__main__.generate_html_code = safety_shield_generator

async def register(bot):
    print("🛡️ Safety Shield + 🚀 Stable Uploader Plugin Activated!")
