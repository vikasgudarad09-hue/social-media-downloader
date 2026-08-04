import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from app.models import ExtractRequest, ExtractResponse
from app.extractor import (
    extract_media_info, try_piped, try_invidious,
    get_invidious_instances, extract_youtube_id, http_get_json
)
import yt_dlp

app = FastAPI(
    title="Social Media Downloader API",
    description="FastAPI service powered by yt-dlp to extract video metadata & direct stream links safely.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Social Media Downloader API",
        "endpoints": {"extract": "POST /api/extract", "diagnose": "GET /api/diagnose"}
    }

@app.get("/api/diagnose")
def diagnose():
    """Test each YouTube engine from this server to see what works."""
    video_id = "9bZkp7q19f0"  # Gangnam Style
    results = {}

    # Test yt-dlp
    try:
        opts = {
            'quiet': True, 'skip_download': True, 'socket_timeout': 10,
            'extractor_args': {'youtube': {'player_client': ['ios', 'android_embedded', 'tv_embedded']}},
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            results['ytdlp'] = "OK: " + (info.get('title', 'no title') if info else 'no info')
    except Exception as e:
        results['ytdlp'] = "FAIL: " + str(e)[:150]

    # Test Piped instances one by one
    from app.extractor import PIPED_INSTANCES
    results['piped'] = {}
    for inst in PIPED_INSTANCES:
        data = http_get_json(f"{inst}/streams/{video_id}", timeout=6)
        if data and data.get('title'):
            results['piped'][inst] = "OK: " + data.get('title', '')
        elif data:
            results['piped'][inst] = "FAIL: " + str(data.get('error', 'no title'))
        else:
            results['piped'][inst] = "FAIL: no response"

    # Test Invidious instances one by one
    instances = get_invidious_instances()
    results['invidious'] = {}
    for inst in instances:
        data = http_get_json(f"{inst}/api/v1/videos/{video_id}?fields=title", timeout=6)
        if data and data.get('title'):
            results['invidious'][inst] = "OK: " + data.get('title', '')
        elif data:
            results['invidious'][inst] = "FAIL: " + str(data)[:100]
        else:
            results['invidious'][inst] = "FAIL: no response"

    return results

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
