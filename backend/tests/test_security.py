import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.security import is_safe_proxy_url

client = TestClient(app)


def test_is_safe_proxy_url_blocks_internal_and_metadata():
    # Loopback
    assert is_safe_proxy_url("http://127.0.0.1:8000/api/extract") is False
    assert is_safe_proxy_url("http://localhost:8000/") is False
    assert is_safe_proxy_url("http://[::1]/") is False

    # Private IP ranges
    assert is_safe_proxy_url("http://10.0.0.1/video.mp4") is False
    assert is_safe_proxy_url("http://192.168.1.100/video.mp4") is False
    assert is_safe_proxy_url("http://172.16.0.5/video.mp4") is False

    # Cloud instance metadata endpoints (AWS, GCP, Azure, DigitalOcean)
    assert is_safe_proxy_url("http://169.254.169.254/latest/meta-data/") is False
    assert is_safe_proxy_url("http://metadata.google.internal/computeMetadata/v1/") is False
    assert is_safe_proxy_url("http://0.0.0.0/") is False

    # Non-HTTP schemes
    assert is_safe_proxy_url("file:///etc/passwd") is False
    assert is_safe_proxy_url("ftp://example.com/video.mp4") is False
    assert is_safe_proxy_url("javascript:alert(1)") is False
    assert is_safe_proxy_url("") is False
    assert is_safe_proxy_url(None) is False


def test_is_safe_proxy_url_allows_public_urls():
    # Valid public web domains
    assert is_safe_proxy_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True
    assert is_safe_proxy_url("https://example.com/media.mp4") is True


def test_proxy_download_blocks_ssrf_attacks():
    # Test SSRF payloads against proxy-download
    ssrf_targets = [
        "http://127.0.0.1:8000/api/health",
        "http://localhost:8000/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/admin",
        "ftp://malicious.com/file.mp4",
        "file:///etc/hosts",
    ]
    for target in ssrf_targets:
        res = client.get("/api/proxy-download", params={"url": target})
        assert res.status_code == 400
        assert "Invalid URL scheme" in res.json().get("detail", "") or "restricted" in res.json().get("detail", "")


def test_security_headers_present_on_responses():
    res = client.get("/health")
    assert res.status_code == 200
    headers = res.headers
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "SAMEORIGIN"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in headers.get("permissions-policy", "")
    assert headers.get("cross-origin-opener-policy") == "same-origin-allow-popups"


def test_information_disclosure_mitigated():
    # Check root endpoint
    res = client.get("/", headers={"accept": "application/json"})
    if res.status_code == 200 and res.headers.get("content-type") == "application/json":
        data = res.json()
        assert "youtube_cookies_length" not in data

    # Check diagnose endpoint does not leak cookies sample or file path
    diag_res = client.get("/api/diagnose/youtube")
    if diag_res.status_code == 200:
        data = diag_res.json()
        cookie_info = data.get("cookies_info", {})
        assert "sample" not in cookie_info
        assert "cookie_file" not in cookie_info
        assert "cookie_header_length" not in cookie_info
