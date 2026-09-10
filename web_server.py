"""
web_server.py — Flask web server for the Instagram → YouTube Bot.
Supports local dev and cloud deployment (Railway).
Multi-account YouTube support.
"""

import json
import os
import queue
import threading
import time
from pathlib import Path

# Allow OAuth over HTTP for local development
if os.getenv("APP_ENV", "development") != "production":
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

from flask import (
    Flask, Response, jsonify, redirect, render_template,
    request, send_from_directory, session, url_for
)
from flask_cors import CORS

from config import (
    APP_NAME, APP_VERSION, APP_URL, ENV_FILE, PORT, SECRET_KEY,
    credentials_configured, get_redirect_uri, is_local,
)
import instagram as insta
import youtube as yt

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = SECRET_KEY
CORS(app)


# ── Static / PWA routes ────────────────────────────────────────────────────────

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(Path(__file__).parent / "static", filename)


@app.route("/manifest.json")
def manifest():
    return send_from_directory(Path(__file__).parent / "static", "manifest.json")


# ── Main page ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/share")
def share_target():
    """
    Web Share Target handler — called when user shares a link from Instagram.
    Redirects to home page with the URL as a query param so JS can pre-fill it.
    """
    # Instagram shares the URL in 'url' or sometimes embeds it in 'text'
    url = (
        request.args.get("url")
        or request.args.get("text")
        or request.args.get("title")
        or ""
    ).strip()
    return redirect(f"/?shared_url={url}")


# ── API: Status ───────────────────────────────────────────────────────────────

@app.route("/api/status")
def status():
    creds_ok = credentials_configured()
    accounts = yt.list_accounts() if creds_ok else []
    return jsonify({
        "credentials_configured": creds_ok,
        "youtube_authenticated": len(accounts) > 0,
        "accounts": accounts,
        "is_local": is_local(),
    })


@app.route("/api/debug")
def debug():
    return jsonify({
        "APP_URL": APP_URL,
        "redirect_uri": get_redirect_uri(),
        "credentials_configured": credentials_configured(),
        "client_id_prefix": os.getenv("GOOGLE_CLIENT_ID", "")[:30] + "...",
        "is_local": is_local(),
        "PORT": PORT,
    })


# ── API: Accounts ─────────────────────────────────────────────────────────────

@app.route("/api/accounts")
def get_accounts():
    accounts = yt.list_accounts()
    return jsonify({"accounts": accounts})


@app.route("/api/accounts/<account_id>/delete", methods=["POST"])
def delete_account(account_id: str):
    yt.delete_account(account_id)
    return jsonify({"success": True})


@app.route("/api/accounts/export")
def export_accounts():
    """Return accounts JSON for saving as ACCOUNTS_JSON env var."""
    return jsonify({"accounts_json": yt.get_accounts_export_json()})


# ── OAuth: Web Flow ───────────────────────────────────────────────────────────

@app.route("/oauth/start")
def oauth_start():
    """Redirect user to Google's OAuth consent screen (with PKCE)."""
    if not credentials_configured():
        return "❌ Google credentials not configured.", 400

    try:
        redirect_uri = get_redirect_uri()
        code_verifier, _ = yt.generate_pkce_pair()
        session["code_verifier"] = code_verifier
        auth_url, state = yt.get_web_auth_url(redirect_uri, code_verifier)
        session["oauth_state"] = state
        return redirect(auth_url)
    except Exception as exc:
        return f"❌ OAuth error: {exc}", 500


@app.route("/oauth/callback")
def oauth_callback():
    """Handle Google's redirect after user grants permission."""
    code  = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    if error:
        return render_template("oauth_result.html", success=False,
                               message=f"Google denied access: {error}")

    if not code:
        return render_template("oauth_result.html", success=False,
                               message="No authorization code received from Google.")

    # Verify state
    expected_state = session.get("oauth_state")
    if expected_state and state != expected_state:
        return render_template("oauth_result.html", success=False,
                               message="OAuth state mismatch. Please try again.")

    try:
        redirect_uri = get_redirect_uri()
        code_verifier = session.get("code_verifier", "")
        token_json = yt.exchange_web_code(code, state, redirect_uri, code_verifier)

        # Save as new account
        acc_id = yt.save_new_account(token_json)
        accounts = yt.list_accounts()
        new_acc = next((a for a in accounts if a["id"] == acc_id), {})
        channel_name = new_acc.get("channel_name", "YouTube Account")

        return render_template(
            "oauth_result.html",
            success=True,
            channel_name=channel_name,
            is_cloud=not is_local(),
        )
    except Exception as exc:
        return render_template("oauth_result.html", success=False, message=str(exc))


# ── API: Upload pipeline ───────────────────────────────────────────────────────

@app.route("/api/upload", methods=["POST"])
def upload():
    data = request.get_json(force=True)
    url        = (data.get("url") or "").strip()
    account_id = (data.get("account_id") or "").strip()

    if not url or not url.startswith("http"):
        return jsonify({"success": False, "error": "Please provide a valid Instagram URL."}), 400

    if not credentials_configured():
        return jsonify({"success": False, "error": "Google credentials not configured."}), 400

    accounts = yt.list_accounts()
    if not accounts:
        return jsonify({"success": False, "error": "No YouTube account connected. Please add one first."}), 401

    # Validate account_id or pick first valid
    if not account_id or not any(a["id"] == account_id for a in accounts):
        account_id = accounts[0]["id"]

    job_id = str(int(time.time() * 1000))
    app.config[f"queue_{job_id}"] = queue.Queue()

    def _pipeline():
        q: queue.Queue = app.config[f"queue_{job_id}"]

        def log(msg: str, type_: str = "info"):
            q.put({"type": type_, "message": msg})

        try:
            acc_name = next((a["channel_name"] for a in accounts if a["id"] == account_id), account_id)
            log(f"📺 Uploading to: {acc_name}")
            log("🔍 Extracting Instagram video info…")

            video_path, caption = insta.download_instagram_video(
                url, progress_callback=lambda m: log(m)
            )

            service = yt.get_service_for_account(account_id, log=log)
            video_url = yt.upload_video(service, video_path, caption, log=log)

            log("✅ Upload complete!", "success")
            log(video_url, "link")

        except insta.InstagramDownloadError as exc:
            log(f"❌ Instagram error: {exc}", "error")
        except yt.YouTubeAuthError as exc:
            log(f"❌ Auth error: {exc}", "error")
        except yt.YouTubeUploadError as exc:
            log(f"❌ Upload failed: {exc}", "error")
        except Exception as exc:
            log(f"❌ Unexpected error: {exc}", "error")
        finally:
            q.put({"type": "done"})

    threading.Thread(target=_pipeline, daemon=True).start()
    return jsonify({"success": True, "job_id": job_id})


# ── API: SSE Progress stream ───────────────────────────────────────────────────

@app.route("/api/progress/<job_id>")
def progress(job_id: str):
    q: queue.Queue = app.config.get(f"queue_{job_id}")
    if q is None:
        return Response('data: {"type":"error","message":"Job not found"}\n\n',
                        mimetype="text/event-stream")

    def generate():
        yield f"data: {json.dumps({'type': 'connected'})}\n\n"
        while True:
            try:
                msg = q.get(timeout=30)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("type") == "done":
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import socket

    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    ip = get_local_ip()
    print("\n" + "="*55)
    print("  Insta -> YouTube Bot  -- Web Server")
    print("="*55)
    print(f"  [PC]     http://127.0.0.1:{PORT}")
    print(f"  [MOBILE] http://{ip}:{PORT}")
    print("="*55)
    print("  Open the MOBILE URL on your phone (same WiFi)")
    print("  Press Ctrl+C to stop")
    print("="*55 + "\n")

    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
