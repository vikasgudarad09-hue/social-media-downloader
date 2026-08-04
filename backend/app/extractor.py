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
            with open(env_cookie_file, "w", encoding="utf-8") as f:
                f.write(cookies_text.strip())
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

def extract_media_info(url: str) -> Dict[str, Any]:
    """
    Extracts video metadata and direct downloadable links using yt-dlp.
    Does NOT download files to disk.
    """
    ydl_opts: Dict[str, Any] = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': False,
        'format': 'best/bestvideo+bestaudio/all',
        'socket_timeout': 15,
    }

    cookie_file = get_cookie_file_path()
    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file

    platform = detect_platform(url)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if info is None:
                raise ValueError("Could not extract info from URL")

            # Handle playlists or single entry
            if 'entries' in info and info['entries']:
                info = info['entries'][0]

            title = info.get('title') or f"{platform} Video"
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

                # Capture audio-only stream if present
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

            # If no direct video url found in main info, grab highest quality format
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
                "formats": extracted_formats[:10], # Return top 10 format options
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
