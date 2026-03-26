# plugins/seo_and_timer.py
import __main__
import json

# --- 🏷️ SEO KEYWORDS GENERATOR ---
def generate_seo_tags(data):
    title = data.get("title") or data.get("name")
    year = (data.get("release_date") or data.get("first_air_date") or "----")[:4]
    lang = data.get('custom_language', 'Dual Audio')
    genres = ", ".join([g['name'] for g in data.get('genres', [])])
    
    # কিওয়ার্ড লিস্ট তৈরি
    tags = [
        f"{title} Full Movie Download", f"{title} {year} Dual Audio", 
        f"{title} {lang} Download", f"{title} HD 1080p", 
        f"{title} Blogger Code", f"Download {title} Movie",
        f"{genres} Movies {year}", "CineZoneBD1 Movies", "Banglaflix4k"
    ]
    return ", ".join(tags)

# --- ⏳ GLOWING ANIMATED TIMER UI ---
def get_animated_timer_js():
    return """
    <script>
    function startUnlock(btn, type) {
        // ১. অ্যাড লিংক ওপেন করা (যাতে ইনকাম মিস না হয়)
        let randomAd = AD_LINKS[Math.floor(Math.random() * AD_LINKS.length)];
        window.open(randomAd, '_blank'); 
        
        // ২. বাটন এনিমেশন শুরু
        btn.disabled = true;
        btn.style.position = 'relative';
        btn.style.overflow = 'hidden';
        
        // বাটনের ভেতরে লোডার সেট করা
        btn.innerHTML = `
            <span style="position:relative; z-index:2;">⏳ GENERATING SECURE LINK...</span>
            <div id="glow-bar" style="position:absolute; bottom:0; left:0; height:100%; width:0%; background:rgba(255,255,255,0.2); transition: width 5s linear; z-index:1;"></div>
        `;

        let timeLeft = 5;
        let timer = setInterval(function() {
            timeLeft--;
            if (timeLeft < 0) {
                clearInterval(timer);
                // ৩. আনলক হয়ে প্লেয়ার/লিঙ্ক দেখানো
                document.getElementById('view-details').style.display = 'none';
                document.getElementById('view-links').style.display = 'block';
                window.scrollTo({top: 0, behavior: 'smooth'});
            }
        }, 1000);

        // গ্লোয়িং বার এনিমেশন স্টার্ট
        setTimeout(() => { document.getElementById('glow-bar').style.width = '100%'; }, 50);
    }
    </script>
    <style>
    /* গ্লোয়িং বার ইফেক্ট */
    #glow-bar {
        box-shadow: inset 0 0 20px rgba(255,255,255,0.5);
    }
    .main-btn:disabled {
        filter: brightness(0.8);
        cursor: not-allowed;
    }
    </style>
    """

# ==========================================================
# 🔥 MONKEY PATCH: INJECTOR
# ==========================================================

# ১. মেইন HTML জেনারেটর আপডেট করা (টাইমারের জন্য)
original_html_func = __main__.generate_html_code

def enhanced_timer_generator(data, links, user_ads, owner_ads, share):
    html = original_html_func(data, links, user_ads, owner_ads, share)
    
    # এনিমেটেড টাইমার স্ক্রিপ্ট ইনজেক্ট করা
    timer_code = get_animated_timer_js()
    
    # যদি আগে কোনো টাইমার স্ক্রিপ্ট থাকে তবে তা সরিয়ে এটি বসাবে
    import re
    html = re.sub(r'<script>.*?function startUnlock.*?</script>', timer_code, html, flags=re.DOTALL)
    
    return html

__main__.generate_html_code = enhanced_timer_generator

# ২. মেইন ক্যাপশন জেনারেটর আপডেট করা (SEO কিওয়ার্ড এর জন্য)
original_caption_func = __main__.generate_formatted_caption

def seo_caption_generator(data, pid=None):
    caption = original_caption_func(data, pid)
    
    # কিওয়ার্ড জেনারেট করা
    seo_tags = generate_seo_tags(data)
    
    # ক্যাপশনের নিচে কিওয়ার্ড সেকশন যোগ করা
    seo_text = f"\n\n🏷️ **SEO Labels (Copy for Blogger):**\n`{seo_tags}`"
    
    return caption + seo_text

__main__.generate_formatted_caption = seo_caption_generator

async def register(bot):
    print("🚀 SEO Tags & Animated Timer: Activated!")

print("✅ SEO & Timer Plugin Loaded Successfully!")
