# plugins/safety_shield.py
import __main__

# --- 🔞 ১৮+ মুভি চেনার জন্য কিওয়ার্ড লিস্ট ---
ADULT_KEYWORDS = ["erotic", "porn", "sexy", "nudity", "adult", "18+", "uncut", "kink", "sex"]

def is_content_adult(data):
    if data.get('adult') is True or data.get('force_adult') is True:
        return True
    
    title = (data.get("title") or data.get("name") or "").lower()
    overview = (data.get("overview") or "").lower()
    
    for word in ADULT_KEYWORDS:
        if word in title or word in overview:
            return True
    return False

# --- 🛡️ SAFETY UI (CSS & JS) ---
def get_safety_shield_code(is_adult):
    if not is_adult:
        return "" # ১৮+ না হলে কোনো কোড এড হবে না

    return """
    <style>
        /* ব্লার কন্টেইনার স্টাইল */
        .nsfw-masked {
            position: relative !important;
            overflow: hidden !important;
            cursor: pointer !important;
        }
        /* শুধু ইমেজ ব্লার হবে */
        .nsfw-masked img {
            filter: blur(50px) !important;
            transition: 0.4s ease-in-out !important;
        }
        /* ওপরে টেক্সট লেয়ার */
        .nsfw-masked::after {
            content: "🔞 18+ CONTENT\\nClick to Reveal";
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.8);
            color: #ff5252; display: flex; align-items: center; justify-content: center;
            text-align: center; font-weight: bold; font-size: 14px;
            white-space: pre; z-index: 5; transition: 0.3s;
            border: 1px solid #ff5252; border-radius: inherit;
        }
        /* আনলক হওয়ার পর স্টাইল */
        .nsfw-unmasked img {
            filter: blur(0px) !important;
        }
        .nsfw-unmasked::after {
            opacity: 0 !important;
            visibility: hidden !important;
        }
    </style>
    <script>
        function revealNSFW(el) {
            el.classList.add('nsfw-unmasked');
        }
    </script>
    <div style="margin-top: 50px; padding: 20px; background: rgba(255,255,255,0.02); border-top: 1px solid #333; font-size: 12px; color: #777; text-align: justify; line-height: 1.6;">
        <b>DMCA Disclaimer:</b> This website is a metadata portal. We do not host any copyrighted files. All content is for educational purposes.
        <center><br><a href="https://t.me/CineZoneBD1" style="color:#E50914; text-decoration:none;">Report / DMCA Request</a></center>
    </div>
    """

# ==========================================================
# 🔥 MONKEY PATCH: HTML GENERATOR (STRUCTURE SAFE)
# ==========================================================

if not hasattr(__main__, 'shield_old_html'):
    __main__.shield_old_html = __main__.generate_html_code

def safety_shield_generator(data, links, user_ads, owner_ads, share):
    is_adult = is_content_adult(data)
    # ১. অরিজিনাল HTML জেনারেট করা
    html = __main__.shield_old_html(data, links, user_ads, owner_ads, share)
    
    if is_adult:
        # ২. পোস্টার সেকশনে ক্লাস ঢুকিয়ে দেওয়া (কোনো নতুন DIV যোগ করা হচ্ছে না)
        if '<div class="info-poster">' in html:
            html = html.replace(
                '<div class="info-poster">', 
                '<div class="info-poster nsfw-masked" onclick="revealNSFW(this)">'
            )
        
        # ৩. স্ক্রিনশট গ্রিডে ক্লাস ঢুকিয়ে দেওয়া
        if '<div class="screenshot-grid">' in html:
            html = html.replace(
                '<div class="screenshot-grid">', 
                '<div class="screenshot-grid nsfw-masked" onclick="revealNSFW(this)">'
            )

    # ৪. সিএসএস এবং জেএস কোড যুক্ত করা
    safety_code = get_safety_shield_code(is_adult)
    return f"{html}\n{safety_code}"

__main__.generate_html_code = safety_shield_generator

async def register(bot):
    print("🛡️ Safety Shield & Adult Blur Plugin: Activated Safely!")

print("✅ Safety Shield Plugin Loaded Successfully!")
