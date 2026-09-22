import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.firebase_service import (
    get_firebase_status,
    verify_firebase_token,
    save_download_to_firestore,
    get_user_downloads_from_firestore
)

client = TestClient(app)

def test_firebase_status_endpoint():
    response = client.get("/api/firebase/status")
    assert response.status_code == 200
    data = response.json()
    assert "sdk_installed" in data
    assert "initialized" in data
    assert "mode" in data
    assert data["sdk_installed"] is True

def test_health_check_includes_firebase():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "firebase" in data
    assert "mode" in data["firebase"]

def test_unauthenticated_user_history():
    # Calling history without header should return 401
    response = client.get("/api/user/history")
    assert response.status_code == 401

def test_unauthenticated_user_history_record():
    # Calling history record without header should return 401
    payload = {
        "title": "Test Video",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "platform": "YouTube"
    }
    response = client.post("/api/user/history/record", json=payload)
    assert response.status_code == 401

def test_invalid_token_rejected():
    headers = {"Authorization": "Bearer invalid_fake_token_12345"}
    response = client.get("/api/user/history", headers=headers)
    assert response.status_code == 401

def test_firebase_service_safe_fallbacks():
    # When not initialized, verify_firebase_token should return None without throwing
    assert verify_firebase_token("fake_token") is None
    # Firestore calls should gracefully return None or empty list
    assert save_download_to_firestore("test_uid", {"title": "Sample"}) is None
    assert get_user_downloads_from_firestore("test_uid") == []
