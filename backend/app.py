# ==============================================================
# VibeDownloader — Backend (Flask + yt-dlp)
# SKY GRIT (SG) — FINAL WORKING VERSION
# ==============================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import os
import shutil
import re

app = Flask(__name__)
CORS(app)

# Cookies path
COOKIES_FILE = '/tmp/cookies.txt'
SECRET_COOKIES = '/etc/secrets/cookies.txt'

# Startup pe cookies copy karo
if os.path.isfile(SECRET_COOKIES):
    shutil.copy(SECRET_COOKIES, COOKIES_FILE)
    print("✅ Cookies /etc/secrets/ se /tmp/ mein copy ki gayi")


def clean_youtube_url(url):
    """
    Koi bhi YouTube URL format ko clean karta hai.
    
    Supported formats:
    - https://youtube.com/shorts/ABC123?si=xyz     (Shorts share link)
    - https://youtu.be/ABC123?si=xyz               (Short share link)
    - https://www.youtube.com/watch?v=ABC123       (Normal video)
    - https://youtube.com/watch?v=ABC123&list=xyz  (Playlist link)
    - https://m.youtube.com/watch?v=ABC123         (Mobile link)
    """
    
    # YouTube Shorts
    shorts_match = re.search(r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})', url)
    if shorts_match:
        video_id = shorts_match.group(1)
        return f'https://www.youtube.com/watch?v={video_id}'
    
    # youtu.be short links
    youtu_be_match = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', url)
    if youtu_be_match:
        video_id = youtu_be_match.group(1)
        return f'https://www.youtube.com/watch?v={video_id}'
    
    # Normal YouTube watch links — sirf v= parameter rakhte hain
    watch_match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url)
    if watch_match:
        video_id = watch_match.group(1)
        return f'https://www.youtube.com/watch?v={video_id}'
    
    # Koi YouTube format nahi mila — URL as-is return karo
    return url


def build_ydl_opts():
    has_cookies = os.path.isfile(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0

    opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,

        # Best available format — koi restriction nahi
        # best = video+audio combined
        # bestvideo+bestaudio = alag alag best quality
        'format': 'best/bestvideo+bestaudio',

        # Real Chrome browser headers
        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/131.0.0.0 Safari/537.36'
            ),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        },

        'sleep_interval': 1,
        'max_sleep_interval': 2,
        'ignoreerrors': False,
    }

    if has_cookies:
        opts['cookiefile'] = COOKIES_FILE
        print(f"✅ Cookies loaded")
    else:
        print(f"⚠️ Cookies nahi mili")

    return opts


@app.route('/api/info', methods=['POST'])
def get_media_info():
    data = request.get_json()

    if not data or 'url' not in data:
        return jsonify({'error': 'URL nahi diya. Paste karo aur try karo.'}), 400

    raw_url = data['url'].strip()

    if not raw_url.startswith('http'):
        return jsonify({'error': 'Valid URL nahi hai. https:// se shuru honi chahiye.'}), 400

    # YouTube URLs clean karo — ?si= aur extra params hata do
    video_url = clean_youtube_url(raw_url)
    print(f"\n🔍 Original URL: {raw_url}")
    print(f"🔗 Cleaned URL:  {video_url}")

    try:
        ydl_opts = build_ydl_opts()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

        if not info:
            return jsonify({'error': 'Video info nahi mila. URL check karo.'}), 422

        formats = info.get('formats', [])

        video_hd_url = None
        video_sd_url = None
        audio_url = None

        # --- Audio formats ---
        audio_formats = [
            f for f in formats
            if f.get('vcodec') in ('none', None)
            and f.get('acodec') and f.get('acodec') != 'none'
            and f.get('url')
        ]
        if audio_formats:
            audio_formats.sort(key=lambda f: f.get('abr', 0) or 0, reverse=True)
            audio_url = audio_formats[0].get('url')

        # --- Video formats ---
        # Pehle combined dhundo (video + audio dono)
        combined = [
            f for f in formats
            if f.get('vcodec') and f.get('vcodec') != 'none'
            and f.get('acodec') and f.get('acodec') != 'none'
            and f.get('url')
        ]

        # Nahi mila toh video-only
        video_only = [
            f for f in formats
            if f.get('vcodec') and f.get('vcodec') != 'none'
            and f.get('url')
        ]

        usable = combined if combined else video_only

        if usable:
            usable.sort(key=lambda f: f.get('height', 0) or 0, reverse=True)
            video_hd_url = usable[0].get('url')

            # SD: 480p ya usse kam
            sd_list = [f for f in usable if (f.get('height') or 999) <= 480]
            if sd_list:
                video_sd_url = sd_list[0].get('url')
            elif len(usable) > 1:
                video_sd_url = usable[-1].get('url')

        # Agar audio bhi nahi mila toh info ka url try karo
        if not video_hd_url and not audio_url:
            direct_url = info.get('url')
            if direct_url:
                video_hd_url = direct_url
            else:
                return jsonify({
                    'error': 'Download link nahi mila. Video private ya unavailable ho sakta hai.'
                }), 422

        # Duration format
        duration_secs = info.get('duration', 0) or 0
        duration_str = ''
        if duration_secs:
            mins, secs = divmod(int(duration_secs), 60)
            hours, mins = divmod(mins, 60)
            duration_str = f'{hours}:{mins:02d}:{secs:02d}' if hours else f'{mins}:{secs:02d}'

        result = {
            'error': None,
            'title': info.get('title', 'Untitled Media'),
            'thumbnail': info.get('thumbnail', ''),
            'platform': info.get('extractor_key', 'Unknown'),
            'duration': duration_str,
            'uploader': info.get('uploader', '') or info.get('channel', ''),
            'video_url': video_hd_url,
            'video_sd_url': video_sd_url,
            'audio_url': audio_url,
        }

        print(f"✅ Success: {result['title'][:60]}")
        return jsonify(result)

    except yt_dlp.utils.DownloadError as e:
        raw = str(e)
        print(f"❌ Error: {raw}")

        if 'Sign in' in raw or 'bot' in raw.lower():
            msg = 'YouTube ne bot detect kiya. Cookies refresh karo.'
        elif 'private' in raw.lower():
            msg = 'Yeh video private hai.'
        elif 'not available' in raw.lower() or 'unavailable' in raw.lower():
            msg = 'Video available nahi hai — deleted, private ya region blocked ho sakta hai.'
        elif 'Unsupported URL' in raw:
            msg = 'Yeh platform supported nahi hai.'
        elif 'format' in raw.lower():
            msg = 'Video format extract nahi hua. Dobara try karo.'
        else:
            clean = raw.replace('ERROR: ', '').strip()
            msg = f'{clean[:250]}'

        return jsonify({'error': msg}), 422

    except Exception as e:
        print(f"❌ Unexpected: {e}")
        return jsonify({'error': f'Server error: {str(e)[:200]}'}), 500


@app.route('/health', methods=['GET'])
def health_check():
    has_cookies = os.path.isfile(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0
    return jsonify({
        'status': 'ok',
        'service': 'VibeDownloader — SKY GRIT',
        'cookies_loaded': has_cookies,
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n🚀 VibeDownloader starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)