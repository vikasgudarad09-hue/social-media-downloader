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
    """Check for cookies file in standard locations, or write from YOUTUBE_COOKIES_TEXT / COOKIES_TEXT env var."""
    cookies_text = os.environ.get("YOUTUBE_COOKIES_TEXT") or os.environ.get("COOKIES_TEXT")
    if cookies_text and len(cookies_text.strip()) > 10:
        env_cookie_file = os.path.join(os.path.dirname(__file__), "..", "runtime_cookies.txt")
        try:
            raw_text = cookies_text.strip()
            if "\\n" in raw_text:
                raw_text = raw_text.replace("\\n", "\n")
            with open(env_cookie_file, "w", encoding="utf-8") as f:
                f.write(raw_text)
            return env_cookie_file
        except Exception:
            pass

    env_path = os.environ.get("YOUTUBE_COOKIES_PATH") or os.environ.get("COOKIES_FILE")
    if env_path and os.path.exists(env_path):
        return env_path
    
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
    """Get optimized HTTP headers for specific platforms to bypass bot detection."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    if platform == "Instagram":
        headers['Referer'] = 'https://www.instagram.com/'
        headers['User-Agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1'
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
    Extracts video metadata and direct downloadable links across all supported platforms.
    """
    platform = detect_platform(url)
    cookie_file = get_cookie_file_path()

    # 1. Primary engine for YouTube: pytubefix fallback
    if platform == "YouTube":
        try:
            from pytubefix import YouTube
            yt = YouTube(url)
            stream = yt.streams.filter(file_extension='mp4').order_by('resolution').desc().first()
            if not stream:
                stream = yt.streams.get_highest_resolution()

            if stream and stream.url:
                formats = []
                for s in yt.streams.filter(file_extension='mp4')[:10]:
                    if not getattr(s, 'url', None):
                        continue
                    formats.append({
                        "format_id": str(getattr(s, 'itag', '')),
                        "ext": "mp4",
                        "resolution": str(getattr(s, 'resolution', None) or "Standard"),
                        "filesize_approx": format_filesize(getattr(s, 'filesize', None)),
                        "url": s.url,
                        "vcodec": getattr(s, 'video_codec', 'h264'),
                        "acodec": getattr(s, 'audio_codec', 'aac')
                    })

                return {
                    "success": True,
                    "url": url,
                    "platform": platform,
                    "title": getattr(yt, 'title', 'YouTube Video') or "YouTube Video",
                    "thumbnail": getattr(yt, 'thumbnail_url', None),
                    "duration": getattr(yt, 'length', 0) or 0,
                    "duration_formatted": format_duration(getattr(yt, 'length', 0) or 0),
                    "video_url": stream.url,
                    "audio_url": stream.url,
                    "formats": formats,
                    "error": None
                }
        except Exception:
            pass

    # 2. Main engine: yt-dlp with platform headers & cookies
    ydl_opts: Dict[str, Any] = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': False,
        'format': 'best/bestvideo+bestaudio/all',
        'socket_timeout': 15,
        'http_headers': get_platform_headers(platform),
    }

    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if info is None:
                raise ValueError("Could not extract info from URL")

            if 'entries' in info and info['entries']:
                info = info['entries'][0]

            title = info.get('title') or f"{platform} Video"
            thumbnail = info.get('thumbnail') or (info.get('thumbnails')[-1].get('url') if info.get('thumbnails') else None)
            duration = info.get('duration') or 0
            duration_str = format_duration(duration)

            video_url = info.get('url')
            audio_url = None
            
            extracted_formats = []
            raw_formats = info.get('formats') or []

            for fmt in raw_formats:
                fmt_url = fmt.get('url')
                if not fmt_url:
                    continue

                ext = fmt.get('ext', 'mp4')
                format_id = str(fmt.get('format_id', ''))

                # Filter out mhtml storyboard images / preview sprites
                if ext.lower() in ['mhtml', 'sb'] or format_id.startswith('sb'):
                    continue

                vcodec = fmt.get('vcodec', 'none')
                acodec = fmt.get('acodec', 'none')
                res = fmt.get('resolution') or f"{fmt.get('width', '')}x{fmt.get('height', '')}"
                if res == "x":
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

            if not video_url and extracted_formats:
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
        err_msg = str(e)
        if any(w in err_msg.lower() for w in ["sign in", "bot", "confirm", "login"]):
            err_msg = "Unable to extract video at the moment. Please verify the URL and try again."

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
            "error": err_msg
        }
