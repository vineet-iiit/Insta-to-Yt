"""
config.py — App-wide configuration. Loads from .env for local dev,
and from actual environment variables when deployed to Railway/cloud.
"""

import os
import secrets
import tempfile
from pathlib import Path

from dotenv import load_dotenv

# ── Base Paths ────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.resolve()
TOKENS_DIR = BASE_DIR / "tokens"
TEMP_DIR   = Path(tempfile.gettempdir()) / "insta_yt_bot"

TOKENS_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

# ── Load .env (only used locally; on Railway env vars are set directly) ───────
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=False)  # env vars from host take priority

# ── Google / YouTube credentials ──────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

# Token can be persisted as a JSON string in env (for cloud deployments)
# This way it survives container restarts on Railway
GOOGLE_TOKEN_JSON = os.getenv("GOOGLE_TOKEN_JSON", "")   # full token JSON string

TOKEN_FILE     = TOKENS_DIR / "token.json"
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

# ── Server settings ───────────────────────────────────────────────────────────
PORT       = int(os.getenv("PORT", 5000))

# APP_URL: the public URL of this app (used for OAuth redirect URI)
# Set this in Railway to your Railway domain, e.g. https://my-app.railway.app
APP_URL = os.getenv("APP_URL", f"http://localhost:{PORT}")

# Flask session secret — must be stable across restarts for OAuth state to work
# Railway: set SECRET_KEY as an env var
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))

# ── YouTube upload defaults ───────────────────────────────────────────────────
YOUTUBE_DEFAULT_PRIVACY  = os.getenv("YOUTUBE_PRIVACY", "public")
YOUTUBE_DEFAULT_CATEGORY = os.getenv("YOUTUBE_CATEGORY_ID", "22")
YOUTUBE_TITLE_MAX_CHARS  = 100

# ── yt-dlp ───────────────────────────────────────────────────────────────────
YT_DLP_FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

# ── App Info ─────────────────────────────────────────────────────────────────
APP_NAME    = "Insta → YouTube Bot"
APP_VERSION = "1.2"


def credentials_configured() -> bool:
    """Return True if Google OAuth credentials are properly set."""
    return bool(
        GOOGLE_CLIENT_ID
        and GOOGLE_CLIENT_SECRET
        and "your_client_id" not in GOOGLE_CLIENT_ID
        and "your_client_secret" not in GOOGLE_CLIENT_SECRET
    )


def get_redirect_uri() -> str:
    """Build the OAuth redirect URI based on APP_URL."""
    return f"{APP_URL.rstrip('/')}/oauth/callback"


def is_local() -> bool:
    """Return True when running locally (not on cloud)."""
    return "localhost" in APP_URL or "127.0.0.1" in APP_URL
