import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from app.models import ExtractRequest, ExtractResponse
from app.extractor import extract_media_info
import httpx
import re
from typing import Optional

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
        "endpoints": {
            "extract": "POST /api/extract",
            "download": "GET /api/proxy-download"
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

@app.get("/api/proxy-download")
async def proxy_download(url: str, filename: Optional[str] = "download.mp4"):
    """
    Proxies media stream with Content-Disposition: attachment header to force
    direct file download in browser instead of playing in a tab.
    """
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="Invalid URL scheme")

    # Sanitize filename
    safe_filename = re.sub(r'[^\w\s.-]', '', filename or "video.mp4").strip() or "video.mp4"

    client = httpx.AsyncClient(follow_redirects=True, timeout=60.0)

    try:
        req = client.build_request("GET", url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        })

        response = await client.send(req, stream=True)
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
        }
        if "content-length" in response.headers:
            headers["Content-Length"] = response.headers["content-length"]

        return StreamingResponse(media_stream(), media_type=content_type, headers=headers)

    except Exception as e:
        await client.aclose()
        raise HTTPException(status_code=500, detail=f"Download proxy error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
