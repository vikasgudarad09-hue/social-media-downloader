import yt_dlp
import re
import os
from typing import Dict, Any, Optional

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

def get_cookie_file_path() -> Optional[str]:
    """Check for cookies file in standard locations, or write from YOUTUBE_COOKIES_TEXT env var."""
    # 1. If cookie text is provided directly via environment variable (ideal for Render / Cloud hosting)
    cookies_text = os.environ.get("YOUTUBE_COOKIES_TEXT") or os.environ.get("COOKIES_TEXT")
    if cookies_text and len(cookies_text.strip()) > 10:
        env_cookie_file = os.path.join(os.path.dirname(__file__), "..", "runtime_cookies.txt")
        try:
            with open(env_cookie_file, "w", encoding="utf-8") as f:
                f.write(cookies_text.strip())
            return env_cookie_file
        except Exception:
            pass

    # 2. Check for path specified in env
    env_path = os.environ.get("COOKIES_FILE") or os.environ.get("YOUTUBE_COOKIES_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    
    # 3. Check candidate file paths
    candidate_paths = [
        "cookies.txt",
        "backend/cookies.txt",
        "../cookies.txt",
        os.path.join(os.path.dirname(__file__), "..", "cookies.txt"),
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            return path
    return None

def get_platform_headers(platform: str) -> Dict[str, str]:
    """Get optimized HTTP headers for specific platforms to minimize bot blocking."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    if platform == "Instagram":
        headers['Referer'] = 'https://www.instagram.com/'
        headers['User-Agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
    elif platform == "TikTok":
        headers['Referer'] = 'https://www.tiktok.com/'
    elif platform == "X (Twitter)":
        headers['Referer'] = 'https://x.com/'
    elif platform == "Facebook":
        headers['Referer'] = 'https://www.facebook.com/'
    elif platform == "Reddit":
        headers['User-Agent'] = 'python:social-media-downloader:v1.0.0 (by /u/JPMediaSaver)'
    elif platform == "Pinterest":
        headers['Referer'] = 'https://www.pinterest.com/'

    return headers

def extract_media_info(url: str) -> Dict[str, Any]:
    """
    Extracts video metadata and direct downloadable links using yt-dlp across all supported platforms.
    Includes robust fallback strategies for bot-detection and platform-specific restrictions.
    """
    platform = detect_platform(url)
    cookie_file = get_cookie_file_path()

    base_opts: Dict[str, Any] = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': False,
        'format': 'best/bestvideo+bestaudio/all',
        'socket_timeout': 15,
        'js_runtimes': {'node': {}},
        'http_headers': get_platform_headers(platform),
    }

    if cookie_file:
        base_opts['cookiefile'] = cookie_file

    # Platform specific strategy fallbacks
    strategies = [None]
    if platform == "YouTube":
        strategies = [
            ['ios', 'android', 'mweb'],
            ['android', 'web'],
            ['tv', 'mweb'],
        ]
    elif platform in ("Instagram", "TikTok", "Facebook"):
        strategies = [None, "mobile_ua_fallback"]

    last_exception = None

    for strategy in strategies:
        ydl_opts = base_opts.copy()

        if platform == "YouTube" and isinstance(strategy, list):
            ydl_opts['extractor_args'] = {
                'youtube': {
                    'player_client': strategy,
                }
            }
        elif strategy == "mobile_ua_fallback":
            ydl_opts['http_headers']['User-Agent'] = (
                'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36'
            )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info is None:
                    raise ValueError("Could not extract info from URL")

                # Handle playlists or multi-video entries
                if 'entries' in info and info['entries']:
                    info = info['entries'][0]

                title = info.get('title') or f"{platform} Content"
                thumbnail = info.get('thumbnail') or (info.get('thumbnails')[-1].get('url') if info.get('thumbnails') else None)
                duration = info.get('duration') or 0
                duration_str = format_duration(duration)

                # Find best video & audio links
                video_url = info.get('url')
                audio_url = None
                
                extracted_formats = []
                raw_formats = info.get('formats') or []

                for fmt in raw_formats:
                    fmt_url = fmt.get('url')
                    if not fmt_url:
                        continue

                    vcodec = fmt.get('vcodec', 'none')
                    acodec = fmt.get('acodec', 'none')
                    ext = fmt.get('ext', 'mp4')
                    res = fmt.get('resolution') or f"{fmt.get('width', '')}x{fmt.get('height', '')}"
                    if res == "x" or not res:
                        res = fmt.get('format_note', 'Standard')

                    filesize = format_filesize(fmt.get('filesize') or fmt.get('filesize_approx'))

                    if vcodec == 'none' and acodec != 'none' and not audio_url:
                        audio_url = fmt_url

                    extracted_formats.append({
                        "format_id": str(fmt.get('format_id', '')),
                        "ext": ext,
                        "resolution": res,
                        "filesize_approx": filesize,
                        "url": fmt_url,
                        "vcodec": vcodec,
                        "acodec": acodec
                    })

                # If direct video url is missing, pick best progressive (video+audio) format or best format overall
                if not video_url and extracted_formats:
                    combined_formats = [f for f in extracted_formats if f["vcodec"] != "none" and f["acodec"] != "none"]
                    if combined_formats:
                        video_url = combined_formats[-1]["url"]
                    else:
                        video_url = extracted_formats[-1]["url"]

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
                    "formats": extracted_formats[:10],
                    "error": None
                }

        except Exception as e:
            last_exception = e
            err_msg = str(e).lower()
            # If not a block/bot error, don't keep retrying
            if not any(k in err_msg for k in ["sign in", "bot", "confirm", "login", "cookie", "rate limit", "429"]):
                break

    # Format user-friendly error messages if extraction failed
    error_str = str(last_exception) if last_exception else "Extraction failed"
    if "sign in" in error_str.lower() or "login" in error_str.lower() or "bot" in error_str.lower():
        error_str = f"{platform} requires authentication or cookies to access this link. If this is a private or age-restricted post, add a cookies.txt file to the backend."

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
        "error": error_str
    }


