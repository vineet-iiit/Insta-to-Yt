"""
instagram.py — Download a public Instagram video and extract its caption
using yt-dlp (no Instagram login required for public posts).
"""

import os
import re
import shutil
from pathlib import Path
from typing import Callable, Optional, Tuple

import yt_dlp

from config import TEMP_DIR, YT_DLP_FORMAT


class InstagramDownloadError(Exception):
    """Raised when something goes wrong during Instagram download."""
    pass


def _sanitize_filename(name: str, max_len: int = 80) -> str:
    """Remove characters that are illegal in file names."""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name[:max_len].strip()


def download_instagram_video(
    url: str,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[Path, str]:
    """
    Download a public Instagram post/reel video.

    Parameters
    ----------
    url : str
        The full Instagram post or reel URL.
    progress_callback : callable, optional
        Called with a status string at key steps so the GUI can display progress.

    Returns
    -------
    (video_path, caption) : tuple
        - video_path : Path to the downloaded .mp4 file
        - caption    : The Instagram post caption (may be empty string)

    Raises
    ------
    InstagramDownloadError
        If the download fails for any reason.
    """

    def _log(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    # ── Clean temp folder ────────────────────────────────────────────────────
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    output_template = str(TEMP_DIR / "%(id)s.%(ext)s")

    # ── yt-dlp options ────────────────────────────────────────────────────────
    ydl_opts = {
        "format": YT_DLP_FORMAT,
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # Merge video+audio into a single mp4 when needed
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ],
        # Progress hooks
        "progress_hooks": [_make_progress_hook(_log)],
    }

    _log("🔍 Extracting Instagram video info…")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract metadata WITHOUT downloading first to get the caption
            info = ydl.extract_info(url, download=False)
            if info is None:
                raise InstagramDownloadError("Could not extract video info from the URL.")

            caption: str = info.get("description", "") or info.get("title", "") or ""
            uploader: str = info.get("uploader", "Instagram")
            video_id: str = info.get("id", "video")

            _log(f"📄 Post by @{uploader} — caption captured")
            _log(f"⬇️  Downloading video…")

            # Now actually download
            ydl.download([url])

    except yt_dlp.utils.DownloadError as exc:
        raise InstagramDownloadError(
            f"yt-dlp failed to download the video.\n\nDetails: {exc}"
        ) from exc
    except Exception as exc:
        raise InstagramDownloadError(str(exc)) from exc

    # ── Find the downloaded file ───────────────────────────────────────────────
    downloaded_files = list(TEMP_DIR.glob("*.mp4"))
    if not downloaded_files:
        # Try any video extension as fallback
        downloaded_files = [
            f for f in TEMP_DIR.iterdir()
            if f.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}
        ]

    if not downloaded_files:
        raise InstagramDownloadError(
            "Download appeared to succeed, but no video file was found in temp folder."
        )

    video_path = downloaded_files[0]
    _log(f"✅ Video saved: {video_path.name}")

    return video_path, caption


def _make_progress_hook(log_fn: Callable[[str], None]):
    """Build a yt-dlp progress hook that forwards download speed info."""
    last_reported = [0]  # mutable container for closure

    def hook(d: dict) -> None:
        status = d.get("status", "")
        if status == "downloading":
            pct = d.get("_percent_str", "").strip()
            speed = d.get("_speed_str", "").strip()
            eta = d.get("_eta_str", "").strip()
            # Only report every ~10% to avoid flooding the log
            try:
                pct_val = float(pct.replace("%", ""))
            except (ValueError, AttributeError):
                pct_val = 0
            if pct_val - last_reported[0] >= 10 or pct_val >= 99:
                last_reported[0] = pct_val
                log_fn(f"   📶 {pct} downloaded  |  speed: {speed}  |  ETA: {eta}")
        elif status == "finished":
            log_fn("   ✔ Download complete, processing…")

    return hook
