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

# --- ৪. আধুনিক ডিজাইন ও স্ক্রিপ্ট (Premium UI + Anti-Blur Logic) ---
def get_safety_shield_code(is_adult):
    if not is_adult:
        return "" 

    # গুগল বটকে ইনডেক্স করতে বাধা দেওয়া
    no_index = '<meta name="robots" content="noindex, nofollow, noarchive">' if is_adult else ""

    return f"""
    {no_index}
    <style>
        /* মাস্ক করা অবস্থায় স্টাইল */
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

        /* আনমাস্ক বা রিভিল করার পর স্টাইল (আপনার স্ক্রিনশট বড় দেখানোর জন্য) */
        .nsfw-unmasked {{
            display: block !important;
            min-height: auto !important;
            cursor: default !important;
            background: transparent !important;
            border: none !important;
        }}
        .nsfw-unmasked img {{
            filter: blur(0px) grayscale(0) !important;
            opacity: 1 !important;
            width: 100% !important; /* ইমেজ ফুল উইডথ হবে */
            height: auto !important; /* ইমেজের রেশিও ঠিক থাকবে */
            object-fit: contain !important;
            border-radius: 8px;
            margin-bottom: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.5);
        }}

        /* স্ক্রিনশট গ্রিড যদি থাকে তবে সেটিকে সুন্দর করা */
        .screenshot-grid.nsfw-unmasked {{
            display: grid !important;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)) !important; /* স্ক্রিনশট বড় দেখাবে */
            gap: 15px !important;
            padding: 10px 0;
        }}

        /* ওভারলে ডিজাইন */
        .nsfw-overlay {{
            position: absolute; inset: 0;
            background: rgba(0, 0, 0, 0.85);
            backdrop-filter: blur(20px);
            display: flex; flex-direction: column;
            align-items: center; justify-content: center;
            z-index: 100; color: #fff; text-align: center;
            padding: 20px;
        }}
        .nsfw-btn {{
            background: #ff4d4d; color: white; border: none;
            padding: 12px 24px; border-radius: 50px; font-weight: bold;
            margin-top: 15px; cursor: pointer; text-transform: uppercase;
            box-shadow: 0 4px 15px rgba(255, 77, 77, 0.4);
            font-size: 14px;
            transition: 0.3s;
        }}
        .nsfw-btn:hover {{
            background: #ff3333;
            transform: scale(1.05);
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
    
    # গুগল বটের জন্য স্টিলথ মোড
    if is_adult and is_bot:
        data['title'] = "Restricted Content"
        data['overview'] = "This content is not available for preview due to safety policies."
        links = [] # বটকে ডাউনলোড লিঙ্ক দেখাবেন না

    html = __main__.shield_old_html(data, links, user_ads, owner_ads, share)
    
    if is_adult:
        # ইমেজ রিপ্লেসমেন্ট (বট এবং ইউজারের জন্য আলাদা)
        def secure_img_tags(match):
            img_src = match.group(1)
            # লোগো বা টেলিগ্রাম আইকন হলে মাস্ক করার দরকার নেই
            if any(x in img_src.lower() for x in ["logo", "icon", "telegram", "banner"]): 
                return match.group(0)
            
            if is_bot:
                # বটকে একদম ব্ল্যাঙ্ক ইমেজ দিন
                return f'src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"'
            
            encoded_url = encode_b64(img_src)
            return f'src="{SAFE_PLACEHOLDER}" data-raw="{encoded_url}"'

        html = re.sub(r'src="([^"]+)"', secure_img_tags, html)

        # ওভারলে UI অ্যাড করা
        overlay_html = '<div class="nsfw-overlay"><div>🔞 Adult Content</div><button class="nsfw-btn">Reveal Screenshots & Poster</button></div>'
        
        # পোস্টার এবং স্ক্রিনশট সেকশনে মাস্কিং অ্যাপ্লাই
        if '<div class="info-poster">' in html:
            html = html.replace('<div class="info-poster">', f'<div class="info-poster nsfw-masked" onclick="revealNSFW(this)">{overlay_html}')
        
        if '<div class="screenshot-grid">' in html:
            html = html.replace('<div class="screenshot-grid">', f'<div class="screenshot-grid nsfw-masked" onclick="revealNSFW(this)">{overlay_html}')
        
        # যদি আপনার থিমে অন্য কোন ক্লাসে স্ক্রিনশট থাকে (যেমন: 'screenshots')
        if '<div class="screenshots">' in html:
            html = html.replace('<div class="screenshots">', f'<div class="screenshots nsfw-masked" onclick="revealNSFW(this)">{overlay_html}')

    return f"{html}\n{get_safety_shield_code(is_adult)}"

__main__.generate_html_code = safety_shield_generator

async def register(bot):
    print("🛡️ All-in-One Safety Shield (Stealth + Premium Large UI) Activated!")
