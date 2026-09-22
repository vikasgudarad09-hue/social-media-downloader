import yt_dlp
import re
import os
import urllib.request
import urllib.error
import json
from typing import Dict, Any, Optional, List

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
# YouTube Video ID extractor
# ─────────────────────────────────────────────
def extract_youtube_id(url: str) -> Optional[str]:
    patterns = [
        r'(?:v=|/)([0-9A-Za-z_-]{11})',
        r'youtu\.be/([0-9A-Za-z_-]{11})',
        r'embed/([0-9A-Za-z_-]{11})',
        r'shorts/([0-9A-Za-z_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

# ─────────────────────────────────────────────
# Simple HTTP GET helper
# ─────────────────────────────────────────────
def http_get_json(url: str, timeout: int = 8) -> Optional[Dict]:
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; MediaBot/1.0)',
                'Accept': 'application/json',
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode('utf-8'))
    except Exception:
        pass
    return None

# ─────────────────────────────────────────────
# Piped API — YouTube proxy (no sign-in needed)
# ─────────────────────────────────────────────
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.adminforge.de",
    "https://pipedapi.darkness.services",
    "https://piped-api.garudalinux.org",
    "https://api.piped.projectsegfau.lt",
]

def try_piped(video_id: str) -> Optional[Dict[str, Any]]:
    for instance in PIPED_INSTANCES:
        data = http_get_json(f"{instance}/streams/{video_id}")
        if data and not data.get('error') and data.get('title'):
            return data
    return None

# ─────────────────────────────────────────────
# Invidious API — secondary YouTube fallback
# Uses official health API to get live instances
# ─────────────────────────────────────────────

# Hardcoded high-uptime instances (fallback if health API fails)
INVIDIOUS_INSTANCES = [
    "https://invidious.f5.si",       # 99.5% uptime
    "https://invidious.nerdvpn.de",  # 99%+ uptime
    "https://inv.nadeko.net",
    "https://invidious.privacyredirect.com",
    "https://invidious.perennialte.ch",
    "https://iv.ggtyler.dev",
    "https://invidious.einfachzocken.eu",
    "https://yt.artemislena.eu",
]

_dynamic_instances: Optional[List[str]] = None

def get_invidious_instances() -> List[str]:
    """Fetch live instance list from Invidious health API, fall back to hardcoded list."""
    global _dynamic_instances
    if _dynamic_instances:
        return _dynamic_instances
    try:
        data = http_get_json("https://api.invidious.io/instances.json?sort_by=health", timeout=5)
        if data and isinstance(data, list):
            instances = []
            for item in data:
                if isinstance(item, list) and len(item) >= 2:
                    info = item[1]
                    uri = info.get('uri', '')
                    monitor = info.get('monitor', {})
                    # Only use https instances that are up and have API enabled
                    if (uri.startswith('https') and
                            not monitor.get('down', True) and
                            info.get('api') is not False):
                        instances.append(uri)
                        if len(instances) >= 6:
                            break
            if instances:
                _dynamic_instances = instances
                return instances
    except Exception:
        pass
    return INVIDIOUS_INSTANCES

def try_invidious(video_id: str) -> Optional[Dict[str, Any]]:
    instances = get_invidious_instances()
    for instance in instances:
        data = http_get_json(
            f"{instance}/api/v1/videos/{video_id}?fields=title,videoThumbnails,lengthSeconds,adaptiveFormats,formatStreams"
        )
        if data and 'title' in data:
            return data
    return None

def parse_piped_response(data: Dict, video_id: str, url: str) -> Dict[str, Any]:
    title = data.get('title', 'YouTube Video')
    duration = data.get('duration', 0)
    thumbnail = data.get('thumbnailUrl') or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    formats = []
    video_url = None
    audio_url = None

    # videoStreams = combined or video-only streams
    for s in data.get('videoStreams', []):
        stream_url = s.get('url')
        if not stream_url:
            continue
        quality = s.get('quality', 'Standard')
        ext = 'mp4' if 'mp4' in s.get('mimeType', 'mp4') else 'webm'
        formats.append({
            "format_id": s.get('itag', quality),
            "ext": ext,
            "resolution": quality,
            "filesize_approx": None,
            "url": stream_url,
            "vcodec": "h264",
            "acodec": "aac" if not s.get('videoOnly') else "none",
        })
        if not video_url and not s.get('videoOnly'):
            video_url = stream_url

    # audioStreams = audio-only
    for s in data.get('audioStreams', []):
        stream_url = s.get('url')
        if not stream_url:
            continue
        if not audio_url:
            audio_url = stream_url

    # If all videoStreams are videoOnly, pick first one
    if not video_url and formats:
        video_url = formats[0]['url']

    return {
        "success": True,
        "url": url,
        "platform": "YouTube",
        "title": title,
        "thumbnail": thumbnail,
        "duration": duration,
        "duration_formatted": format_duration(duration),
        "video_url": video_url,
        "audio_url": audio_url or video_url,
        "formats": formats[:10],
        "error": None,
    }

# ─────────────────────────────────────────────
# Invidious API — secondary YouTube fallback
# ─────────────────────────────────────────────
INVIDIOUS_INSTANCES = [
    "https://invidious.nerdvpn.de",
    "https://iv.datura.network",
    "https://invidious.privacydev.net",
    "https://yt.cdaut.de",
    "https://invidious.fdn.fr",
    "https://invidious.lunar.icu",
]

def try_invidious(video_id: str) -> Optional[Dict[str, Any]]:
    for instance in INVIDIOUS_INSTANCES:
        data = http_get_json(
            f"{instance}/api/v1/videos/{video_id}?fields=title,videoThumbnails,lengthSeconds,adaptiveFormats,formatStreams"
        )
        if data and 'title' in data:
            return data
    return None

def parse_invidious_response(data: Dict, video_id: str, url: str) -> Dict[str, Any]:
    title = data.get('title', 'YouTube Video')
    duration = data.get('lengthSeconds', 0)

    thumbs = data.get('videoThumbnails', [])
    thumbnail = None
    for t in thumbs:
        if t.get('quality') in ('maxres', 'sddefault', 'high'):
            thumbnail = t.get('url')
            break
    if not thumbnail:
        thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    formats = []
    video_url = None
    audio_url = None

    for fmt in data.get('formatStreams', []):
        u = fmt.get('url')
        if not u:
            continue
        res = fmt.get('resolution', fmt.get('qualityLabel', 'Standard'))
        formats.append({
            "format_id": str(fmt.get('itag', '')),
            "ext": "mp4",
            "resolution": res,
            "filesize_approx": None,
            "url": u,
            "vcodec": "h264",
            "acodec": "aac",
        })
        if not video_url:
            video_url = u

    for fmt in data.get('adaptiveFormats', []):
        u = fmt.get('url')
        if not u:
            continue
        mime = fmt.get('type', '')
        is_audio = mime.startswith('audio/')
        if is_audio and not audio_url:
            audio_url = u

    return {
        "success": True,
        "url": url,
        "platform": "YouTube",
        "title": title,
        "thumbnail": thumbnail,
        "duration": duration,
        "duration_formatted": format_duration(duration),
        "video_url": video_url,
        "audio_url": audio_url or video_url,
        "formats": formats[:10],
        "error": None,
    }

# ─────────────────────────────────────────────
# Build yt-dlp options per platform
# ─────────────────────────────────────────────
def build_ydl_opts(platform: str) -> Dict[str, Any]:
    base = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': False,
        'socket_timeout': 12,
        'retries': 2,
        'ignoreerrors': False,
    }

    if platform == "YouTube":
        base.update({
            'extractor_args': {
                'youtube': {
                    'player_client': ['mweb', 'web', 'android', 'ios'],
                }
            },
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'geo_bypass': True,
        })
    elif platform == "Instagram":
        base.update({
            'format': 'best[ext=mp4]/best',
        })
    elif platform == "TikTok":
        base.update({
            'format': 'best[ext=mp4]/best',
            'extractor_args': {'tiktok': {'api_hostname': 'api22-normal-c-alisg.tiktokv.com'}},
        })
    else:
        base.update({
            'format': 'best[ext=mp4]/best',
        })
    return base

# ─────────────────────────────────────────────
# Build format list from yt-dlp info dict
# ─────────────────────────────────────────────
def build_formats(info: Dict):
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
        if ext.lower() in ['mhtml', 'sb'] or format_id.startswith('sb') or 'storyboard' in format_id.lower():
            continue
        vcodec = fmt.get('vcodec', 'none')
        acodec = fmt.get('acodec', 'none')
        res = fmt.get('resolution')
        if not res or res == 'none':
            w, h = fmt.get('width'), fmt.get('height')
            res = f"{w}x{h}" if (w and h) else fmt.get('format_note', 'Standard')
        filesize = format_filesize(fmt.get('filesize') or fmt.get('filesize_approx'))
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

    if not video_url:
        video_url = info.get('url') or (extracted_formats[-1]["url"] if extracted_formats else None)
    return extracted_formats, video_url, audio_url

# ─────────────────────────────────────────────
# pytubefix YouTube fallback
# ─────────────────────────────────────────────
def try_pytubefix(url: str) -> Optional[Dict[str, Any]]:
    try:
        from pytubefix import YouTube

        # Normalize YouTube Shorts and short links to watch URLs
        video_id = extract_youtube_id(url)
        target_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else url

        for client_type in ['TV', 'IOS']:


            try:
                yt = YouTube(target_url, client=client_type)
                title = str(getattr(yt, 'title', '') or 'YouTube Video')
                thumbnail = str(getattr(yt, 'thumbnail_url', '') or '')
                if not thumbnail and video_id:
                    thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

                length = int(getattr(yt, 'length', 0) or 0)

                # Get all streams with a valid URL (handles both regular videos and Shorts adaptive streams)
                all_streams = []
                try:
                    all_streams = [s for s in list(yt.streams) if getattr(s, 'url', None)]
                except Exception:
                    pass

                if not all_streams:
                    continue

                stream = all_streams[0]

                formats = []
                try:
                    for s in all_streams[:10]:
                        s_url = getattr(s, 'url', None)
                        if not s_url:
                            continue
                        res_val = str(getattr(s, 'resolution', None) or getattr(s, 'quality_label', 'Standard') or "Standard")
                        formats.append({
                            "format_id": str(getattr(s, 'itag', '')),
                            "ext": str(getattr(s, 'subtype', 'mp4') or 'mp4'),
                            "resolution": res_val,
                            "filesize_approx": format_filesize(getattr(s, 'filesize', None)),
                            "url": s_url,
                            "vcodec": "h264",
                            "acodec": "aac"
                        })
                except Exception:
                    pass

                return {
                    "success": True,
                    "url": url,
                    "platform": "YouTube",
                    "title": title,
                    "thumbnail": thumbnail,
                    "duration": length,
                    "duration_formatted": format_duration(length),
                    "video_url": stream.url,
                    "audio_url": stream.url,
                    "formats": formats,
                    "requires_ad_unlock": (length > 900),
                    "error": None
                }
            except Exception:
                continue
    except Exception:
        pass
    return None

# ─────────────────────────────────────────────
# TikWM TikTok Engine
# ─────────────────────────────────────────────
def try_tikwm(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(
            f"https://www.tikwm.com/api/?url={urllib.parse.quote(url)}",
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode('utf-8', errors='ignore'))
            if data.get("code") == 0 and data.get("data"):
                d = data["data"]
                play_url = d.get("play") or d.get("wmplay")
                if play_url:
                    if play_url.startswith("/"):
                        play_url = "https://www.tikwm.com" + play_url
                    dur = d.get("duration", 0) or 0
                    return {
                        "success": True,
                        "url": url,
                        "platform": "TikTok",
                        "title": str(d.get("title") or "TikTok Video"),
                        "thumbnail": d.get("cover"),
                        "duration": dur,
                        "duration_formatted": format_duration(dur),
                        "video_url": play_url,
                        "audio_url": d.get("music") or play_url,
                        "formats": [{
                            "format_id": "hd",
                            "ext": "mp4",
                            "resolution": "HD",
                            "filesize_approx": None,
                            "url": play_url,
                            "vcodec": "h264",
                            "acodec": "aac"
                        }],
                        "requires_ad_unlock": (dur > 900),
                        "error": None
                    }
    except Exception:
        pass
    return None

# ─────────────────────────────────────────────
# Instagram URL Normalizer & Embed Engine
# ─────────────────────────────────────────────
def normalize_instagram_url(url: str) -> str:
    # Handle mobile share links like /share/reel/ or /share/p/
    m = re.search(r'instagram\.com/(?:share/)?(reel|p|tv)/([0-9A-Za-z_-]+)', url)
    if m:
        media_type = m.group(1)
        shortcode = m.group(2)
        return f"https://www.instagram.com/{media_type}/{shortcode}/"
    return url

def try_instagram_embed(url: str) -> Optional[Dict[str, Any]]:
    m = re.search(r'instagram\.com/(?:share/)?(?:reel|p|tv)/([0-9A-Za-z_-]+)', url)
    if not m:
        return None
    shortcode = m.group(1)
    embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"

    try:
        req = urllib.request.Request(embed_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

            video_urls = re.findall(r'video_url["\']?\s*:\s*["\']([^"\']+)["\']', html)
            if not video_urls:
                video_urls = re.findall(r'https?://[^\s"\'\\]+\.mp4[^\s"\'\\]*', html)

            thumbnail_urls = re.findall(r'thumbnail_src["\']?\s*:\s*["\']([^"\']+)["\']', html)
            if not thumbnail_urls:
                thumbnail_urls = re.findall(r'display_url["\']?\s*:\s*["\']([^"\']+)["\']', html)

            if video_urls:
                clean_video = video_urls[0].replace('\\u0026', '&').replace('\\/', '/')
                clean_thumb = thumbnail_urls[0].replace('\\u0026', '&').replace('\\/', '/') if thumbnail_urls else None

                return {
                    "success": True,
                    "url": url,
                    "platform": "Instagram",
                    "title": f"Instagram Video ({shortcode})",
                    "thumbnail": clean_thumb,
                    "duration": 0,
                    "duration_formatted": "00:00",
                    "video_url": clean_video,
                    "audio_url": clean_video,
                    "formats": [{
                        "format_id": "hd",
                        "ext": "mp4",
                        "resolution": "HD",
                        "filesize_approx": None,
                        "url": clean_video,
                        "vcodec": "h264",
                        "acodec": "aac"
                    }],
                    "requires_ad_unlock": False,
                    "error": None
                }
    except Exception:
        pass
    return None

# ─────────────────────────────────────────────
# In-memory extraction LRU cache (TTL = 15 mins)
# ─────────────────────────────────────────────
import time
_extraction_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}

def extract_media_info(url: str) -> Dict[str, Any]:
    clean_url = url.strip()
    if "instagram.com" in clean_url.lower():
        clean_url = normalize_instagram_url(clean_url)

    # Check cache first
    now = time.time()
    if clean_url in _extraction_cache:
        ts, cached_res = _extraction_cache[clean_url]
        if now - ts < 900:  # 15 minutes TTL
            return cached_res

    res = _do_extract_media_info(clean_url)
    if res.get("success"):
        _extraction_cache[clean_url] = (now, res)
    return res

def _do_extract_media_info(url: str) -> Dict[str, Any]:
    platform = detect_platform(url)

    # ── TikTok Engine 1: TikWM (fast 0.3s) ──
    if platform == "TikTok":
        tikwm_res = try_tikwm(url)
        if tikwm_res:
            return tikwm_res

    # ── YouTube Engine 1: pytubefix ──
    if platform == "YouTube":
        pytube_res = try_pytubefix(url)
        if pytube_res:
            return pytube_res

    # ── Engine 2: yt-dlp ──
    ytdlp_error = None
    try:
        with yt_dlp.YoutubeDL(build_ydl_opts(platform)) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                raise ValueError("No info returned")
            if 'entries' in info and info['entries']:
                info = info['entries'][0]

            title = info.get('title') or f"{platform} Video"
            thumbnail = info.get('thumbnail')
            if not thumbnail and info.get('thumbnails'):
                thumbnail = info['thumbnails'][-1].get('url')
            duration = info.get('duration') or 0
            extracted_formats, video_url, audio_url = build_formats(info)

            return {
                "success": True,
                "url": url,
                "platform": platform,
                "title": title,
                "thumbnail": thumbnail,
                "duration": duration,
                "duration_formatted": format_duration(duration),
                "video_url": video_url,
                "audio_url": audio_url or video_url,
                "formats": extracted_formats[-10:],
                "requires_ad_unlock": (duration > 900),
                "error": None,
            }
    except Exception as e:
        ytdlp_error = str(e)

    # ── Instagram Engine 2: Embed Scraper Fallback ──
    if platform == "Instagram":
        ig_res = try_instagram_embed(url)
        if ig_res:
            return ig_res

    # ── YouTube Engine 3 & 4: Piped & Invidious ──
    if platform == "YouTube":
        video_id = extract_youtube_id(url)
        if video_id:
            piped_data = try_piped(video_id)
            if piped_data:
                return parse_piped_response(piped_data, video_id, url)

            inv_data = try_invidious(video_id)
            if inv_data:
                return parse_invidious_response(inv_data, video_id, url)

    # ── All engines failed ──
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
        "error": "Could not extract media. This video may be private, removed, or region-locked.",
    }


