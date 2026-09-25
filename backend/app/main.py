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

from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI(
    title="Social Media Downloader API",
    description="FastAPI service powered by yt-dlp to extract video metadata & direct stream links safely.",
    version="1.0.0"
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    firebase_info = get_firebase_status()
    raw_cookies = os.environ.get("YOUTUBE_COOKIES", "")
    return {
        "status": "online",
        "service": "Social Media Downloader API",
        "version": "1.2.0",
        "youtube_cookies_present": bool(raw_cookies),
        "youtube_cookies_length": len(raw_cookies),
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
        "cookie_file": c_path,
        "cookie_file_exists": bool(c_path and os.path.exists(c_path)),
        "cookie_header_length": len(c_hdr) if c_hdr else 0,
        "sample": c_hdr[:50] if c_hdr else None
    }

    import yt_dlp
    clients_to_test = ['android', 'ios', 'web']
    diag["clients_results"] = {}
    for c in clients_to_test:
        ct0 = time.time()
        try:
            test_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'format': 'all',
                'socket_timeout': 6,
                'retries': 0,
                'geo_bypass': True,
                'extractor_args': {'youtube': {'player_client': [c]}}
            }
            if c_path and os.path.exists(c_path):
                test_opts['cookiefile'] = c_path
            with yt_dlp.YoutubeDL(test_opts) as ydl:
                res_info = ydl.extract_info(url, download=False)
                diag["clients_results"][c] = {
                    "success": True,
                    "elapsed": round(time.time() - ct0, 2),
                    "title": res_info.get("title"),
                    "formats": len(res_info.get("formats", []))
                }
        except Exception as ce:
            diag["clients_results"][c] = {
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
        raise HTTPException(status_code=400, detail="Invalid URL scheme")

    # Sanitize filename
    safe_filename = re.sub(r'[^\w\s.-]', '', filename or "video.mp4").strip() or "video.mp4"
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
