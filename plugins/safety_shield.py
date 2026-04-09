import __main__
import base64
import re

# --- ১. কনফিগারেশন ---
ADULT_KEYWORDS = [
    "erotic", "porn", "sexy", "nudity", "adult", "18+", "uncut", "kink", 
    "sex", "brazzers", "web series", "hot scenes", "softcore", "nsfw"
]

# একাধিক ব্যাকআপ প্লেসহোল্ডার (একটি ডাউন থাকলে অন্যটি অটোমেটিক কাজ করবে)
SAFE_SOURCES = [
    "https://i.ibb.co/9TRmN8V/nsfw-placeholder.png",
    "https://images2.imgbox.com/5b/72/Z8pS7FQX_o.png",
    "https://pic8.co/a/240212/65ca0f2b842c1.png"
]

# --- ২. গুগল বট ডিটেকশন ---
def is_google_bot():
    try:
        from flask import request
        ua = request.headers.get('User-Agent', '').lower()
        bots = ["googlebot", "bingbot", "yandexbot", "baiduspider", "slurp", "duckduckbot"]
        return any(bot in ua for bot in bots)
    except:
        return False

# --- ৩. অ্যাডাল্ট কন্টেন্ট চেক লজিক ---
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

# --- ৪. আধুনিক ডিজাইন ও মাল্টি-সোর্স ইমেজ রিকভারি স্ক্রিপ্ট ---
def get_safety_shield_code(is_adult):
    if not is_adult:
        return "" 

    no_index = '<meta name="robots" content="noindex, nofollow, noarchive">' if is_adult else ""
    sources_json = str(SAFE_SOURCES)

    return f"""
    {no_index}
    <style>
        /* মাস্ক করা অবস্থায় ডিজাইন */
        .nsfw-masked {{
            position: relative !important;
            overflow: hidden !important;
            cursor: pointer !important;
            border-radius: 12px;
            background: #0b0b0b !important;
            min-height: 280px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid rgba(255, 77, 77, 0.15);
            margin-bottom: 20px;
        }}
        .nsfw-masked img {{
            filter: blur(75px) grayscale(1) !important;
            opacity: 0.3 !important;
            transition: 0.6s ease-in-out !important;
            width: 100% !important;
            height: auto !important;
        }}

        /* আনমাস্ক বা রিভিল করার পর ডিজাইন */
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
            width: 100% !important;
            height: auto !important;
            object-fit: contain !important;
            border-radius: 8px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.7);
        }}

        /* স্ক্রিনশট গ্রিড বড় দেখানোর জন্য */
        .screenshot-grid.nsfw-unmasked {{
            display: grid !important;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)) !important;
            gap: 15px !important;
        }}

        /* ওভারলে UI ডিজাইন */
        .nsfw-overlay {{
            position: absolute; inset: 0;
            background: rgba(0, 0, 0, 0.82);
            backdrop-filter: blur(15px);
            display: flex; flex-direction: column;
            align-items: center; justify-content: center;
            z-index: 100; color: #fff; text-align: center;
            padding: 20px;
        }}
        .nsfw-btn {{
            background: linear-gradient(135deg, #ff4d4d, #b30000);
            color: white; border: none;
            padding: 14px 28px; border-radius: 50px; font-weight: bold;
            margin-top: 15px; cursor: pointer; text-transform: uppercase;
            box-shadow: 0 5px 20px rgba(255, 77, 77, 0.4);
            transition: 0.3s ease;
            font-size: 13px;
        }}
        .nsfw-btn:hover {{
            transform: scale(1.05);
            filter: brightness(1.2);
        }}
        .dmca-footer {{
            margin-top: 40px; padding: 20px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 10px; border: 1px solid #222;
            font-size: 12px; color: #666; text-align: center;
        }}
    </style>

    <script>
        const safeSources = {sources_json};

        // প্লেসহোল্ডার ইমেজ ফেইলওভার ফাংশন
        function handlePlaceholderError(img) {{
            let currentSrc = img.src;
            let index = safeSources.indexOf(currentSrc);
            if (index !== -1 && index < safeSources.length - 1) {{
                img.src = safeSources[index + 1];
            }} else {{
                img.onerror = null;
                img.src = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=";
            }}
        }}

        function revealNSFW(el) {{
            const imgs = el.querySelectorAll('img');
            imgs.forEach(img => {{
                const encodedUrl = img.getAttribute('data-raw');
                if (encodedUrl) {{
                    let rawUrl = atob(encodedUrl);
                    
                    // সিস্টেম ১: গুগল প্রক্সি দিয়ে লোড করার চেষ্টা (সার্ভার ডাউন থাকলেও ছবি দেখাবে)
                    let proxyUrl = "https://images1-focus-opensocial.googleusercontent.com/gadgets/proxy?container=focus&refresh=2592000&url=" + encodeURIComponent(rawUrl);
                    
                    img.src = proxyUrl;
                    img.removeAttribute('data-raw');
                    
                    // সিস্টেম ২: গুগল প্রক্সি কাজ না করলে অরিজিনাল লিঙ্ক ট্রাই করো
                    img.onerror = function() {{
                        if (this.src !== rawUrl) {{
                            this.src = rawUrl;
                        } else {{
                            // সিস্টেম ৩: সব ফেল করলে প্লেসহোল্ডার দেখাও
                            this.src = safeSources[0];
                            this.onerror = function() {{ handlePlaceholderError(this); }};
                        }
                    }};
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

# --- ৫. মেইন জেনারেটর (অরিজিনাল কোডের সাথে ইন্টিগ্রেশন) ---
if not hasattr(__main__, 'shield_old_html'):
    __main__.shield_old_html = __main__.generate_html_code

def safety_shield_generator(data, links, user_ads, owner_ads, share):
    is_adult = is_content_adult(data)
    is_bot = is_google_bot()
    
    # গুগল বটের জন্য স্টিলথ মোড
    if is_adult and is_bot:
        data['title'] = "Content Restricted"
        data['overview'] = "Preview unavailable for safety policy reasons."
        links = [] 

    html = __main__.shield_old_html(data, links, user_ads, owner_ads, share)
    
    if is_adult:
        # সব ইমেজ ট্যাগ মাস্ক করা এবং রিকভারি হ্যান্ডলার বসানো
        def secure_img_tags(match):
            img_src = match.group(1)
            # লোগো, আইকন বা টেলিগ্রাম ব্যানার হলে মাস্ক করার দরকার নেই
            if any(x in img_src.lower() for x in ["logo", "icon", "telegram", "banner"]): 
                return match.group(0)
            
            if is_bot:
                # বটকে ব্ল্যাঙ্ক ইমেজ দাও
                return 'src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"'
            
            encoded_url = encode_b64(img_src)
            # ডিফল্টভাবে ব্যাকআপ প্লেসহোল্ডার দেখাবে
            return f'src="{SAFE_SOURCES[0]}" data-raw="{encoded_url}" onerror="handlePlaceholderError(this)"'

        html = re.sub(r'src="([^"]+)"', secure_img_tags, html)

        # ওভারলে UI অ্যাড করা
        overlay_html = '<div class="nsfw-overlay"><div>🔞 Adult Content Content</div><button class="nsfw-btn">Reveal Content</button></div>'
        
        # থিমের ক্লাস অনুযায়ী মাস্কিং অ্যাপ্লাই
        target_classes = ['info-poster', 'screenshot-grid', 'screenshots', 'post-content img']
        for cls in target_classes:
            tag = f'class="{cls}"'
            if tag in html:
                # ক্লাস আপডেট এবং ক্লিক ফাংশন এড
                html = html.replace(tag, f'class="{cls} nsfw-masked" onclick="revealNSFW(this)"')
                # ওভারলে ইনজেক্ট করা (একবার)
                search_str = f'class="{cls} nsfw-masked" onclick="revealNSFW(this)">'
                if search_str in html:
                    html = html.replace(search_str, search_str + overlay_html)

    return f"{html}\n{get_safety_shield_code(is_adult)}"

__main__.generate_html_code = safety_shield_generator

async def register(bot):
    print("🛡️ All-in-One Safety Shield (Google Proxy + Multi-Recovery) Activated!")
