import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger("firebase_service")

# State trackers
_firebase_initialized = False
_firestore_db = None
_project_id = None
_init_error = None

try:
    import firebase_admin
    from firebase_admin import credentials, auth, firestore
    FIREBASE_SDK_INSTALLED = True
except ImportError:
    FIREBASE_SDK_INSTALLED = False
    logger.warning("firebase-admin package is not installed. Run 'pip install firebase-admin' to enable backend Firebase features.")


def initialize_firebase() -> bool:
    """
    Initializes Firebase Admin SDK using the first available credential source:
    1. FIREBASE_SERVICE_ACCOUNT_KEY env var (JSON string)
    2. FIREBASE_SERVICE_ACCOUNT_PATH env var (Path to .json)
    3. 'firebase-credentials.json' or 'serviceAccountKey.json' in backend or project root
    4. Google Application Default Credentials
    """
    global _firebase_initialized, _firestore_db, _project_id, _init_error

    if not FIREBASE_SDK_INSTALLED:
        _init_error = "firebase-admin SDK is not installed in the Python environment."
        return False

    if _firebase_initialized:
        return True

    # Avoid duplicate initialization if app already exists
    if firebase_admin._apps:
        try:
            app = firebase_admin.get_app()
            _project_id = app.project_id
            _firestore_db = firestore.client()
            _firebase_initialized = True
            logger.info("Firebase Admin already initialized.")
            return True
        except Exception as e:
            logger.warning(f"Error accessing existing Firebase app: {e}")

    cred = None
    cred_source = None

    # Check 1: Inline JSON in environment variable
    env_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
    if env_json:
        try:
            cert_dict = json.loads(env_json)
            cred = credentials.Certificate(cert_dict)
            cred_source = "FIREBASE_SERVICE_ACCOUNT_KEY env var"
        except Exception as e:
            logger.warning(f"Failed to parse FIREBASE_SERVICE_ACCOUNT_KEY env JSON: {e}")

    # Check 2: Path in environment variable
    if not cred:
        env_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
        if env_path and os.path.isfile(env_path):
            try:
                cred = credentials.Certificate(env_path)
                cred_source = f"path: {env_path}"
            except Exception as e:
                logger.warning(f"Failed to load credentials from {env_path}: {e}")

    # Check 3: Standard local credential file names
    if not cred:
        search_dirs = [
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),  # backend/
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),  # workspace root
            os.path.dirname(__file__),  # backend/app/
        ]
        target_files = ["firebase-credentials.json", "serviceAccountKey.json", "firebase-key.json"]
        for directory in search_dirs:
            for fname in target_files:
                candidate = os.path.join(directory, fname)
                if os.path.isfile(candidate):
                    try:
                        cred = credentials.Certificate(candidate)
                        cred_source = f"file: {candidate}"
                        break
                    except Exception as e:
                        logger.warning(f"Failed to parse certificate from {candidate}: {e}")
            if cred:
                break

    # Check 4: Application Default Credentials fallback (only if env var explicitly set to avoid metadata server timeouts)
    if not cred and os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            cred = credentials.ApplicationDefault()
            cred_source = "ApplicationDefault (GOOGLE_APPLICATION_CREDENTIALS)"
        except Exception:
            cred = None

    if cred:
        try:
            app = firebase_admin.initialize_app(cred)
            _project_id = app.project_id or getattr(cred, "project_id", "connected")
            try:
                _firestore_db = firestore.client()
            except Exception as fe:
                logger.warning(f"Firestore client initialization warning: {fe}")
                _firestore_db = None

            _firebase_initialized = True
            _init_error = None
            logger.info(f"Firebase Admin successfully initialized from {cred_source} (project: {_project_id})")
            return True
        except Exception as e:
            _init_error = str(e)
            logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
            return False
    else:
        _init_error = "No valid Firebase credentials found. Provide serviceAccountKey.json or FIREBASE_SERVICE_ACCOUNT_KEY."
        logger.info(f"Firebase Admin running in standby mode: {_init_error}")
        return False


def is_firebase_available() -> bool:
    """Returns True if Firebase is initialized and ready."""
    return _firebase_initialized


def get_firebase_status() -> Dict[str, Any]:
    """Returns status diagnostics for health & diagnostics endpoints."""
    return {
        "sdk_installed": FIREBASE_SDK_INSTALLED,
        "initialized": _firebase_initialized,
        "project_id": _project_id,
        "firestore_available": _firestore_db is not None,
        "mode": "live" if _firebase_initialized else "standby",
        "notice": _init_error if not _firebase_initialized else "Firebase services connected and active."
    }


def verify_firebase_token(id_token: str) -> Optional[Dict[str, Any]]:
    """
    Verifies a Firebase ID token sent in the Authorization header.
    Returns decoded token dictionary (including 'uid', 'email', 'name', 'picture') or None.
    """
    if not _firebase_initialized or not FIREBASE_SDK_INSTALLED:
        return None

    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        return None


def save_download_to_firestore(uid: str, download_data: Dict[str, Any]) -> Optional[str]:
    """
    Records a user's download or extraction event in Cloud Firestore under:
    users/{uid}/downloads/{auto_doc_id}
    """
    if not _firestore_db:
        return None

    try:
        doc_data = {
            "title": download_data.get("title", "Unknown Media"),
            "url": download_data.get("url", ""),
            "platform": download_data.get("platform", "Unknown"),
            "thumbnail": download_data.get("thumbnail"),
            "duration": download_data.get("duration", 0),
            "duration_formatted": download_data.get("duration_formatted", "00:00"),
            "format_chosen": download_data.get("format_chosen"),
            "created_at": firestore.SERVER_TIMESTAMP,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        # Add to subcollection
        user_downloads_ref = _firestore_db.collection("users").document(uid).collection("downloads")
        _, doc_ref = user_downloads_ref.add(doc_data)
        return doc_ref.id
    except Exception as e:
        logger.error(f"Error saving download event to Firestore: {e}")
        return None


def get_user_downloads_from_firestore(uid: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Retrieves the most recent downloads for a user from Cloud Firestore.
    """
    if not _firestore_db:
        return []

    try:
        user_downloads_ref = _firestore_db.collection("users").document(uid).collection("downloads")
        query = user_downloads_ref.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)
        docs = query.stream()

        results = []
        for doc in docs:
            item = doc.to_dict()
            item["id"] = doc.id
            if "created_at" in item and item["created_at"]:
                # Convert timestamp if needed
                try:
                    item["created_at"] = str(item["created_at"])
                except Exception:
                    pass
            results.append(item)
        return results
    except Exception as e:
        logger.error(f"Error retrieving downloads from Firestore: {e}")
        return []


# Auto-initialize on import in standby/live mode
initialize_firebase()
