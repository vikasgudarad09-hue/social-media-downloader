import yt_dlp
import re
import os
from typing import Dict, Any, Optional

# ─────────────────────────────────────────────
# Platform detection
# ─────────────────────────────────────────────
def detect_platform(url: str) -> str:
    url_lower = url.lower()
    if "instagram.com" in url_lower or "instagr.am" in url_lower:
        return "Instagram"
    elif "tiktok.com" in url_lower:
        return "TikTok"
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "YouTube"
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        return "X (Twitter)"
    elif "facebook.com" in url_lower or "fb.watch" in url_lower:
        return "Facebook"
    elif "pinterest.com" in url_lower or "pin.it" in url_lower:
        return "Pinterest"
    elif "reddit.com" in url_lower or "redd.it" in url_lower:
        return "Reddit"
    else:
        return "Social Media"

# ─────────────────────────────────────────────
# Formatters
# ─────────────────────────────────────────────
def format_duration(seconds: Optional[int]) -> str:
    if not seconds or seconds <= 0:
        return "N/A"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def format_filesize(bytes_val: Optional[int]) -> Optional[str]:
    if not bytes_val:
        return None
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"

# ─────────────────────────────────────────────
# Build yt-dlp options per platform
# ─────────────────────────────────────────────
def build_ydl_opts(platform: str) -> Dict[str, Any]:
    """
    Return yt-dlp opts tuned for each platform.
    YouTube uses the tv_embedded + android client to bypass bot detection
    on cloud server IPs — no cookies required.
    """
    base = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': False,
        'socket_timeout': 20,
        'retries': 3,
        'ignoreerrors': False,
    }

    if platform == "YouTube":
        base.update({
            'extractor_args': {
                'youtube': {
                    'player_client': ['tv_embedded', 'android', 'web'],
                    'skip': ['webpage'],
                }
            },
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'http_headers': {
                'User-Agent': 'com.google.android.youtube/19.09.37 (Linux; U; Android 11) gzip',
                'Accept-Language': 'en-US,en;q=0.9',
            },
        })

    elif platform == "TikTok":
        base.update({
            'format': 'best[ext=mp4]/best',
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36'
                ),
                'Referer': 'https://www.tiktok.com/',
                'Accept-Language': 'en-US,en;q=0.9',
            },
            'extractor_args': {
                'tiktok': {
                    'api_hostname': 'api22-normal-c-alisg.tiktokv.com',
                }
            },
        })

    elif platform == "Instagram":
        base.update({
            'format': 'best[ext=mp4]/best',
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) '
                    'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 '
                    'Mobile/15E148 Safari/604.1'
                ),
                'Referer': 'https://www.instagram.com/',
                'Accept-Language': 'en-US,en;q=0.9',
            },
        })

    elif platform == "X (Twitter)":
        base.update({
            'format': 'best[ext=mp4]/best',
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
                ),
                'Referer': 'https://x.com/',
                'Accept-Language': 'en-US,en;q=0.9',
            },
        })

    elif platform == "Facebook":
        base.update({
            'format': 'best[ext=mp4]/best',
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
                ),
                'Referer': 'https://www.facebook.com/',
                'Accept-Language': 'en-US,en;q=0.9',
            },
        })

    elif platform == "Reddit":
        base.update({
            'format': 'best[ext=mp4]/best',
            'http_headers': {
                'User-Agent': 'python:social-media-downloader:v1.0.0 (by /u/JPMediaSaver)',
                'Accept-Language': 'en-US,en;q=0.9',
            },
        })

    elif platform == "Pinterest":
        base.update({
            'format': 'best[ext=mp4]/best',
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
                ),
                'Referer': 'https://www.pinterest.com/',
                'Accept-Language': 'en-US,en;q=0.9',
            },
        })

    else:
        base.update({
            'format': 'best[ext=mp4]/best',
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
                ),
                'Accept-Language': 'en-US,en;q=0.9',
            },
        })

    return base

# ─────────────────────────────────────────────
# Main extractor
# ─────────────────────────────────────────────
def extract_media_info(url: str) -> Dict[str, Any]:
    """
    Extract video metadata and direct download links for all supported platforms.
    Uses yt-dlp with platform-specific client spoofing to bypass bot detection.
    """
    platform = detect_platform(url)
    ydl_opts = build_ydl_opts(platform)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if info is None:
                raise ValueError("Could not extract info from URL")

            # Handle playlist / search results
            if 'entries' in info and info['entries']:
                info = info['entries'][0]

            title = info.get('title') or f"{platform} Video"

            # Best thumbnail
            thumbnail = info.get('thumbnail')
            if not thumbnail and info.get('thumbnails'):
                thumbnail = info['thumbnails'][-1].get('url')

            duration = info.get('duration') or 0
            duration_str = format_duration(duration)

            # Build format list (filter out storyboards/MHTML)
            raw_formats = info.get('formats') or []
            extracted_formats = []
            video_url = None
            audio_url = None

            for fmt in raw_formats:
                fmt_url = fmt.get('url')
                if not fmt_url:
                    continue

                ext = fmt.get('ext', 'mp4')
                format_id = str(fmt.get('format_id', ''))

                # Skip storyboard / preview sprite formats
                if ext.lower() in ['mhtml', 'sb'] or format_id.startswith('sb') or 'storyboard' in format_id.lower():
                    continue

                vcodec = fmt.get('vcodec', 'none')
                acodec = fmt.get('acodec', 'none')

                # Resolution string
                res = fmt.get('resolution')
                if not res or res == 'none':
                    w = fmt.get('width')
                    h = fmt.get('height')
                    if w and h:
                        res = f"{w}x{h}"
                    else:
                        res = fmt.get('format_note', 'Standard')

                filesize = format_filesize(fmt.get('filesize') or fmt.get('filesize_approx'))

                # Track best video and audio URLs
                if vcodec != 'none' and not video_url:
                    video_url = fmt_url
                if vcodec == 'none' and acodec != 'none' and not audio_url:
                    audio_url = fmt_url

                extracted_formats.append({
                    "format_id": format_id,
                    "ext": ext,
                    "resolution": res,
                    "filesize_approx": filesize,
                    "url": fmt_url,
                    "vcodec": vcodec,
                    "acodec": acodec,
                })

            # Fallback: use info-level URL
            if not video_url:
                video_url = info.get('url') or (extracted_formats[-1]["url"] if extracted_formats else None)

            return {
                "success": True,
                "url": url,
                "platform": platform,
                "title": title,
                "thumbnail": thumbnail,
                "duration": duration,
                "duration_formatted": duration_str,
                "video_url": video_url,
                "audio_url": audio_url or video_url,
                "formats": extracted_formats[-10:],
                "error": None,
            }

    except Exception as e:
        err_msg = str(e)

        lower_err = err_msg.lower()
        if any(w in lower_err for w in [
            "sign in", "bot", "confirm", "login", "empty media response",
            "ip address", "blocked", "http error 403", "http error 429",
            "precondition", "unavailable", "private video", "age",
        ]):
            err_msg = "Unable to extract this video. The platform may be blocking server requests. Try a different video."
        elif "unsupported url" in lower_err:
            err_msg = "This URL is not supported. Please paste a direct video link."
        elif "video unavailable" in lower_err or "this video is not available" in lower_err:
            err_msg = "This video is unavailable or has been removed."

        return {
            "success": False,
            "url": url,
            "platform": platform,
            "title": "Extraction Failed",
            "thumbnail": None,
            "duration": 0,
            "duration_formatted": "00:00",
            "video_url": None,
            "audio_url": None,
            "formats": [],
            "error": err_msg,
        }
