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
    elif "vimeo.com" in url_lower:
        return "Vimeo"
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

def find_corrected_youtube_id(video_id: str) -> Optional[str]:
    """
    Checks if a YouTube video ID has ambiguous character typos (e.g. 'l' vs 'I' vs '1', 'O' vs '0')
    and discovers the genuine valid YouTube video ID via fast oEmbed verification.
    """
    if not video_id or len(video_id) != 11:
        return None

    ambig_map = {
        'l': ['l', 'I', '1'],
        'I': ['I', 'l', '1'],
        '1': ['1', 'I', 'l'],
        'O': ['O', '0'],
        '0': ['0', 'O']
    }
    indices = [i for i, c in enumerate(video_id) if c in ambig_map]
    if not indices or len(indices) > 4:
        return None

    import itertools
    choices = [ambig_map[video_id[i]] for i in indices]
    for combo in itertools.product(*choices):
        cand = list(video_id)
        for idx, repl in zip(indices, combo):
            cand[idx] = repl
        cand_id = ''.join(cand)
        if cand_id == video_id:
            continue
        try:
            req = urllib.request.Request(
                f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={cand_id}&format=json',
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                if resp.status == 200:
                    return cand_id
        except Exception:
            pass
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
        if line.startswith("#") and not line.startswith("#HttpOnly_"):
            if "Netscape" in line:
                has_header = True
            clean_lines.append(line)
            continue

        is_httponly = line.startswith("#HttpOnly_")
        cookie_str = line[10:] if is_httponly else line
        parts = re.split(r'\t+|\s{2,}|\s+', cookie_str)
        if len(parts) >= 7:
            domain, flag, path, secure, expiration, name = parts[:6]
            value = " ".join(parts[6:])
            prefix = "#HttpOnly_" if is_httponly else ""
            clean_lines.append(f"{prefix}{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}")
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

    if platform == "YouTube":
        cookie_path, _ = get_clean_youtube_cookies()
        if cookie_path:
            base['cookiefile'] = cookie_path
        base.update({
            'format': 'all',
            'geo_bypass': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web'],
                }
            }
        })
    elif platform == "Vimeo":
        base.update({
            'format': 'best[ext=mp4]/best',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                'Referer': 'https://vimeo.com/',
            }
        })
    elif platform == "Instagram":
        cookie_path, _ = get_clean_youtube_cookies()
        if cookie_path:
            base['cookiefile'] = cookie_path
        base.update({
            'format': 'best[ext=mp4]/best',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            }
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
    prog_formats = []
    video_only = []
    audio_only = []

    for fmt in raw_formats:
        fmt_url = fmt.get('url')
        if not fmt_url:
            continue
        ext = fmt.get('ext', 'mp4')
        format_id = str(fmt.get('format_id', ''))
        if ext.lower() in ['mhtml', 'sb'] or format_id.startswith('sb') or 'storyboard' in format_id.lower():
            continue

        # NEVER include playlist / manifest URLs as direct downloads (prevents 23KB text file bug)
        proto = str(fmt.get('protocol', '')).lower()
        if 'm3u8' in proto or 'm3u8' in fmt_url.lower() or 'manifest' in fmt_url.lower() or 'dash' in proto:
            continue

        vcodec = fmt.get('vcodec') or 'none'
        acodec = fmt.get('acodec') or 'none'
        h = fmt.get('height') or 0
        w = fmt.get('width') or 0
        abr = fmt.get('abr') or 0
        filesize = format_filesize(fmt.get('filesize') or fmt.get('filesize_approx'))

        has_v = (vcodec != 'none')
        has_a = (acodec != 'none')

        res_str = fmt.get('resolution') or (f"{w}x{h}" if (w and h) else fmt.get('format_note') or 'Standard')

        item = {
            "format_id": format_id,
            "ext": ext,
            "resolution": res_str,
            "height": h,
            "abr": abr,
            "filesize_approx": filesize,
            "url": fmt_url,
            "vcodec": vcodec,
            "acodec": acodec,
        }

        if has_v and has_a:
            prog_formats.append(item)
        elif has_v and not has_a:
            video_only.append(item)
        elif not has_v and has_a:
            audio_only.append(item)

    # Sort formats from highest to lowest quality
    prog_formats.sort(key=lambda x: x['height'], reverse=True)
    video_only.sort(key=lambda x: x['height'], reverse=True)
    audio_only.sort(key=lambda x: x['abr'], reverse=True)

    # Pick defaults
    if prog_formats:
        video_url = prog_formats[0]['url']
    elif video_only:
        video_url = video_only[0]['url']
    elif raw_formats:
        video_url = raw_formats[0].get('url')
    else:
        video_url = None

    if audio_only:
        # Prefer m4a if available for best browser playback
        m4a_audios = [a for a in audio_only if a['ext'] == 'm4a']
        audio_url = m4a_audios[0]['url'] if m4a_audios else audio_only[0]['url']
    elif prog_formats:
        audio_url = prog_formats[0]['url']
    else:
        audio_url = video_url

    # Build final curated formats list for UI
    curated = []
    seen = set()

    for p in prog_formats:
        label = f"{p['height']}p (Video + Audio)" if p['height'] else p['resolution']
        key = (p['ext'], label)
        if key not in seen:
            seen.add(key)
            curated.append({**p, "resolution": label})

    for v in video_only:
        if v['height'] >= 720:  # Only add HD streams to avoid clutter
            label = f"{v['height']}p (HD Video)"
            key = (v['ext'], label)
            if key not in seen and len(curated) < 10:
                seen.add(key)
                curated.append({**v, "resolution": label})

    for a in audio_only[:3]:
        label = f"Audio ({a['ext'].upper()} {int(a['abr'])}k)" if a['abr'] else f"Audio ({a['ext'].upper()})"
        key = (a['ext'], label)
        if key not in seen and len(curated) < 14:
            seen.add(key)
            curated.append({**a, "resolution": label})

    # If no curated formats were formed, fallback to raw
    if not curated and raw_formats:
        for fmt in raw_formats[:8]:
            u = fmt.get('url')
            if u:
                curated.append({
                    "format_id": str(fmt.get('format_id', 'standard')),
                    "ext": fmt.get('ext', 'mp4'),
                    "resolution": fmt.get('resolution') or 'Standard',
                    "filesize_approx": format_filesize(fmt.get('filesize') or fmt.get('filesize_approx')),
                    "url": u,
                    "vcodec": fmt.get('vcodec', 'none'),
                    "acodec": fmt.get('acodec', 'none'),
                })

    return curated, video_url, audio_url

# ─────────────────────────────────────────────
# pytubefix YouTube Engine (fast 0.8s, reliable)
# ─────────────────────────────────────────────
def try_pytubefix(url: str, use_cookies: bool = True) -> Optional[Dict[str, Any]]:
    try:
        from pytubefix import YouTube

        # Normalize YouTube Shorts and short links to watch URLs
        video_id = extract_youtube_id(url)
        target_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else url

        # Priority clients for fallback - WEB first for fastest response
        client_candidates = ['WEB', 'ANDROID_VR', 'ANDROID']

        # Inject user session cookies if requested and present
        if use_cookies:
            _, cookie_header = get_clean_youtube_cookies()
            if cookie_header:
                try:
                    import pytubefix.request
                    orig_exec = getattr(pytubefix.request, '_orig_execute_request', pytubefix.request._execute_request)
                    pytubefix.request._orig_execute_request = orig_exec
                    def patched_exec(req_url, method=None, headers=None, data=None, timeout=6):
                        if headers is None:
                            headers = {}
                        if 'Cookie' not in headers:
                            headers['Cookie'] = cookie_header
                        return orig_exec(req_url, method=method, headers=headers, data=data, timeout=timeout)
                    pytubefix.request._execute_request = patched_exec
                except Exception:
                    pass
        else:
            try:
                import pytubefix.request
                if hasattr(pytubefix.request, '_orig_execute_request'):
                    pytubefix.request._execute_request = pytubefix.request._orig_execute_request
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

                # Filter candidate streams without deciphering URLs first
                prog_streams = list(yt.streams.filter(progressive=True))
                prog_streams.sort(key=lambda s: int(''.join(filter(str.isdigit, str(getattr(s, 'resolution', '') or '0'))) or 0), reverse=True)

                audio_streams = list(yt.streams.filter(only_audio=True))
                audio_streams.sort(key=lambda s: int(''.join(filter(str.isdigit, str(getattr(s, 'abr', '') or '0'))) or 0), reverse=True)

                video_streams = list(yt.streams.filter(adaptive=True, type="video"))
                video_streams.sort(key=lambda s: int(''.join(filter(str.isdigit, str(getattr(s, 'resolution', '') or '0'))) or 0), reverse=True)

                if not prog_streams and not video_streams and not audio_streams:
                    continue

                formats = []
                seen_itags = set()
                video_url = None
                audio_url = None

                # 1. Progressive streams (Video + Audio) - decipher top 2
                for s in prog_streams[:2]:
                    try:
                        u = s.url
                        if u:
                            itag = str(getattr(s, 'itag', ''))
                            seen_itags.add(itag)
                            res_val = str(getattr(s, 'resolution', '') or '360p')
                            if not video_url:
                                video_url = u
                            formats.append({
                                "format_id": itag,
                                "ext": "mp4",
                                "resolution": f"{res_val} (Video + Audio)",
                                "filesize_approx": format_filesize(getattr(s, 'filesize', None)),
                                "url": u,
                                "vcodec": "h264",
                                "acodec": "aac"
                            })
                    except Exception:
                        pass

                # 2. Audio streams - decipher top 2
                for s in audio_streams[:2]:
                    try:
                        u = s.url
                        if u:
                            itag = str(getattr(s, 'itag', ''))
                            if itag in seen_itags:
                                continue
                            seen_itags.add(itag)
                            if not audio_url:
                                audio_url = u
                            abr_val = str(getattr(s, 'abr', '') or 'Audio')
                            ext = "m4a" if "mp4" in str(getattr(s, 'mime_type', '')) else "webm"
                            formats.append({
                                "format_id": itag,
                                "ext": ext,
                                "resolution": f"Audio ({abr_val})",
                                "filesize_approx": format_filesize(getattr(s, 'filesize', None)),
                                "url": u,
                                "vcodec": "none",
                                "acodec": "aac" if ext == "m4a" else "opus"
                            })
                    except Exception:
                        pass

                # 3. High-definition video streams - decipher top 2
                for s in video_streams[:2]:
                    try:
                        res_num = int(''.join(filter(str.isdigit, str(getattr(s, 'resolution', '') or '0'))) or 0)
                        if res_num >= 720:
                            u = s.url
                            if u:
                                itag = str(getattr(s, 'itag', ''))
                                if itag in seen_itags:
                                    continue
                                seen_itags.add(itag)
                                formats.append({
                                    "format_id": itag,
                                    "ext": "mp4" if "mp4" in str(getattr(s, 'mime_type', '')) else "webm",
                                    "resolution": f"{res_num}p (HD Video)",
                                    "filesize_approx": format_filesize(getattr(s, 'filesize', None)),
                                    "url": u,
                                    "vcodec": "h264",
                                    "acodec": "none"
                                })
                    except Exception:
                        pass

                if not video_url and formats:
                    video_url = formats[0]['url']
                if not audio_url:
                    audio_url = video_url

                if video_url:
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
                        "formats": formats,
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
def resolve_redirects(url: str) -> str:
    """Follow HTTP 301/302 redirects to find the canonical destination URL."""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
        })
        with urllib.request.urlopen(req, timeout=4) as resp:
            return resp.geturl() or url
    except Exception:
        return url

# ─────────────────────────────────────────────
# TikWM TikTok Engine
# ─────────────────────────────────────────────
def try_tikwm(url: str) -> Optional[Dict[str, Any]]:
    try:
        clean_url = url
        if any(short in url.lower() for short in ["vm.tiktok.com", "vt.tiktok.com", "/t/"]):
            clean_url = resolve_redirects(url)

        post_data = urllib.parse.urlencode({
            'url': clean_url,
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
        with urllib.request.urlopen(req, timeout=8) as resp:
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
                if d.get("music"):
                    music_url = d.get("music")
                    if music_url.startswith("/"):
                        music_url = "https://www.tikwm.com" + music_url
                    formats.append({
                        "format_id": "music",
                        "ext": "mp3",
                        "resolution": "Audio Track (MP3)",
                        "filesize_approx": None,
                        "url": music_url,
                        "vcodec": "none",
                        "acodec": "mp3"
                    })

                music_stream = d.get("music")
                if music_stream and music_stream.startswith("/"):
                    music_stream = "https://www.tikwm.com" + music_stream

                return {
                    "success": True,
                    "url": url,
                    "platform": "TikTok",
                    "title": str(d.get("title") or "TikTok Video"),
                    "thumbnail": d.get("cover"),
                    "duration": dur,
                    "duration_formatted": format_duration(dur),
                    "video_url": main_url,
                    "audio_url": music_stream or main_url,
                    "formats": formats,
                    "requires_ad_unlock": False,
                    "error": None
                }
    except Exception as e:
        print(f"[TIKWM ERROR]: {e}")
    return None

# ─────────────────────────────────────────────
# Vimeo Engine (Direct config + embed player)
# ─────────────────────────────────────────────
def extract_vimeo_id(url: str) -> Optional[str]:
    m = re.search(r'vimeo\.com/(?:channels/(?:\w+/)?|groups/[^/]+/videos/|album/(?:\d+/)?video/|video/|)(\d+)', url)
    return m.group(1) if m else None

def try_vimeo(url: str) -> Optional[Dict[str, Any]]:
    vid = extract_vimeo_id(url)
    if not vid:
        return None

    # 1. Direct player config JSON API (fast, extracts progressive MP4s if enabled)
    try:
        config_url = f"https://player.vimeo.com/video/{vid}/config"
        req = urllib.request.Request(
            config_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                'Referer': f'https://vimeo.com/{vid}',
                'Accept': 'application/json, text/plain, */*'
            }
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            cfg = json.loads(resp.read().decode('utf-8'))
            video_meta = cfg.get('video', {})
            title = video_meta.get('title') or "Vimeo Video"
            duration = video_meta.get('duration', 0)
            thumbs = video_meta.get('thumbs', {})
            thumbnail = thumbs.get('base') or (list(thumbs.values())[-1] if thumbs else None)

            progs = cfg.get('request', {}).get('files', {}).get('progressive', [])
            formats = []
            for p in progs:
                u = p.get('url')
                if not u:
                    continue
                q = p.get('quality') or (f"{p.get('height')}p" if p.get('height') else "HD")
                formats.append({
                    "format_id": str(p.get('profile') or q),
                    "ext": "mp4",
                    "resolution": f"{q} (Video + Audio)",
                    "filesize_approx": None,
                    "url": u,
                    "vcodec": "h264",
                    "acodec": "aac"
                })

            if formats:
                formats.sort(key=lambda x: int(''.join(filter(str.isdigit, x['resolution'])) or 0), reverse=True)
                return {
                    "success": True,
                    "url": url,
                    "platform": "Vimeo",
                    "title": title,
                    "thumbnail": thumbnail,
                    "duration": duration,
                    "duration_formatted": format_duration(duration),
                    "video_url": formats[0]['url'],
                    "audio_url": formats[0]['url'],
                    "formats": formats,
                    "requires_ad_unlock": False,
                    "error": None
                }
    except Exception as ve:
        print(f"[VIMEO CONFIG NOTICE]: {ve}")

    # 2. yt-dlp via embed player URL (bypasses Vimeo web login requirement)
    try:
        player_embed_url = f"https://player.vimeo.com/video/{vid}"
        opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'noplaylist': True,
            'socket_timeout': 8,
            'retries': 1,
            'format': 'best[ext=mp4]/best'
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(player_embed_url, download=False)
            if info:
                title = info.get('title') or "Vimeo Video"
                thumbnail = info.get('thumbnail')
                duration = int(float(info.get('duration') or 0))
                extracted_formats, video_url, audio_url = build_formats(info)
                if video_url and extracted_formats:
                    return {
                        "success": True,
                        "url": url,
                        "platform": "Vimeo",
                        "title": title,
                        "thumbnail": thumbnail,
                        "duration": duration,
                        "duration_formatted": format_duration(duration),
                        "video_url": video_url,
                        "audio_url": audio_url or video_url,
                        "formats": extracted_formats,
                        "requires_ad_unlock": False,
                        "error": None
                    }
    except Exception as ye:
        print(f"[VIMEO YTDLP NOTICE]: {ye}")

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

def try_parth_dl(url: str) -> Optional[Dict[str, Any]]:
    try:
        from parth_dl.extractors import MediaExtractor
        me = MediaExtractor(verbose=False)
        res = me.extract(url)
        if res:
            v_url = None
            formats = []

            # 1. Check formats array from finalize_info
            raw_formats = res.get('formats') or []
            if raw_formats:
                v_url = raw_formats[0].get('url')
                for idx, f in enumerate(raw_formats):
                    formats.append({
                        "format_id": str(f.get("format_id") or f"fmt-{idx}"),
                        "ext": "mp4",
                        "resolution": f"{f.get('height', 'HD')}p" if f.get('height') else "HD",
                        "filesize_approx": None,
                        "url": f.get("url"),
                        "vcodec": "h264",
                        "acodec": "aac"
                    })

            # 2. Check entries if formats is empty
            if not v_url and res.get('entries'):
                entry = res['entries'][0]
                entry_fmts = entry.get('formats') or []
                if entry_fmts:
                    v_url = entry_fmts[0].get('url')
                    for idx, f in enumerate(entry_fmts):
                        formats.append({
                            "format_id": str(f.get("format_id") or f"fmt-{idx}"),
                            "ext": "mp4",
                            "resolution": f"{f.get('height', 'HD')}p" if f.get('height') else "HD",
                            "filesize_approx": None,
                            "url": f.get("url"),
                            "vcodec": "h264",
                            "acodec": "aac"
                        })

            # 3. Check images for photos or carousels
            if not v_url and res.get('images'):
                img = res['images'][0]
                v_url = img.get('url')
                formats.append({
                    "format_id": "image",
                    "ext": "jpg",
                    "resolution": "Original Image",
                    "filesize_approx": None,
                    "url": v_url,
                    "vcodec": "none",
                    "acodec": "none"
                })

            if v_url and formats:
                title = res.get('title') or "Instagram Media"
                thumb = res.get('thumbnail')
                dur = res.get('duration') or 0
                return {
                    "success": True,
                    "url": url,
                    "platform": "Instagram",
                    "title": title,
                    "thumbnail": thumb,
                    "duration": dur,
                    "duration_formatted": format_duration(dur),
                    "video_url": v_url,
                    "audio_url": v_url,
                    "formats": formats,
                    "requires_ad_unlock": False,
                    "error": None
                }
    except Exception as pe:
        print(f"[PARTH-DL NOTICE]: {pe}")
    return None

def try_instagram_embed(url: str) -> Optional[Dict[str, Any]]:
    m = re.search(r'instagram\.com/(?:share/)?(?:reel|p|tv)/([0-9A-Za-z_-]+)', url)
    if not m:
        return None
    shortcode = m.group(1)
    embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"

    try:
        req = urllib.request.Request(embed_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

            # Search both direct and JSON-escaped URLs
            found_videos = []
            for vm in re.finditer(r'https?(?::|%3A)(?:\\/\\/|//)[^\s"\'<>]+\.mp4[^\s"\'<>]*', html):
                raw_u = vm.group(0).replace('\\u0026', '&').replace('\\/', '/').replace('&amp;', '&')
                if raw_u not in found_videos:
                    found_videos.append(raw_u)

            if not found_videos:
                video_urls = re.findall(r'video_url["\']?\s*:\s*["\']([^"\']+)["\']', html)
                if video_urls:
                    found_videos.append(video_urls[0].replace('\\u0026', '&').replace('\\/', '/'))

            thumbnail_urls = re.findall(r'thumbnail_src["\']?\s*:\s*["\']([^"\']+)["\']', html)
            if not thumbnail_urls:
                thumbnail_urls = re.findall(r'display_url["\']?\s*:\s*["\']([^"\']+)["\']', html)

            if found_videos:
                clean_video = found_videos[0]
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
    except Exception as e:
        print(f"[INSTAGRAM EMBED NOTICE]: {e}")
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

    # If YouTube extraction failed, attempt automatic ambiguous character recovery
    if not res.get("success") and ("youtube.com" in clean_url.lower() or "youtu.be" in clean_url.lower()):
        yt_id = extract_youtube_id(clean_url)
        if yt_id:
            fixed_id = find_corrected_youtube_id(yt_id)
            if fixed_id and fixed_id != yt_id:
                print(f"[YOUTUBE AUTO-CORRECT]: Resolved ambiguous ID {yt_id} -> {fixed_id}")
                fixed_url = f"https://www.youtube.com/watch?v={fixed_id}"
                fixed_res = _do_extract_media_info(fixed_url)
                if fixed_res.get("success"):
                    res = fixed_res

    # Clean up error messages for users so internal bot flags don't confuse them
    if not res.get("success") and res.get("error"):
        err = str(res["error"])
        if any(b in err.lower() for b in ["bot", "sign in", "confirm you're not a bot", "cookies-from-browser", "--cookies"]):
            res["error"] = "YouTube requested verification for this video. Please ensure the link is public, or try another video link."
        elif "unavailable" in err.lower():
            res["error"] = "This video is unavailable or does not exist. Please check the URL for typos."

    if res.get("success"):
        _extraction_cache[clean_url] = (now, res)
    return res

def _do_extract_media_info(url: str) -> Dict[str, Any]:
    platform = detect_platform(url)

    # ── Fast Engine 1: TikTok TikWM (sub-second, direct clean watermark-free MP4) ──
    if platform == "TikTok":
        try:
            tikwm_res = try_tikwm(url)
            if tikwm_res and tikwm_res.get("success"):
                return tikwm_res
        except Exception as te:
            print(f"[TIKWM NOTICE]: {te}")

    # ── Fast Engine 2: Vimeo (direct config + embed player) ──
    if platform == "Vimeo":
        try:
            vimeo_res = try_vimeo(url)
            if vimeo_res and vimeo_res.get("success"):
                return vimeo_res
        except Exception as ve:
            print(f"[VIMEO NOTICE]: {ve}")

    # ── Universal Engine: yt-dlp (fast, comprehensive) ──
    ytdlp_error = None
    info = None

    if platform == "YouTube":
        try:
            with yt_dlp.YoutubeDL(build_ydl_opts(platform)) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as ye1:
            err_str = str(ye1)
            ytdlp_error = err_str
            print(f"[YOUTUBE PRIMARY WARNING]: {ye1}")

            # 1. Immediately check if the video ID contains ambiguous characters (e.g. l vs I)
            yt_id = extract_youtube_id(url)
            if yt_id:
                fixed_id = find_corrected_youtube_id(yt_id)
                if fixed_id and fixed_id != yt_id:
                    print(f"[YOUTUBE AUTO-CORRECT]: Found genuine ID {yt_id} -> {fixed_id}")
                    url = f"https://www.youtube.com/watch?v={fixed_id}"
                    try:
                        with yt_dlp.YoutubeDL(build_ydl_opts(platform)) as ydl:
                            info = ydl.extract_info(url, download=False)
                            if info:
                                ytdlp_error = None
                    except Exception as ye_fix:
                        err_str = str(ye_fix)
                        ytdlp_error = err_str

            # 2. If bot challenge, 403, or cookie issue, retry immediately with clean unauthenticated android/ios client
            if not info and any(k in err_str.lower() for k in ["bot", "sign in", "cookie", "login", "confirm you're not a bot", "403"]):
                try:
                    print("[YOUTUBE RETRY]: Retrying without cookies using android/ios client...")
                    clean_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'skip_download': True,
                        'noplaylist': True,
                        'socket_timeout': 10,
                        'retries': 2,
                        'format': 'all',
                        'geo_bypass': True,
                        'extractor_args': {
                            'youtube': {
                                'player_client': ['android', 'ios']
                            }
                        }
                    }
                    with yt_dlp.YoutubeDL(clean_opts) as a_ydl:
                        info = a_ydl.extract_info(url, download=False)
                        if info:
                            ytdlp_error = None
                except Exception as ye2:
                    print(f"[YOUTUBE CLEAN RETRY FAILED]: {ye2}")
                    ytdlp_error = str(ye2)
    else:
        try:
            with yt_dlp.YoutubeDL(build_ydl_opts(platform)) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            ytdlp_error = str(e)
            print(f"[EXTRACT WARNING] yt-dlp failed for {platform} ({url}): {e}")

    if info:
        try:
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

            # If YouTube video lacks progressive streams (video+audio combined),
            # query Android client format 18 (fast ~1s) to guarantee synchronized audio/video playback
            if platform == "YouTube":
                has_prog = any(
                    f.get('vcodec') != 'none' and f.get('acodec') != 'none' and
                    'm3u8' not in f.get('url', '') and 'manifest' not in f.get('url', '') and
                    'm3u8' not in str(f.get('protocol', '')).lower()
                    for f in (info.get('formats') or [])
                )
                if not has_prog:
                    try:
                        android_opts = build_ydl_opts("YouTube")
                        android_opts['extractor_args'] = {'youtube': {'player_client': ['android']}}
                        with yt_dlp.YoutubeDL(android_opts) as a_ydl:
                            a_info = a_ydl.extract_info(url, download=False)
                            if a_info and a_info.get('formats'):
                                a_progs = [
                                    f for f in a_info['formats']
                                    if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and
                                    'm3u8' not in f.get('url', '') and 'manifest' not in f.get('url', '')
                                ]
                                if a_progs:
                                    if 'formats' not in info or not info['formats']:
                                        info['formats'] = []
                                    info['formats'].extend(a_progs)
                    except Exception as ae:
                        print(f"[ANDROID PROG NOTICE]: {ae}")

            extracted_formats, video_url, audio_url = build_formats(info)
            if video_url and extracted_formats:
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
                    "formats": extracted_formats,
                    "requires_ad_unlock": False,
                    "error": None,
                }
        except Exception as parse_err:
            print(f"[FORMAT BUILD ERROR]: {parse_err}")

    # ── YouTube Engine Fallback 2: pytubefix ──
    if platform == "YouTube":
        try:
            pytube_res = try_pytubefix(url, use_cookies=True)
            if pytube_res and pytube_res.get("success"):
                return pytube_res
        except Exception as pe1:
            print(f"[PYTUBEFIX COOKIE NOTICE]: {pe1}")

        # Retry pytubefix without cookies in case cookies are expired/flagged
        try:
            pytube_clean_res = try_pytubefix(url, use_cookies=False)
            if pytube_clean_res and pytube_clean_res.get("success"):
                return pytube_clean_res
        except Exception as pe2:
            print(f"[PYTUBEFIX CLEAN NOTICE]: {pe2}")

        # ── YouTube Engine Fallback 3: Invidious / Piped API ──
        yt_id = extract_youtube_id(url)
        if yt_id:
            try:
                inv_data = try_invidious(yt_id)
                if inv_data:
                    inv_res = parse_invidious_response(inv_data, yt_id, url)
                    if inv_res and inv_res.get("success"):
                        return inv_res
            except Exception as ie:
                print(f"[INVIDIOUS NOTICE]: {ie}")

            try:
                piped_data = try_piped(yt_id)
                if piped_data:
                    piped_res = parse_piped_response(piped_data, yt_id, url)
                    if piped_res and piped_res.get("success"):
                        return piped_res
            except Exception as pie:
                print(f"[PIPED NOTICE]: {pie}")

    # ── TikTok Engine Fallback: TikWM ──
    if platform == "TikTok":
        tikwm_res = try_tikwm(url)
        if tikwm_res and tikwm_res.get("success"):
            return tikwm_res

    # ── Instagram Fallbacks: parth-dl then Embed Scraper ──
    if platform == "Instagram":
        parth_res = try_parth_dl(url)
        if parth_res and parth_res.get("success"):
            return parth_res
        ig_res = try_instagram_embed(url)
        if ig_res and ig_res.get("success"):
            return ig_res

    # ── Vimeo specific friendly failure note ──
    if platform == "Vimeo":
        return {
            "success": False,
            "url": url,
            "platform": "Vimeo",
            "title": "Extraction Failed",
            "thumbnail": None,
            "duration": 0,
            "duration_formatted": "00:00",
            "video_url": None,
            "audio_url": None,
            "formats": [],
            "error": "Could not extract Vimeo video. This video is either private or restricted to adaptive HLS streaming by the creator without progressive MP4 download permissions.",
        }

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


