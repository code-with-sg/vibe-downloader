# ==============================================================
# VibeDownloader — Backend (Flask + yt-dlp)
# SKY GRIT (SG) — FIXED VERSION with Cookie Support
# ==============================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import os

app = Flask(__name__)
CORS(app)

# ==============================================================
# COOKIES.TXT ka path
# Yeh file teri YouTube login cookies hold karti hai
# Iske bina YouTube "Sign in to confirm you're not a bot" error deta hai
# Neeche guide hai isko kaise banate hain
# ==============================================================
# Render Secret Files /etc/secrets/ mein store hoti hain
# /etc/secrets/ read-only hota hai Render pe
# Isliye /tmp/ mein save karte hain — yeh writable hota hai
COOKIES_FILE = '/tmp/cookies.txt'

# Render Secret File se directly padhte hain
SECRET_COOKIES = '/etc/secrets/cookies.txt'

if os.path.isfile(SECRET_COOKIES):
    # Secret file se /tmp/ mein copy karo
    import shutil
    shutil.copy(SECRET_COOKIES, COOKIES_FILE)
    print("✅ Cookies /etc/secrets/ se /tmp/ mein copy ki gayi")


def build_ydl_opts():
    """
    yt-dlp ke liye settings banata hai.
    Cookies file hai toh use karega, nahi hai toh bina cookies ke try karega.
    """
    # Check karo ki cookies file exist karti hai
    has_cookies = os.path.isfile(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0

    opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,   # Sirf info chahiye, file download nahi karni

        # --- Real Chrome browser jaisi headers ---
        # Yeh YouTube/Instagram ko lagta hai ki ek real browser request kar raha hai
        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/131.0.0.0 Safari/537.36'
            ),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': (
                'text/html,application/xhtml+xml,application/xml;'
                'q=0.9,image/avif,image/webp,*/*;q=0.8'
            ),
            'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
        },

        # --- YouTube specific settings ---
        'extractor_args': {
            'youtube': {
                # web + android dono try karega — zyada compatible
                'player_client': ['web', 'android'],
            },
            # Instagram ke liye
            'instagram': {
                'username': '',  # Optional: Instagram username daal sakte ho
            },
        },

        # Requests ke beech thoda wait — bot jaisa nahi lagega
        'sleep_interval': 1,
        'max_sleep_interval': 2,

        # Warnings suppress
        'ignoreerrors': False,
        'nocheckcertificate': False,
    }

    # Agar cookies file hai toh add karo
    if has_cookies:
        opts['cookiefile'] = COOKIES_FILE
        print(f"✅ Cookies file mili: {COOKIES_FILE}")
    else:
        print(f"⚠️  Cookies file nahi mili at: {COOKIES_FILE}")
        print("   YouTube Shorts ya age-restricted videos fail ho sakte hain.")
        print("   Cookies export karo — neeche README dekho.")

    return opts


@app.route('/api/info', methods=['POST'])
def get_media_info():
    """
    Frontend yahan POST request bhejta hai with { "url": "..." }
    Hum yt-dlp se info extract karke download links return karte hain.
    """

    data = request.get_json()

    if not data or 'url' not in data:
        return jsonify({'error': 'Koi URL nahi diya. URL paste karo aur dobara try karo.'}), 400

    video_url = data['url'].strip()

    if not video_url.startswith('http'):
        return jsonify({'error': 'Yeh valid URL nahi lagti. https:// se shuru honi chahiye.'}), 400

    print(f"\n🔍 Processing URL: {video_url}")

    try:
        ydl_opts = build_ydl_opts()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

        if not info:
            return jsonify({'error': 'Video info extract nahi ho paya. URL check karo.'}), 422

        # ==============================================================
        # Formats mein se sahi video/audio links nikalo
        # ==============================================================
        formats = info.get('formats', [])

        video_hd_url = None
        video_sd_url = None
        audio_url    = None

        # --- Best audio format dhundo ---
        audio_formats = [
            f for f in formats
            if f.get('vcodec') in ('none', None)
            and f.get('url')
            and f.get('ext') in ('m4a', 'mp4', 'webm', 'mp3', 'ogg', 'opus', 'mp4a')
        ]
        if not audio_formats:
            # Koi bhi audio format le lo
            audio_formats = [
                f for f in formats
                if f.get('acodec') and f.get('acodec') != 'none' and f.get('url')
                and not f.get('vcodec') or f.get('vcodec') == 'none'
            ]

        if audio_formats:
            audio_formats.sort(key=lambda f: f.get('abr', 0) or 0, reverse=True)
            audio_url = audio_formats[0].get('url')

        # --- Video formats dhundo ---
        # Pehle combined (video + audio dono) dhundo
        combined_formats = [
            f for f in formats
            if f.get('vcodec') and f.get('vcodec') != 'none'
            and f.get('acodec') and f.get('acodec') != 'none'
            and f.get('url')
        ]

        # Phir video-only formats
        video_only_formats = [
            f for f in formats
            if f.get('vcodec') and f.get('vcodec') != 'none'
            and f.get('url')
        ]

        usable = combined_formats if combined_formats else video_only_formats

        if usable:
            usable.sort(key=lambda f: f.get('height', 0) or 0, reverse=True)
            video_hd_url = usable[0].get('url')

            # SD: 480p ya usse kam
            sd_list = [f for f in usable if (f.get('height') or 999) <= 480]
            if sd_list:
                video_sd_url = sd_list[0].get('url')
            elif len(usable) > 1:
                video_sd_url = usable[-1].get('url')

        # Agar kuch bhi nahi mila
        if not video_hd_url and not audio_url:
            return jsonify({
                'error': (
                    'Koi download link nahi mila. Ho sakta hai:\n'
                    '• Video private hai\n'
                    '• Platform supported nahi hai\n'
                    '• Cookies expire ho gayi hain — dobara export karo'
                )
            }), 422

        # --- Duration format karo ---
        duration_secs = info.get('duration', 0) or 0
        duration_str = ''
        if duration_secs:
            mins, secs = divmod(int(duration_secs), 60)
            hours, mins = divmod(mins, 60)
            duration_str = f'{hours}:{mins:02d}:{secs:02d}' if hours else f'{mins}:{secs:02d}'

        result = {
            'error':        None,
            'title':        info.get('title', 'Untitled Media'),
            'thumbnail':    info.get('thumbnail', ''),
            'platform':     info.get('extractor_key', 'Unknown'),
            'duration':     duration_str,
            'uploader':     info.get('uploader', '') or info.get('channel', ''),
            'video_url':    video_hd_url,
            'video_sd_url': video_sd_url,
            'audio_url':    audio_url,
        }

        print(f"✅ Success: {result['title'][:50]}")
        return jsonify(result)

    except yt_dlp.utils.DownloadError as e:
        raw = str(e)
        print(f"❌ DownloadError: {raw}")

        # User-friendly error messages in Hinglish
        if 'Sign in' in raw or 'bot' in raw.lower() or 'confirm' in raw.lower():
            msg = (
                'YouTube ne bot detect kiya. '
                'Fix: cookies.txt file backend/ folder mein rakho. '
                'Neeche README mein guide hai.'
            )
        elif 'Private video' in raw or 'private' in raw.lower():
            msg = 'Yeh video private hai — public video ka link dalo.'
        elif 'not available' in raw.lower() or 'unavailable' in raw.lower():
            msg = 'Yeh video available nahi hai (deleted, region-blocked ya private ho sakta hai).'
        elif 'Unsupported URL' in raw:
            msg = 'Yeh platform supported nahi hai. YouTube, Instagram, TikTok, Facebook, X try karo.'
        elif 'instagram' in raw.lower() and ('login' in raw.lower() or 'cookie' in raw.lower()):
            msg = 'Instagram ke liye bhi cookies chahiye. Neeche guide dekho.'
        else:
            # Raw error clean karke dikhao
            clean = raw.replace('ERROR: ', '').replace('[youtube] ', '').replace('[download] ', '').strip()
            msg = f'Error: {clean[:300]}'

        return jsonify({'error': msg}), 422

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return jsonify({'error': f'Server error: {str(e)[:200]}'}), 500


@app.route('/health', methods=['GET'])
def health_check():
    has_cookies = os.path.isfile(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0
    return jsonify({
        'status': 'ok',
        'service': 'VibeDownloader — SKY GRIT',
        'cookies_loaded': has_cookies,
    })


@app.route('/api/cookies-status', methods=['GET'])
def cookies_status():
    """Frontend check kar sakta hai ki cookies loaded hain ya nahi"""
    has_cookies = os.path.isfile(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0
    return jsonify({
        'cookies_present': has_cookies,
        'path': COOKIES_FILE,
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n🚀 VibeDownloader backend starting on port {port}")
    print(f"🍪 Looking for cookies at: {COOKIES_FILE}")
    has_cookies = os.path.isfile(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0
    print(f"🍪 Cookies status: {'✅ Found' if has_cookies else '❌ Not found (YouTube may fail)'}")
    app.run(host='0.0.0.0', port=port, debug=False)