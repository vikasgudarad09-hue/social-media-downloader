import sys
import os

# Add parent directory of main.py to sys.path so 'app' module can be imported anywhere
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from app.models import ExtractRequest, ExtractResponse
from app.extractor import extract_media_info, get_cookie_file_path
import time
import yt_dlp
from collections import defaultdict

app = FastAPI(
    title="Social Media Downloader API",
    description="FastAPI service powered by yt-dlp to extract video metadata & direct stream links safely.",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiter State: IP -> list of timestamps
RATE_LIMIT_REQUESTS = 15  # Max requests
RATE_LIMIT_WINDOW = 60    # per 60 seconds
ip_request_history = defaultdict(list)

@app.middleware("http")
async def security_and_rate_limit_middleware(request: Request, call_next):
    # 1. Security Headers
    client_ip = request.client.host if request.client else "127.0.0.1"
    
    # 2. Rate Limiting for /api/extract
    if request.url.path == "/api/extract" and request.method == "POST":
        now = time.time()
        # Filter timestamps within window
        history = [t for t in ip_request_history[client_ip] if now - t < RATE_LIMIT_WINDOW]
        ip_request_history[client_ip] = history
        
        if len(history) >= RATE_LIMIT_REQUESTS:
            return Response(
                content='{"detail": "Rate limit exceeded. Please wait a minute before downloading again."}',
                status_code=429,
                media_type="application/json"
            )
        ip_request_history[client_ip].append(now)

    response = await call_next(request)
    
    # Apply Security Headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Social Media Downloader API",
        "endpoints": {
            "extract": "POST /api/extract",
            "debug": "GET /api/debug"
        }
    }

@app.get("/api/debug")
def debug_info():
    """Returns server diagnostic info – useful to verify cookies and yt-dlp version on Render."""
    cookie_file = get_cookie_file_path()
    cookie_status = "Not found"
    cookie_lines = 0
    if cookie_file and os.path.exists(cookie_file):
        try:
            with open(cookie_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = [l for l in f.readlines() if l.strip() and not l.startswith('#')]
                cookie_lines = len(lines)
                cookie_status = f"Loaded ({cookie_lines} cookie entries)"
        except Exception as ex:
            cookie_status = f"Error reading: {ex}"
    return {
        "python_version": sys.version,
        "yt_dlp_version": yt_dlp.version.__version__,
        "cookie_file": cookie_file,
        "cookie_status": cookie_status,
        "env_vars_set": {
            "YOUTUBE_COOKIES_TEXT": bool(os.environ.get("YOUTUBE_COOKIES_TEXT")),
            "COOKIES_TEXT": bool(os.environ.get("COOKIES_TEXT")),
            "YOUTUBE_COOKIES_PATH": bool(os.environ.get("YOUTUBE_COOKIES_PATH")),
        }
    }

@app.post("/api/extract", response_model=ExtractResponse)
def extract_media(request: ExtractRequest):
    result = extract_media_info(request.url.strip())
    if not result.get("success"):
        return ExtractResponse(
            success=False,
            url=request.url,
            platform=result.get("platform", "Unknown"),
            title="Failed to extract media",
            error=result.get("error", "Unknown extraction error")
        )
    
    return ExtractResponse(**result)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
