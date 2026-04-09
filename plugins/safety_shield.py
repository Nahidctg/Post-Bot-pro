import __main__
import base64
import re

# --- ১. কনফিগারেশন ---
ADULT_KEYWORDS = [
    "erotic", "porn", "sexy", "nudity", "adult", "18+", "uncut", "kink", 
    "sex", "brazzers", "web series", "hot scenes", "softcore", "nsfw"
]

# ব্যাকআপ প্লেসহোল্ডার ইমেজ (ibb.co ডাউন থাকলে অন্যগুলো কাজ করবে)
SAFE_SOURCES = [
    "https://i.ibb.co/9TRmN8V/nsfw-placeholder.png",
    "https://images2.imgbox.com/5b/72/Z8pS7FQX_o.png",
    "https://pic8.co/a/240212/65ca0f2b842c1.png"
]

# --- ২. ডিটেকশন লজিক ---
def is_google_bot():
    try:
        from flask import request
        ua = request.headers.get('User-Agent', '').lower()
        bots = ["googlebot", "bingbot", "yandexbot", "baiduspider", "slurp", "duckduckbot"]
        return any(bot in ua for bot in bots)
    except:
        return False

def is_content_adult(data):
    # ম্যানুয়াল হোক বা অটো—যদি অ্যাডাল্ট কি-ওয়ার্ড থাকে তবে ট্রু হবে
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

# --- ৩. ১০০% গ্যারান্টিড ইমেজ রিকভারি স্ক্রিপ্ট (জাভাস্ক্রিপ্ট) ---
def get_safety_shield_code(is_adult):
    if not is_adult:
        return "" 

    sources_json = str(SAFE_SOURCES)
    return f"""
    <style>
        .nsfw-masked {{
            position: relative !important;
            display: inline-block !important; /* ইমেজ অনুযায়ী ছোট বড় হবে */
            width: 100% !important;
            overflow: hidden !important;
            cursor: pointer !important;
            background: #000 !important;
            border-radius: 10px;
            margin-bottom: 15px;
        }}
        .nsfw-masked img {{
            filter: blur(70px) grayscale(1) !important;
            opacity: 0.3 !important;
            width: 100% !important;
            height: auto !important;
            display: block !important;
            transition: 0.5s ease-in-out;
        }}
        .nsfw-unmasked img {{
            filter: blur(0px) grayscale(0) !important;
            opacity: 1 !important;
            box-shadow: 0 5px 25px rgba(0,0,0,0.8);
        }}
        .nsfw-overlay {{
            position: absolute; inset: 0;
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(12px);
            display: flex; flex-direction: column;
            align-items: center; justify-content: center;
            z-index: 10; color: #fff;
        }}
        .nsfw-btn {{
            background: #ff4d4d; color: #fff; border: none;
            padding: 10px 20px; border-radius: 50px; font-weight: bold;
            cursor: pointer; box-shadow: 0 4px 15px rgba(255, 77, 77, 0.4);
            text-transform: uppercase; font-size: 12px;
        }}
    </style>
    <script>
        const safeSources = {sources_json};
        
        // ইমেজ লোড না হলে ব্যাকআপ সোর্স ট্রাই করার ফাংশন
        function handlePlaceholderError(img) {{
            let idx = safeSources.indexOf(img.src);
            if (idx !== -1 && idx < safeSources.length - 1) {{
                img.src = safeSources[idx + 1];
            }}
        }}

        function revealNSFW(el) {{
            const img = el.querySelector('img');
            const encodedUrl = img.getAttribute('data-raw');
            if (encodedUrl) {{
                let rawUrl = atob(encodedUrl);
                // গুগল প্রক্সি ১০০% ইমেজ শো করাবে
                let proxyUrl = "https://images1-focus-opensocial.googleusercontent.com/gadgets/proxy?container=focus&refresh=2592000&url=" + encodeURIComponent(rawUrl);
                
                img.src = proxyUrl;
                img.removeAttribute('data-raw');
                
                img.onerror = function() {{
                    if (this.src !== rawUrl) this.src = rawUrl; // প্রক্সি ফেল করলে ডিরেক্ট লিঙ্ক
                }};
            }}
            el.classList.add('nsfw-unmasked');
            const overlay = el.querySelector('.nsfw-overlay');
            if(overlay) overlay.remove();
            el.onclick = null;
        }}
    </script>
    """

# --- ৪. মেইন জেনারেটর (ম্যানুয়াল ইমেজ অটো-র‍্যাপার সহ) ---
if not hasattr(__main__, 'shield_old_html'):
    __main__.shield_old_html = __main__.generate_html_code

def safety_shield_generator(data, links, user_ads, owner_ads, share):
    is_adult = is_content_adult(data)
    is_bot = is_google_bot()
    
    # বট প্রটেকশন
    if is_adult and is_bot:
        data['title'] = "Restricted Content"
        data['overview'] = "Safety policy active."
        links = [] 

    html = __main__.shield_old_html(data, links, user_ads, owner_ads, share)
    
    if is_adult:
        # এই ফাংশনটি প্রতিটি ইমেজ ট্যাগকে একটি মাস্ক করা ডিভ (DIV) এর ভেতরে ঢুকিয়ে দিবে
        # ফলে ম্যানুয়ালি আপলোড করা সব ইমেজ অটোমেটিক মাস্ক হয়ে যাবে
        def secure_img_tags(match):
            img_src = match.group(1)
            # আইকন বা ব্যানার হলে বাদ দিন
            if any(x in img_src.lower() for x in ["logo", "icon", "telegram", "banner"]): 
                return match.group(0)
            
            if is_bot:
                return 'src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"'
            
            encoded_url = encode_b64(img_src)
            overlay = '<div class="nsfw-overlay">🔞<button class="nsfw-btn">Reveal</button></div>'
            
            # প্রতিটি ইমেজকে একটি ক্লিকযোগ্য কন্টেইনারে র‍্যাপ (Wrap) করা হচ্ছে
            return f'''<div class="nsfw-masked" onclick="revealNSFW(this)">{overlay}<img src="{SAFE_SOURCES[0]}" data-raw="{encoded_url}" onerror="handlePlaceholderError(this)"></div>'''

        # HTML এর ভেতরে থাকা সব ইমেজ (img src) খুঁজে বের করে র‍্যাপ করা
        html = re.sub(r'<img [^>]*src="([^"]+)"[^>]*>', secure_img_tags, html)

    return f"{html}\n{get_safety_shield_code(is_adult)}"

__main__.generate_html_code = safety_shield_generator

async def register(bot):
    print("🛡️ Safety Shield 100% Manual & Auto Ready!")
