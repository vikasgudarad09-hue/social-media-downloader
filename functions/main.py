import os
import sys

# Ensure functions root is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from firebase_functions import https_fn, options
from a2wsgi import ASGIMiddleware
from app.main import app as fastapi_app

# Wrap FastAPI ASGI app to WSGI for Firebase Functions 2nd Gen
wsgi_app = ASGIMiddleware(fastapi_app)

@https_fn.on_request(
    memory=options.MemoryOption.GB_1,
    timeout_sec=300,
    min_instances=0,
    max_instances=10
)
def api(req: https_fn.Request) -> https_fn.Response:
    """
    Firebase Cloud Function 2nd Gen entrypoint for Social Media Downloader API.
    Handles all /api/** extraction, health check, and proxy-download requests.
    FastAPI handles all routing, CORS, and request streaming.
    """
    return https_fn.Response.from_app(wsgi_app, req.environ)
