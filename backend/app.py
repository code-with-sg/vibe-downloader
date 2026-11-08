# ==============================================================
# VibeDownloader — Backend (Flask + yt-dlp)
# SKY GRIT (SG)
#
# HOW THIS WORKS (Beginner Explanation):
# ----------------------------------------
# Flask is a lightweight Python "web server framework".
# Think of it like a receptionist: it listens for incoming
# requests from our frontend, processes them, and sends back
# a response.
#
# yt-dlp is a powerful command-line tool (also a Python library)
# that can extract video/audio info and direct download links
# from 1000+ websites without hitting any API limits.
# ==============================================================

from flask import Flask, request, jsonify
from flask_cors import CORS   # Allows our frontend to talk to this backend
import yt_dlp                 # The core download engine
import os

# --- Create the Flask app ---
# __name__ just tells Flask where to look for files
app = Flask(__name__)

# --- Enable CORS ---
# CORS = "Cross-Origin Resource Sharing"
# Without this, browsers block requests from one domain to another.
# Example: your frontend at vibedownloader.netlify.app CAN'T talk
# to your backend at vibedownloader.onrender.com without CORS enabled.
CORS(app)


# ==============================================================
# ROUTE: /api/info
# This is the main endpoint our frontend calls.
# A "route" is like a specific door in your server.
# POST means: the frontend is SENDING us data (the URL).
# ==============================================================
@app.route('/api/info', methods=['POST'])
def get_media_info():
    """
    Expects JSON body: { "url": "https://..." }
    Returns:  {
        "title": "...",
        "thumbnail": "...",
        "video_url": "...",       ← best quality video
        "video_sd_url": "...",    ← lower quality video
        "audio_url": "...",       ← mp3 audio only
        "platform": "...",
        "duration": "...",
        "error": null
    }
    """

    # --- Read the JSON body the frontend sent us ---
    # request.get_json() parses the incoming JSON string
    # into a Python dictionary (like a JS object)
    data = request.get_json()

    if not data or 'url' not in data:
        # If no URL was sent, return a 400 "bad request" error
        return jsonify({'error': 'No URL provided'}), 400

    video_url = data['url'].strip()

    # Basic URL validation
    if not video_url.startswith('http'):
        return jsonify({'error': 'Invalid URL. Must start with http:// or https://'}), 400

    try:
        # ==============================================================
        # STEP A: Use yt-dlp to extract video information
        # We use yt_dlp.YoutubeDL as a Python library (not command line)
        # 'ydl_opts' is a dictionary of settings we pass to yt-dlp
        # ==============================================================
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
            # Yeh headers add karne se yt-dlp ek real browser ki tarah behave karega aur bot-detection bypass hogi
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
            }
        }

        # --- Extract full video info ---
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # extract_info() is the main yt-dlp function.
            # download=False means "get info only, don't download the file"
            info = ydl.extract_info(video_url, download=False)

        # ==============================================================
        # STEP B: Pick the right video/audio formats from the results
        #
        # yt-dlp returns a list of "formats" — each format is a
        # different quality/codec combination available for the video.
        # We need to pick the best ones for HD video, SD video, and audio.
        # ==============================================================

        formats = info.get('formats', [])

        video_hd_url = None   # Will hold 1080p or best video URL
        video_sd_url = None   # Will hold 480p/360p URL
        audio_url    = None   # Will hold audio-only URL

        # --- Find the best audio-only format ---
        # We filter formats that have no video stream (vcodec == 'none')
        # and pick the one with the highest audio bitrate (abr)
        audio_formats = [
            f for f in formats
            if f.get('vcodec') == 'none'
            and f.get('url')
            and f.get('ext') in ('m4a', 'mp4', 'webm', 'mp3', 'ogg', 'opus')
        ]
        if audio_formats:
            # Sort by audio bitrate descending → best quality first
            audio_formats.sort(key=lambda f: f.get('abr', 0) or 0, reverse=True)
            audio_url = audio_formats[0].get('url')

        # --- Find the best video formats ---
        # We filter formats that HAVE a video stream and also have audio
        # (combined formats are easiest to use as direct download links)
        combined_formats = [
            f for f in formats
            if f.get('vcodec') != 'none'
            and f.get('acodec') != 'none'   # has audio too
            and f.get('url')
        ]

        # Also check for video-only formats (some sites separate video+audio)
        video_only_formats = [
            f for f in formats
            if f.get('vcodec') != 'none'
            and f.get('acodec') == 'none'
            and f.get('url')
        ]

        # Prefer combined formats; fall back to video-only
        usable_video_formats = combined_formats if combined_formats else video_only_formats

        if usable_video_formats:
            # Sort by height (resolution) descending → 1080p first
            usable_video_formats.sort(
                key=lambda f: f.get('height', 0) or 0,
                reverse=True
            )

            # HD = highest resolution available
            video_hd_url = usable_video_formats[0].get('url')

            # SD = find something around 480p or lower
            # We look for height <= 480
            sd_candidates = [f for f in usable_video_formats if (f.get('height', 999) or 999) <= 480]
            if sd_candidates:
                video_sd_url = sd_candidates[0].get('url')
            elif len(usable_video_formats) > 1:
                # If no 480p exists, use the second-best quality
                video_sd_url = usable_video_formats[-1].get('url')

        # If nothing was found at all, return an error
        if not video_hd_url and not audio_url:
            return jsonify({'error': 'Could not extract any download links for this URL. The video may be private or the platform may not be supported.'}), 422

        # ==============================================================
        # STEP C: Build and return our clean response object
        # jsonify() converts a Python dict → JSON string for the frontend
        # ==============================================================

        # Format duration from seconds → "MM:SS" or "HH:MM:SS"
        duration_secs = info.get('duration', 0) or 0
        duration_str = ''
        if duration_secs:
            mins, secs = divmod(int(duration_secs), 60)
            hours, mins = divmod(mins, 60)
            if hours:
                duration_str = f'{hours}:{mins:02d}:{secs:02d}'
            else:
                duration_str = f'{mins}:{secs:02d}'

        return jsonify({
            'error':        None,
            'title':        info.get('title', 'Untitled Media'),
            'thumbnail':    info.get('thumbnail', ''),
            'platform':     info.get('extractor_key', 'Unknown'),
            'duration':     duration_str,
            'uploader':     info.get('uploader', ''),
            'video_url':    video_hd_url,
            'video_sd_url': video_sd_url,
            'audio_url':    audio_url,
        })

    except yt_dlp.utils.DownloadError as e:
        # yt-dlp throws DownloadError for things like private videos,
        # geo-restricted content, or unsupported URLs
        err_msg = str(e).replace('[youtube]', '').replace('[download]', '').strip()
        return jsonify({'error': f'Could not process this URL: {err_msg}'}), 422

    except Exception as e:
        # Catch any other unexpected errors
        print(f'Unexpected error: {e}')
        return jsonify({'error': 'An unexpected server error occurred. Please try again.'}), 500


# ==============================================================
# ROUTE: /health
# A simple "ping" endpoint. Used by Render.com to check
# if your server is alive and running.
# ==============================================================
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'service': 'VibeDownloader — SKY GRIT'})


# ==============================================================
# START THE SERVER
# When you run `python app.py`, this block executes.
# host='0.0.0.0' means "listen on all network interfaces"
# (required for Render/cloud hosting)
# port reads from environment variable (Render sets this automatically)
# or defaults to 5000 for local testing
# ==============================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)