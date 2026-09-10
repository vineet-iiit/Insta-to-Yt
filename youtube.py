"""
youtube.py — YouTube OAuth (web flow) and video upload.

Supports two auth modes:
  1. Web flow (cloud/production) — proper redirect-based OAuth
  2. Local flow — opens browser on the machine running the server
"""

from pathlib import Path
from typing import Callable, Optional
import base64
import hashlib
import secrets

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_TOKEN_JSON,
    TOKEN_FILE,
    YOUTUBE_SCOPES,
    YOUTUBE_DEFAULT_CATEGORY,
    YOUTUBE_DEFAULT_PRIVACY,
    YOUTUBE_TITLE_MAX_CHARS,
    credentials_configured,
    ENV_FILE,
    is_local,
)


class YouTubeAuthError(Exception):
    pass


class YouTubeUploadError(Exception):
    pass


# ── Build client config dict from env vars ────────────────────────────────────

def _client_config() -> dict:
    return {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost", "urn:ietf:wg:oauth:2.0:oob"],
        }
    }


def _installed_client_config() -> dict:
    """Config for InstalledAppFlow (local dev only)."""
    return {
        "installed": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


# ── Token loading / saving ────────────────────────────────────────────────────

def _load_credentials() -> Optional[Credentials]:
    """Try to load credentials from env var first, then from file."""
    # 1. Try env var (cloud deployments)
    if GOOGLE_TOKEN_JSON:
        try:
            return Credentials.from_authorized_user_info(
                eval(GOOGLE_TOKEN_JSON) if GOOGLE_TOKEN_JSON.startswith("{") else {},
                YOUTUBE_SCOPES
            )
        except Exception:
            pass
        try:
            import json
            return Credentials.from_authorized_user_info(
                json.loads(GOOGLE_TOKEN_JSON), YOUTUBE_SCOPES
            )
        except Exception:
            pass

    # 2. Try file (local dev)
    if TOKEN_FILE.exists():
        try:
            return Credentials.from_authorized_user_file(str(TOKEN_FILE), YOUTUBE_SCOPES)
        except Exception:
            pass

    return None


def _save_credentials(creds: Credentials) -> str:
    """Save credentials to file and return the JSON string (for env var storage)."""
    token_json = creds.to_json()
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        f.write(token_json)
    return token_json


# ── PKCE helpers ─────────────────────────────────────────────────────────────

def generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code_verifier and code_challenge (S256 method)."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    return code_verifier, code_challenge


# ── Web OAuth Flow (for cloud/production) ─────────────────────────────────────

def get_web_auth_url(redirect_uri: str, code_verifier: str) -> tuple[str, str]:
    """
    Generate a Google OAuth URL for the web flow (with PKCE).
    Returns (auth_url, state).
    """
    if not credentials_configured():
        raise YouTubeAuthError("Google credentials not configured in environment variables.")

    _, code_challenge = generate_pkce_pair() if not code_verifier else (
        None,
        base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b'=').decode()
    )

    flow = Flow.from_client_config(
        _client_config(),
        scopes=YOUTUBE_SCOPES,
        redirect_uri=redirect_uri,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )
    return auth_url, state


def exchange_web_code(code: str, state: str, redirect_uri: str, code_verifier: str) -> str:
    """
    Exchange an OAuth authorization code for credentials (with PKCE).
    Saves the token to file and returns the token JSON string.
    """
    flow = Flow.from_client_config(
        _client_config(),
        scopes=YOUTUBE_SCOPES,
        state=state,
        redirect_uri=redirect_uri,
    )
    flow.fetch_token(code=code, code_verifier=code_verifier)
    creds = flow.credentials
    return _save_credentials(creds)


# ── Get Authenticated Service ─────────────────────────────────────────────────

def get_authenticated_service(log: Optional[Callable[[str], None]] = None):
    """
    Return an authenticated YouTube API service.
    Loads existing token (from env or file) and refreshes if needed.
    For local dev with no token: falls back to local browser OAuth.
    """
    def _log(msg: str) -> None:
        if log:
            log(msg)

    if not credentials_configured():
        raise YouTubeAuthError(
            f"Google credentials not configured!\n"
            f"Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your environment."
        )

    creds = _load_credentials()

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        _log("🔄 Refreshing YouTube access token…")
        try:
            creds.refresh(Request())
            _save_credentials(creds)
            _log("✅ Token refreshed")
        except Exception:
            _log("⚠️ Refresh failed — re-authentication needed")
            creds = None

    # Local dev fallback: open browser
    if not creds and is_local():
        _log("🌐 Opening browser for YouTube authentication…")
        flow = InstalledAppFlow.from_client_config(
            _installed_client_config(), YOUTUBE_SCOPES
        )
        creds = flow.run_local_server(port=0, open_browser=True)
        _save_credentials(creds)
        _log("✅ Authenticated and token saved")

    if not creds:
        raise YouTubeAuthError(
            "Not authenticated. Please connect your YouTube account first."
        )

    return build("youtube", "v3", credentials=creds)


def is_authenticated() -> bool:
    """Return True if a valid or refreshable token exists."""
    creds = _load_credentials()
    if not creds:
        return False
    return creds.valid or (creds.expired and bool(creds.refresh_token))


# ── Upload ────────────────────────────────────────────────────────────────────

def upload_video(
    service,
    video_path: Path,
    caption: str,
    log: Optional[Callable[[str], None]] = None,
) -> str:
    """Upload video to YouTube. Returns the YouTube URL."""
    def _log(msg: str) -> None:
        if log:
            log(msg)

    raw_title = caption.strip().split("\n")[0] if caption.strip() else "Instagram Video"
    title = raw_title[:YOUTUBE_TITLE_MAX_CHARS] or "Instagram Video"
    description = (caption + "\n\n📸 Originally posted on Instagram.") if caption else "📸 Originally posted on Instagram."

    _log(f"📝 Title: {title[:60]}{'…' if len(title) > 60 else ''}")
    _log(f"🔒 Privacy: {YOUTUBE_DEFAULT_PRIVACY}")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": YOUTUBE_DEFAULT_CATEGORY,
        },
        "status": {
            "privacyStatus": YOUTUBE_DEFAULT_PRIVACY,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=5 * 1024 * 1024,
    )

    _log("🚀 Starting YouTube upload…")

    try:
        request = service.videos().insert(
            part="snippet,status", body=body, media_body=media
        )
        response = None
        last_pct = -1
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                if pct - last_pct >= 10 or pct >= 99:
                    last_pct = pct
                    _log(f"   📤 Upload progress: {pct}%")

        video_id = response.get("id", "")
        _log(f"🎉 Upload complete!")
        return f"https://youtu.be/{video_id}"

    except HttpError as exc:
        raise YouTubeUploadError(f"YouTube API error {exc.resp.status}: {exc.content.decode()}") from exc
    except Exception as exc:
        raise YouTubeUploadError(str(exc)) from exc
