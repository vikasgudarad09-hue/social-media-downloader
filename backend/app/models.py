from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional, List
import re

class ExtractRequest(BaseModel):
    url: str

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("URL cannot be empty")
        v = v.strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Invalid URL scheme. Only HTTP and HTTPS URLs are allowed.")
        if len(v) > 2048:
            raise ValueError("URL length exceeds maximum allowed limit (2048 characters).")
        # Sanitize against potential injection strings
        if any(c in v for c in ['\n', '\r', '\0', ';', '`']):
            raise ValueError("URL contains invalid control characters.")
        return v

class MediaFormat(BaseModel):
    format_id: str
    ext: str
    resolution: Optional[str] = "Unknown"
    filesize_approx: Optional[str] = None
    url: str
    vcodec: Optional[str] = None
    acodec: Optional[str] = None

class ExtractResponse(BaseModel):
    success: bool
    url: str
    platform: str
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[int] = 0
    duration_formatted: str = "00:00"
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    formats: List[MediaFormat] = []
    error: Optional[str] = None
