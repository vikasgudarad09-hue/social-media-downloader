import yt_dlp
import re
import os
import urllib.request
import urllib.error
import urllib.parse
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
def format_duration(seconds: Optional[Any]) -> str:
    if not seconds:
        return "N/A"
    try:
        sec = int(float(seconds))
    except (ValueError, TypeError):
        return "N/A"
    if sec <= 0:
        return "N/A"
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{s:02d}"
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
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
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
# Dynamic YouTube visitor session cookie generator
# ─────────────────────────────────────────────
_cached_cookie_path: Optional[str] = None
_cached_cookie_time: float = 0

def get_visitor_cookie_file() -> Optional[str]:
    """Dynamically generate or return cached visitor session cookies for YouTube."""
    global _cached_cookie_path, _cached_cookie_time
    now = time.time()
    if _cached_cookie_path and os.path.exists(_cached_cookie_path) and (now - _cached_cookie_time < 7200):
        return _cached_cookie_path

    try:
        import requests
        import tempfile
        s = requests.Session()
        s.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        r = s.get('https://www.youtube.com', timeout=5)
        if s.cookies:
            lines = ['# Netscape HTTP Cookie File']
            for c in s.cookies:
                domain = c.domain if c.domain.startswith('.') else f'.{c.domain}'
                lines.append(f'{domain}\tTRUE\t/\tTRUE\t2147483647\t{c.name}\t{c.value}')
            temp_path = os.path.join(tempfile.gettempdir(), "yt_visitor_cookies.txt")
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            _cached_cookie_path = temp_path
            _cached_cookie_time = now
            return temp_path
    except Exception as e:
        print(f"[DYNAMIC COOKIE WARNING]: {e}")
    return None

def get_clean_youtube_cookies() -> tuple[Optional[str], Optional[str]]:
    """
    Returns (netscape_cookie_file_path, cookie_header_string).
    Cleans up newlines and normalizes whitespace into tabs for valid Netscape format.
    """
    cookie_file = os.path.join(os.path.dirname(__file__), "..", "cookies.txt")
    if os.path.exists(cookie_file):
        try:
            with open(cookie_file, "r", encoding="utf-8") as f:
                content = f.read()
            pairs = []
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and "\t" in line:
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        pairs.append(f"{parts[5]}={parts[6]}")
            return cookie_file, ("; ".join(pairs) if pairs else None)
        except Exception:
            pass

    raw_cookies = os.environ.get("YOUTUBE_COOKIES", "").strip()
    if not raw_cookies:
        return None, None

    raw_cookies = raw_cookies.replace("\\n", "\n").replace("\\r", "").replace("\r\n", "\n")
    clean_lines = []
    pairs = []
    has_header = False

    for line in raw_cookies.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if "Netscape" in line:
                has_header = True
            clean_lines.append(line)
            continue
        parts = re.split(r'\t+|\s{2,}|\s+', line)
        if len(parts) >= 7:
            domain, flag, path, secure, expiration, name = parts[:6]
            value = " ".join(parts[6:])
            clean_lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}")
            pairs.append(f"{name}={value}")
        elif len(parts) == 2 and "=" not in parts[0]:
            pairs.append(f"{parts[0]}={parts[1]}")
        elif "=" in line:
            for sub in line.split(";"):
                sub = sub.strip()
                if "=" in sub:
                    pairs.append(sub)

    if not has_header:
        clean_lines.insert(0, "# Netscape HTTP Cookie File")

    import tempfile
    temp_cookie_path = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
    try:
        with open(temp_cookie_path, "w", encoding="utf-8") as f:
            f.write("\n".join(clean_lines) + "\n")
        cookie_header = "; ".join(pairs) if pairs else None
        return temp_cookie_path, cookie_header
    except Exception as ce:
        print(f"[COOKIE WRITE ERROR]: {ce}")
    return None, None

# ─────────────────────────────────────────────
# Build yt-dlp options per platform
# ─────────────────────────────────────────────
def build_ydl_opts(platform: str) -> Dict[str, Any]:
    base = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': False,
        'noplaylist': True,
        'socket_timeout': 8,
        'retries': 1,
        'ignoreerrors': False,
    }

    # Support cleaned cookies if present
    cookie_path, _ = get_clean_youtube_cookies()
    if cookie_path:
        base['cookiefile'] = cookie_path
    elif platform == "YouTube":
        dyn_cookie = get_visitor_cookie_file()
        if dyn_cookie:
            base['cookiefile'] = dyn_cookie

    if platform == "YouTube":
        base.update({
            'format': 'all',
            'geo_bypass': True,
            'js_runtimes': {'node': {}},
            'remote_components': ['ejs:github'],
        })
        if not base.get('cookiefile'):
            base['extractor_args'] = {
                'youtube': {
                    'player_client': ['mweb', 'web', 'ios'],
                }
            }
    elif platform == "Instagram":
        base.update({
            'format': 'best[ext=mp4]/best',
        })
    elif platform == "TikTok":
        base.update({
            'format': 'best[ext=mp4]/best',
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

    # Prioritize progressive formats (both audio and video included)
    progressive = [f for f in extracted_formats if f.get('vcodec') != 'none' and f.get('acodec') != 'none']
    if progressive:
        video_url = progressive[-1]['url']
    elif extracted_formats:
        video_fmts = [f for f in extracted_formats if f.get('vcodec') != 'none']
        video_url = video_fmts[-1]['url'] if video_fmts else extracted_formats[-1]['url']
    else:
        video_url = None

    if not audio_url:
        audio_only = [f for f in extracted_formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none']
        if audio_only:
            audio_url = audio_only[-1]['url']
        elif progressive:
            audio_url = progressive[-1]['url']

    return extracted_formats, video_url, audio_url

# ─────────────────────────────────────────────
# pytubefix YouTube Engine (fast 0.8s, reliable)
# ─────────────────────────────────────────────
def try_pytubefix(url: str) -> Optional[Dict[str, Any]]:
    try:
        from pytubefix import YouTube

        # Normalize YouTube Shorts and short links to watch URLs
        video_id = extract_youtube_id(url)
        target_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else url

        # Priority clients that work reliably without bot challenges (VISION_OS is fastest at ~1s)
        client_candidates = ['VISION_OS', 'ANDROID_VR', 'MWEB', 'WEB', 'IOS']

        # Inject user session cookies if present to bypass datacenter 403 Forbidden
        _, cookie_header = get_clean_youtube_cookies()
        if cookie_header:
            try:
                import pytubefix.request
                orig_exec = getattr(pytubefix.request, '_orig_execute_request', pytubefix.request._execute_request)
                pytubefix.request._orig_execute_request = orig_exec
                def patched_exec(req_url, method=None, headers=None, data=None, timeout=12):
                    if headers is None:
                        headers = {}
                    if 'Cookie' not in headers:
                        headers['Cookie'] = cookie_header
                    return orig_exec(req_url, method=method, headers=headers, data=data, timeout=timeout)
                pytubefix.request._execute_request = patched_exec
            except Exception:
                pass

        for client_type in client_candidates:
            try:
                yt = YouTube(target_url, client=client_type)
                title = str(getattr(yt, 'title', '') or 'YouTube Video')
                thumbnail = str(getattr(yt, 'thumbnail_url', '') or '')
                if not thumbnail and video_id:
                    thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

                length = int(getattr(yt, 'length', 0) or 0)

                # Get all streams with a valid URL
                all_streams = []
                try:
                    all_streams = [s for s in list(yt.streams) if getattr(s, 'url', None)]
                except Exception:
                    pass

                if not all_streams:
                    continue

                def _res_num(s):
                    res_str = str(getattr(s, 'resolution', '') or getattr(s, 'quality_label', '') or '0p')
                    digits = ''.join([c for c in res_str if c.isdigit()])
                    return int(digits) if digits else 0

                def _abr_num(s):
                    abr_str = str(getattr(s, 'abr', '') or '0kbps')
                    digits = ''.join([c for c in abr_str if c.isdigit()])
                    return int(digits) if digits else 0

                # 1. Progressive streams (contain BOTH video and audio in single MP4)
                prog_streams = [s for s in all_streams if getattr(s, 'is_progressive', False)]
                prog_streams.sort(key=_res_num, reverse=True)

                # 2. MP4 video streams
                mp4_video_streams = [s for s in all_streams if getattr(s, 'resolution', None) and 'mp4' in str(getattr(s, 'mime_type', ''))]
                mp4_video_streams.sort(key=_res_num, reverse=True)

                # 3. All video streams
                any_video_streams = [s for s in all_streams if getattr(s, 'resolution', None)]
                any_video_streams.sort(key=_res_num, reverse=True)

                # 4. Audio streams
                audio_streams = [s for s in all_streams if 'audio' in str(getattr(s, 'mime_type', ''))]
                audio_streams.sort(key=_abr_num, reverse=True)
                mp4_audio_streams = [s for s in audio_streams if 'mp4' in str(getattr(s, 'mime_type', ''))]

                # Determine default video_url:
                # Prioritize progressive (has sound), then top MP4 video stream
                if prog_streams:
                    video_url = prog_streams[0].url
                elif mp4_video_streams:
                    video_url = mp4_video_streams[0].url
                elif any_video_streams:
                    video_url = any_video_streams[0].url
                else:
                    video_url = all_streams[0].url

                # Determine default audio_url:
                if mp4_audio_streams:
                    audio_url = mp4_audio_streams[0].url
                elif audio_streams:
                    audio_url = audio_streams[0].url
                elif prog_streams:
                    audio_url = prog_streams[0].url
                else:
                    audio_url = video_url

                # Build rich format list
                formats = []
                seen_itags = set()

                # Add progressive streams first
                for s in prog_streams:
                    itag = str(getattr(s, 'itag', ''))
                    if itag in seen_itags:
                        continue
                    seen_itags.add(itag)
                    res_val = str(getattr(s, 'resolution', '') or '360p')
                    formats.append({
                        "format_id": itag,
                        "ext": "mp4",
                        "resolution": f"{res_val} (Video + Audio)",
                        "filesize_approx": format_filesize(getattr(s, 'filesize', None)),
                        "url": s.url,
                        "vcodec": "h264",
                        "acodec": "aac"
                    })

                # Add high-resolution video streams
                for s in mp4_video_streams:
                    itag = str(getattr(s, 'itag', ''))
                    if itag in seen_itags:
                        continue
                    seen_itags.add(itag)
                    res_val = str(getattr(s, 'resolution', '') or 'HD')
                    formats.append({
                        "format_id": itag,
                        "ext": "mp4",
                        "resolution": f"{res_val} (HD Video)",
                        "filesize_approx": format_filesize(getattr(s, 'filesize', None)),
                        "url": s.url,
                        "vcodec": "h264",
                        "acodec": "none"
                    })

                # Add best audio streams
                for s in audio_streams[:3]:
                    itag = str(getattr(s, 'itag', ''))
                    if itag in seen_itags:
                        continue
                    seen_itags.add(itag)
                    abr_val = str(getattr(s, 'abr', '') or 'Audio')
                    ext = "m4a" if "mp4" in str(getattr(s, 'mime_type', '')) else "webm"
                    formats.append({
                        "format_id": itag,
                        "ext": ext,
                        "resolution": f"Audio ({abr_val})",
                        "filesize_approx": format_filesize(getattr(s, 'filesize', None)),
                        "url": s.url,
                        "vcodec": "none",
                        "acodec": "aac" if ext == "m4a" else "opus"
                    })

                return {
                    "success": True,
                    "url": url,
                    "platform": "YouTube",
                    "title": title,
                    "thumbnail": thumbnail,
                    "duration": length,
                    "duration_formatted": format_duration(length),
                    "video_url": video_url,
                    "audio_url": audio_url,
                    "formats": formats[:12],
                    "requires_ad_unlock": False,
                    "error": None
                }
            except Exception as ce:
                print(f"[PYTUBEFIX {client_type} NOTICE]: {ce}")
                continue
    except Exception as e:
        print(f"[PYTUBEFIX ERROR]: {e}")
    return None

# ─────────────────────────────────────────────
# TikWM TikTok Engine
# ─────────────────────────────────────────────
def try_tikwm(url: str) -> Optional[Dict[str, Any]]:
    try:
        post_data = urllib.parse.urlencode({
            'url': url,
            'count': 12,
            'cursor': 0,
            'web': 1,
            'hd': 1
        }).encode('utf-8')
        req = urllib.request.Request(
            "https://www.tikwm.com/api/",
            data=post_data,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json, text/plain, */*',
                'Origin': 'https://www.tikwm.com',
                'Referer': 'https://www.tikwm.com/'
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8', errors='ignore'))
            if data.get("code") == 0 and data.get("data"):
                d = data["data"]
                play_url = d.get("play") or d.get("wmplay")
                hd_url = d.get("hdplay")
                if hd_url and hd_url.startswith("/"):
                    hd_url = "https://www.tikwm.com" + hd_url
                if play_url and play_url.startswith("/"):
                    play_url = "https://www.tikwm.com" + play_url

                main_url = hd_url or play_url
                if not main_url:
                    return None

                dur = d.get("duration", 0) or 0
                formats = []
                if hd_url:
                    formats.append({
                        "format_id": "hd",
                        "ext": "mp4",
                        "resolution": "HD No Watermark",
                        "filesize_approx": format_filesize(d.get("size")),
                        "url": hd_url,
                        "vcodec": "h264",
                        "acodec": "aac"
                    })
                if play_url:
                    formats.append({
                        "format_id": "sd",
                        "ext": "mp4",
                        "resolution": "Standard",
                        "filesize_approx": format_filesize(d.get("wm_size") or d.get("size")),
                        "url": play_url,
                        "vcodec": "h264",
                        "acodec": "aac"
                    })

                return {
                    "success": True,
                    "url": url,
                    "platform": "TikTok",
                    "title": str(d.get("title") or "TikTok Video"),
                    "thumbnail": d.get("cover"),
                    "duration": dur,
                    "duration_formatted": format_duration(dur),
                    "video_url": main_url,
                    "audio_url": d.get("music") or main_url,
                    "formats": formats,
                    "requires_ad_unlock": (dur > 900),
                    "error": None
                }
    except Exception as e:
        print(f"[TIKWM ERROR]: {e}")
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
    elif "youtube.com" in clean_url.lower() or "youtu.be" in clean_url.lower():
        yt_id = extract_youtube_id(clean_url)
        if yt_id:
            clean_url = f"https://www.youtube.com/watch?v={yt_id}"

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

    # ── Fast Engine 1: YouTube pytubefix (0.8s, bypasses bot checks) ──
    if platform == "YouTube":
        try:
            pytube_res = try_pytubefix(url)
            if pytube_res and pytube_res.get("success"):
                return pytube_res
        except Exception as pe:
            print(f"[PYTUBEFIX NOTICE]: {pe}")

    # ── Fast Engine 2: TikTok TikWM (0.3s, direct clean MP4) ──
    if platform == "TikTok":
        try:
            tikwm_res = try_tikwm(url)
            if tikwm_res and tikwm_res.get("success"):
                return tikwm_res
        except Exception as te:
            print(f"[TIKWM NOTICE]: {te}")

    # ── Universal Engine: yt-dlp ──
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
            try:
                duration = int(float(info.get('duration') or 0))
            except (ValueError, TypeError):
                duration = 0
            extracted_formats, video_url, audio_url = build_formats(info)
            if not video_url or not extracted_formats:
                raise ValueError("No playable video stream found")

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
                "requires_ad_unlock": False,
                "error": None,
            }
    except Exception as e:
        ytdlp_error = str(e)
        print(f"[EXTRACT WARNING] yt-dlp failed for {platform} ({url}): {e}")

    # ── YouTube Engine Fallback: pytubefix ──
    if platform == "YouTube":
        try:
            pytube_res = try_pytubefix(url)
            if pytube_res and pytube_res.get("success"):
                return pytube_res
        except Exception as pe:
            print(f"[PYTUBEFIX ERROR]: {pe}")

    # ── TikTok Engine Fallback: TikWM ──
    if platform == "TikTok":
        tikwm_res = try_tikwm(url)
        if tikwm_res and tikwm_res.get("success"):
            return tikwm_res

    # ── Instagram Engine 2: Embed Scraper Fallback ──
    if platform == "Instagram":
        ig_res = try_instagram_embed(url)
        if ig_res and ig_res.get("success"):
            return ig_res

    # ── All engines failed ──
    detailed_error = ytdlp_error or "Could not extract media. This video may be private, removed, or region-locked."
    print(f"[EXTRACT FAILED] Final failure for {platform} ({url}): {detailed_error}")
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
        "error": detailed_error,
    }


