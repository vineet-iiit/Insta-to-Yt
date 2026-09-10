"""
youtube.py — YouTube OAuth (web flow, PKCE) and video upload.
Supports multiple YouTube accounts.
"""

from pathlib import Path
from typing import Callable, Optional
import base64
import hashlib
import json
import secrets
import uuid

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
    TOKENS_DIR,
    YOUTUBE_SCOPES,
    YOUTUBE_DEFAULT_CATEGORY,
    YOUTUBE_DEFAULT_PRIVACY,
    YOUTUBE_TITLE_MAX_CHARS,
    credentials_configured,
    is_local,
)


class YouTubeAuthError(Exception):
    pass


class YouTubeUploadError(Exception):
    pass


# ── Accounts file ─────────────────────────────────────────────────────────────

ACCOUNTS_FILE = TOKENS_DIR / "accounts.json"


def _load_accounts() -> dict:
    """Load accounts dict from file. Migrates legacy token.json if present."""
    accounts = {}

    # Load from accounts.json
    if ACCOUNTS_FILE.exists():
        try:
            with open(ACCOUNTS_FILE) as f:
                accounts = json.load(f)
        except Exception:
            accounts = {}

    # Migrate legacy single token.json → account
    if not accounts and TOKEN_FILE.exists():
        try:
            token_json = TOKEN_FILE.read_text()
            acc_id = "default"
            accounts[acc_id] = {
                "id": acc_id,
                "channel_name": "YouTube Account",
                "email": "",
                "token_json": token_json,
            }
            _save_accounts(accounts)
        except Exception:
            pass

    # Also load from GOOGLE_TOKEN_JSON env var (cloud)
    if not accounts and GOOGLE_TOKEN_JSON:
        try:
            acc_id = "default"
            accounts[acc_id] = {
                "id": acc_id,
                "channel_name": "YouTube Account",
                "email": "",
                "token_json": GOOGLE_TOKEN_JSON,
            }
        except Exception:
            pass

    return accounts


def _save_accounts(accounts: dict) -> None:
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump(accounts, f, indent=2)


def list_accounts() -> list[dict]:
    """Return list of all connected YouTube accounts (without token JSON)."""
    accounts = _load_accounts()
    result = []
    for acc in accounts.values():
        creds = _creds_from_token_json(acc.get("token_json", ""))
        valid = bool(creds and (creds.valid or (creds.expired and creds.refresh_token)))
        result.append({
            "id": acc["id"],
            "channel_name": acc.get("channel_name", "YouTube Account"),
            "email": acc.get("email", ""),
            "valid": valid,
        })
    return result


def delete_account(account_id: str) -> None:
    accounts = _load_accounts()
    accounts.pop(account_id, None)
    _save_accounts(accounts)


def get_accounts_export_json() -> str:
    """Return all accounts as JSON string for env var backup."""
    return json.dumps(_load_accounts())


# ── Credential helpers ────────────────────────────────────────────────────────

def _creds_from_token_json(token_json: str) -> Optional[Credentials]:
    if not token_json:
        return None
    try:
        return Credentials.from_authorized_user_info(
            json.loads(token_json), YOUTUBE_SCOPES
        )
    except Exception:
        return None


def _refresh_and_save(acc_id: str, creds: Credentials, accounts: dict) -> Credentials:
    try:
        creds.refresh(Request())
        accounts[acc_id]["token_json"] = creds.to_json()
        _save_accounts(accounts)
    except Exception:
        pass
    return creds


# ── Client configs ────────────────────────────────────────────────────────────

def _client_config() -> dict:
    return {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [],
        }
    }


def _installed_client_config() -> dict:
    return {
        "installed": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


# ── PKCE helpers ──────────────────────────────────────────────────────────────

def generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


# ── Web OAuth Flow ────────────────────────────────────────────────────────────

def get_web_auth_url(redirect_uri: str, code_verifier: str) -> tuple[str, str]:
    """Generate Google OAuth URL (with PKCE). Returns (auth_url, state)."""
    if not credentials_configured():
        raise YouTubeAuthError("Google credentials not configured.")

    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

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


def exchange_web_code(
    code: str, state: str, redirect_uri: str, code_verifier: str
) -> str:
    """Exchange OAuth code for token. Returns raw token JSON string."""
    flow = Flow.from_client_config(
        _client_config(),
        scopes=YOUTUBE_SCOPES,
        state=state,
        redirect_uri=redirect_uri,
    )
    flow.fetch_token(code=code, code_verifier=code_verifier)
    return flow.credentials.to_json()


def save_new_account(token_json: str, channel_name: str = "", email: str = "") -> str:
    """
    Save a newly authenticated account. Fetches channel info automatically.
    Returns the new account_id.
    """
    acc_id = uuid.uuid4().hex[:8]

    # Fetch channel name from YouTube API if not provided
    if not channel_name:
        try:
            creds = _creds_from_token_json(token_json)
            svc = build("youtube", "v3", credentials=creds)
            resp = svc.channels().list(part="snippet", mine=True).execute()
            items = resp.get("items", [])
            if items:
                channel_name = items[0]["snippet"].get("title", "YouTube Account")
                email = items[0]["snippet"].get("customUrl", "")
        except Exception:
            channel_name = "YouTube Account"

    accounts = _load_accounts()
    accounts[acc_id] = {
        "id": acc_id,
        "channel_name": channel_name,
        "email": email,
        "token_json": token_json,
    }
    _save_accounts(accounts)
    return acc_id


# ── Get service for account ───────────────────────────────────────────────────

def get_service_for_account(
    account_id: str,
    log: Optional[Callable[[str], None]] = None,
):
    """Return an authenticated YouTube service for the given account."""
    def _log(msg: str) -> None:
        if log:
            log(msg)

    accounts = _load_accounts()
    if account_id not in accounts:
        raise YouTubeAuthError(f"Account '{account_id}' not found. Please reconnect.")

    acc = accounts[account_id]
    creds = _creds_from_token_json(acc.get("token_json", ""))

    if not creds:
        raise YouTubeAuthError("No credentials found for this account. Please reconnect.")

    if creds.expired and creds.refresh_token:
        _log("🔄 Refreshing token…")
        creds = _refresh_and_save(account_id, creds, accounts)

    if not creds.valid:
        raise YouTubeAuthError("Token expired. Please reconnect this account.")

    return build("youtube", "v3", credentials=creds)


def get_authenticated_service(log: Optional[Callable[[str], None]] = None):
    """Return service for ANY available account (backwards compat)."""
    accounts = _load_accounts()
    if accounts:
        first_id = next(iter(accounts))
        return get_service_for_account(first_id, log)
    raise YouTubeAuthError("No accounts connected. Please connect a YouTube account first.")


def is_authenticated() -> bool:
    """Return True if at least one valid account is connected."""
    return len(list_accounts()) > 0


def account_is_valid(account_id: str) -> bool:
    accounts = _load_accounts()
    if account_id not in accounts:
        return False
    creds = _creds_from_token_json(accounts[account_id].get("token_json", ""))
    return bool(creds and (creds.valid or (creds.expired and creds.refresh_token)))


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
    description = (
        (caption + "\n\n📸 Originally posted on Instagram.")
        if caption
        else "📸 Originally posted on Instagram."
    )

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
        req = service.videos().insert(
            part="snippet,status", body=body, media_body=media
        )
        response = None
        last_pct = -1
        while response is None:
            status, response = req.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                if pct - last_pct >= 10 or pct >= 99:
                    last_pct = pct
                    _log(f"   📤 Upload progress: {pct}%")

        video_id = response.get("id", "")
        _log("🎉 Upload complete!")
        return f"https://youtu.be/{video_id}"

    except HttpError as exc:
        raise YouTubeUploadError(
            f"YouTube API error {exc.resp.status}: {exc.content.decode()}"
        ) from exc
    except Exception as exc:
        raise YouTubeUploadError(str(exc)) from exc
