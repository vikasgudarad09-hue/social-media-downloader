import pytest
from app.extractor import detect_platform, format_duration, extract_media_info

def test_detect_platform():
    assert detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "YouTube"
    assert detect_platform("https://youtu.be/dQw4w9WgXcQ") == "YouTube"
    assert detect_platform("https://www.instagram.com/p/C1234567/") == "Instagram"
    assert detect_platform("https://www.tiktok.com/@user/video/123456789") == "TikTok"
    assert detect_platform("https://x.com/user/status/123456789") == "X (Twitter)"
    assert detect_platform("https://twitter.com/user/status/123456789") == "X (Twitter)"
    assert detect_platform("https://www.facebook.com/watch/?v=123456") == "Facebook"
    assert detect_platform("https://www.pinterest.com/pin/123456/") == "Pinterest"
    assert detect_platform("https://www.reddit.com/r/videos/comments/12345/") == "Reddit"
    assert detect_platform("https://example.com/video") == "Social Media"

def test_format_duration():
    assert format_duration(0) == "N/A"
    assert format_duration(45) == "00:45"
    assert format_duration(125) == "02:05"
    assert format_duration(3665) == "01:01:05"

def test_extract_invalid_url():
    res = extract_media_info("https://invalid-nonexistent-domain-12345.com/video")
    assert res["success"] is False
    assert res["error"] is not None

def test_extract_sample_youtube_video():
    # Public YouTube sample video (standard test video: Big Buck Bunny or short test video)
    test_url = "https://www.youtube.com/watch?v=aqz-KE-bpKQ" # Big Buck Bunny 60fps 4K - Short Clip
    res = extract_media_info(test_url)
    assert res["platform"] == "YouTube"
    if res["success"]:
        assert "Big Buck Bunny" in res["title"] or len(res["title"]) > 0
        assert res["thumbnail"] is not None
        assert res["video_url"] is not None
