import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, HTTPException, Request, Response, Header
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from app.models import ExtractRequest, ExtractResponse, UserDownloadRecordRequest
from app.extractor import extract_media_info
from app.firebase_service import (
    get_firebase_status,
    verify_firebase_token,
    save_download_to_firestore,
    get_user_downloads_from_firestore
)
import httpx
import re
from typing import Optional

from app.security import is_safe_proxy_url

from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI(
    title="Social Media Downloader API",
    description="FastAPI service powered by yt-dlp to extract video metadata & direct stream links safely.",
    version="1.3.1"
)

# Standard Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    return response

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Secure CORS Middleware (API authentication uses Bearer token in headers, avoid wildcard credentials violation)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

from fastapi.responses import FileResponse

@app.get("/")
def read_root(request: Request):
    index_file = os.path.join(frontend_dir, "index.html")
    accept = request.headers.get("accept", "")
    if os.path.exists(index_file) and ("text/html" in accept or "*/*" in accept):
        return FileResponse(index_file)
    firebase_info = get_firebase_status()
    raw_cookies = os.environ.get("YOUTUBE_COOKIES", "")
    return {
        "status": "online",
        "service": "Social Media Downloader API",
        "version": "1.3.1",
        "youtube_cookies_configured": bool(raw_cookies),
        "firebase": firebase_info["mode"],
        "endpoints": {
            "extract": "POST /api/extract",
            "download": "GET /api/proxy-download",
            "firebase_status": "GET /api/firebase/status",
            "user_history": "GET /api/user/history",
            "record_history": "POST /api/user/history/record",
            "health": "GET /health",
            "diagnose_youtube": "GET /api/diagnose/youtube"
        }
    }

@app.get("/health")
def health_check():
    firebase_info = get_firebase_status()
    return {
        "status": "ok",
        "uptime": "healthy",
        "firebase": {
            "mode": firebase_info["mode"],
            "initialized": firebase_info["initialized"],
            "firestore": firebase_info["firestore_available"]
        }
    }

@app.get("/api/firebase/status")
def firebase_status():
    """Returns the operational status of Firebase services on the backend."""
    return get_firebase_status()

@app.get("/api/diagnose/youtube")
def diagnose_youtube(url: Optional[str] = "https://www.youtube.com/watch?v=bFBvAUEJrS8"):
    diag = {}
    import time
    t0 = time.time()

    from app.extractor import get_clean_youtube_cookies
    c_path, c_hdr = get_clean_youtube_cookies()
    diag["cookies_info"] = {
        "cookie_file_configured": bool(c_path and os.path.exists(c_path)),
        "cookie_header_configured": bool(c_hdr),
    }

    import yt_dlp
    clients_to_test = [
        ('android_clean', ['android'], False),
        ('ios_clean', ['ios'], False),
        ('android_cookies', ['android'], True),
        ('web_cookies', ['web'], True),
    ]
    diag["clients_results"] = {}
    for name, c_list, use_cookie in clients_to_test:
        ct0 = time.time()
        try:
            test_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'format': 'all',
                'socket_timeout': 5,
                'retries': 0,
                'geo_bypass': True,
                'extractor_args': {'youtube': {'player_client': c_list}}
            }
            if use_cookie and c_path and os.path.exists(c_path):
                test_opts['cookiefile'] = c_path
            with yt_dlp.YoutubeDL(test_opts) as ydl:
                res_info = ydl.extract_info(url, download=False)
                diag["clients_results"][name] = {
                    "success": True,
                    "elapsed": round(time.time() - ct0, 2),
                    "title": res_info.get("title"),
                    "formats": len(res_info.get("formats", []))
                }
        except Exception as ce:
            diag["clients_results"][name] = {
                "success": False,
                "elapsed": round(time.time() - ct0, 2),
                "error": str(ce)[:120]
            }

    diag["total_elapsed"] = round(time.time() - t0, 2)
    return diag

@app.post("/api/extract", response_model=ExtractResponse)
def extract_media(request: ExtractRequest, authorization: Optional[str] = Header(None)):
    user = None
    if authorization and isinstance(authorization, str) and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
        user = verify_firebase_token(token)

    result = extract_media_info(request.url.strip())
    if not result.get("success"):
        return ExtractResponse(
            success=False,
            url=request.url,
            platform=result.get("platform", "Unknown"),
            title="Failed to extract media",
            error=result.get("error", "Unknown extraction error")
        )

    # If the user is authenticated with Firebase, save record to Firestore
    if user and user.get("uid"):
        try:
            save_download_to_firestore(user["uid"], result)
        except Exception:
            pass

    return ExtractResponse(**result)

@app.get("/api/user/history")
def get_user_history(authorization: Optional[str] = Header(None), limit: int = 20):
    """
    Fetches the authenticated user's download history from Cloud Firestore.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication token required. Header 'Authorization: Bearer <token>' missing.")

    token = authorization.split("Bearer ", 1)[1].strip()
    user = verify_firebase_token(token)
    if not user or not user.get("uid"):
        raise HTTPException(status_code=401, detail="Invalid or expired Firebase ID token.")

    downloads = get_user_downloads_from_firestore(user["uid"], limit=limit)
    return {
        "success": True,
        "uid": user["uid"],
        "count": len(downloads),
        "downloads": downloads
    }

@app.post("/api/user/history/record")
def record_user_download(record: UserDownloadRecordRequest, authorization: Optional[str] = Header(None)):
    """
    Explicitly logs a completed download action to Cloud Firestore for the user.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication token required.")

    token = authorization.split("Bearer ", 1)[1].strip()
    user = verify_firebase_token(token)
    if not user or not user.get("uid"):
        raise HTTPException(status_code=401, detail="Invalid or expired Firebase ID token.")

    doc_id = save_download_to_firestore(user["uid"], record.model_dump())
    return {
        "success": True,
        "doc_id": doc_id,
        "message": "Download event recorded successfully."
    }

@app.get("/api/proxy-download")
async def proxy_download(request: Request, url: str, filename: Optional[str] = "download.mp4"):
    """
    Proxies media stream with Content-Disposition: attachment header to force
    direct file download in browser instead of playing in a tab.
    Supports Range requests for pause, resume, and streaming.
    """
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="Invalid URL scheme. Only HTTP and HTTPS are permitted.")

    if not is_safe_proxy_url(url):
        raise HTTPException(status_code=400, detail="Requested URL cannot be proxied: Host is restricted or internal.")

    # Sanitize filename
    safe_filename = re.sub(r'[^\w\s.-]', '', filename or "video.mp4").strip() or "video.mp4"
    safe_filename = safe_filename[:120]
    client = httpx.AsyncClient(follow_redirects=True, timeout=90.0)

    try:
        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        }
        if "tiktok" in url.lower():
            req_headers["Referer"] = "https://www.tiktok.com/"
        elif "instagram" in url.lower():
            req_headers["Referer"] = "https://www.instagram.com/"

        # Forward range header if present for fast chunk streaming
        range_header = request.headers.get("range")
        if range_header:
            req_headers["Range"] = range_header

        req = client.build_request("GET", url, headers=req_headers)
        response = await client.send(req, stream=True)

        if response.status_code >= 400:
            await response.aclose()
            await client.aclose()
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=url, status_code=302)

        content_type = response.headers.get("content-type", "application/octet-stream")
        if "m3u8" in url.lower() or "mpegurl" in content_type.lower():
            await response.aclose()
            await client.aclose()
            raise HTTPException(status_code=400, detail="Cannot download an m3u8 playlist manifest directly as a video file. Please use a direct progressive video stream.")


        async def media_stream():
            try:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()

        headers = {
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
            "Accept-Ranges": "bytes",
        }
        if "content-length" in response.headers:
            headers["Content-Length"] = response.headers["content-length"]
        if "content-range" in response.headers:
            headers["Content-Range"] = response.headers["content-range"]

        status = 206 if response.status_code == 206 else 200
        return StreamingResponse(media_stream(), status_code=status, media_type=content_type, headers=headers)

    except Exception:
        await client.aclose()
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=url, status_code=302)

# ─────────────────────────────────────────────
# High-Speed Native Media Conversion API
# ─────────────────────────────────────────────
from fastapi import UploadFile, File, Form, BackgroundTasks
import tempfile
import subprocess
import shutil

def _cleanup_paths(*paths):
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

import asyncio

# Concurrency limiter: Allow up to 6 heavy FFmpeg transcodes simultaneously; queue any others cleanly
_CONVERT_SEMAPHORE = asyncio.Semaphore(6)
MAX_CONVERT_SIZE_BYTES = 400 * 1024 * 1024  # 400 MB protection limit

def _run_ffmpeg_sync(cmd: list, in_path: str, out_path: str) -> None:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    if proc.returncode != 0:
        err_msg = proc.stderr.decode("utf-8", errors="ignore")[-400:]
        raise RuntimeError(f"FFmpeg transcode failed: {err_msg}")

@app.post("/api/convert")
async def api_convert_media(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    format: str = Form(...)
):
    target_fmt = format.lower().strip()
    presets = {
        "mp4": ("video/mp4", ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]),
        "webm": ("video/webm", ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-c:a", "libopus"]),
        "avi": ("video/x-msvideo", ["-c:v", "mpeg4", "-qscale:v", "3", "-c:a", "mp3"]),
        "gif": ("image/gif", ["-t", "10", "-vf", "fps=12,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"]),
        "mp3": ("audio/mpeg", ["-vn", "-c:a", "libmp3lame", "-q:a", "2"]),
        "wav": ("audio/wav", ["-vn", "-c:a", "pcm_s16le"]),
        "ogg": ("audio/ogg", ["-vn", "-c:a", "libvorbis", "-q:a", "4"]),
        "aac": ("audio/aac", ["-vn", "-c:a", "aac", "-b:a", "192k"]),
        "flac": ("audio/flac", ["-vn", "-c:a", "flac"]),
    }

    if target_fmt not in presets:
        raise HTTPException(status_code=400, detail=f"Unsupported target format: {target_fmt}")

    mime_type, ffmpeg_flags = presets[target_fmt]

    in_path = None
    out_path = None

    try:
        raw_ext = os.path.splitext(file.filename or "")[1].lower()
        # Sanitize extension: only alphanumeric chars, max 10 chars
        safe_ext = "." + re.sub(r'[^a-z0-9]', '', raw_ext.lstrip('.'))[:10]
        if safe_ext == ".":
            safe_ext = ".bin"

        with tempfile.NamedTemporaryFile(delete=False, suffix=safe_ext) as in_tmp:
            in_path = in_tmp.name
            # Chunked write with size limit to prevent memory/disk exhaustion
            bytes_written = 0
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                bytes_written += len(chunk)
                if bytes_written > MAX_CONVERT_SIZE_BYTES:
                    in_tmp.close()
                    _cleanup_paths(in_path)
                    raise HTTPException(
                        status_code=413,
                        detail="File too large. Maximum supported conversion size is 400 MB."
                    )
                in_tmp.write(chunk)

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{target_fmt}") as out_tmp:
            out_path = out_tmp.name

        cmd = ["ffmpeg", "-y", "-i", in_path] + ffmpeg_flags + [out_path]

        # Acquire semaphore to safely throttle CPU/RAM under high traffic
        async with _CONVERT_SEMAPHORE:
            await asyncio.to_thread(_run_ffmpeg_sync, cmd, in_path, out_path)

        orig_base = os.path.splitext(file.filename or "media")[0]
        safe_base = re.sub(r'[^a-zA-Z0-9_\- ]', '', orig_base).strip() or "media"
        safe_base = safe_base[:100]
        out_filename = f"{safe_base}.{target_fmt}"

        background_tasks.add_task(_cleanup_paths, in_path, out_path)

        return FileResponse(
            out_path,
            media_type=mime_type,
            filename=out_filename,
            headers={"Content-Disposition": f'attachment; filename="{out_filename}"'}
        )

    except HTTPException:
        _cleanup_paths(in_path, out_path)
        raise
    except subprocess.TimeoutExpired:
        _cleanup_paths(in_path, out_path)
        raise HTTPException(status_code=504, detail="Media conversion timed out (>180s)")
    except Exception as e:
        _cleanup_paths(in_path, out_path)
        raise HTTPException(status_code=500, detail=f"Conversion error: {str(e)}")


# ─────────────────────────────────────────────
# Mount Frontend Web App Static Files
# ─────────────────────────────────────────────
from fastapi.staticfiles import StaticFiles

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
