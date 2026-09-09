"""
gui.py — Premium dark-themed desktop GUI for the Instagram → YouTube Bot.
Built with tkinter + ttkbootstrap for a modern, polished look.
"""

import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import scrolledtext
from typing import Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from config import APP_NAME, APP_VERSION, ENV_FILE, credentials_configured
import instagram as insta
import youtube as yt


# ── Colour palette ─────────────────────────────────────────────────────────────
BG_DARK       = "#0d1117"
BG_CARD       = "#161b22"
BG_INPUT      = "#21262d"
ACCENT_PINK   = "#e1306c"   # Instagram pink
ACCENT_RED    = "#ff0000"   # YouTube red
ACCENT_GREEN  = "#3fb950"
ACCENT_YELLOW = "#d29922"
TEXT_PRIMARY  = "#f0f6fc"
TEXT_MUTED    = "#8b949e"
BORDER_COLOR  = "#30363d"


class App(ttk.Window):
    """Main application window."""

    def __init__(self):
        super().__init__(themename="darkly")
        self.title(f"{APP_NAME}  v{APP_VERSION}")
        self.geometry("780x700")
        self.minsize(700, 600)
        self.configure(bg=BG_DARK)
        self.resizable(True, True)

        # State
        self._youtube_service = None
        self._is_running = False

        self._build_ui()
        self._check_auth_status()

    # ── UI Construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        """Assemble all UI widgets."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # ── Header ────────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=BG_DARK, pady=18)
        header.grid(row=0, column=0, sticky="ew", padx=24)

        title_frame = tk.Frame(header, bg=BG_DARK)
        title_frame.pack(side="left")

        # Gradient-style title using two labels side by side
        tk.Label(
            title_frame,
            text="📸 Insta",
            font=("Segoe UI", 22, "bold"),
            fg=ACCENT_PINK,
            bg=BG_DARK,
        ).pack(side="left")
        tk.Label(
            title_frame,
            text=" → ",
            font=("Segoe UI", 22, "bold"),
            fg=TEXT_MUTED,
            bg=BG_DARK,
        ).pack(side="left")
        tk.Label(
            title_frame,
            text="▶ YouTube",
            font=("Segoe UI", 22, "bold"),
            fg=ACCENT_RED,
            bg=BG_DARK,
        ).pack(side="left")

        tk.Label(
            header,
            text=f"v{APP_VERSION}",
            font=("Segoe UI", 9),
            fg=TEXT_MUTED,
            bg=BG_DARK,
        ).pack(side="right", anchor="s", pady=6)

        # Separator
        tk.Frame(self, bg=BORDER_COLOR, height=1).grid(
            row=0, column=0, sticky="ew", padx=0, pady=(70, 0)
        )

        # ── YouTube Auth Card ──────────────────────────────────────────────────
        auth_card = tk.Frame(self, bg=BG_CARD, bd=0, highlightthickness=1,
                             highlightbackground=BORDER_COLOR)
        auth_card.grid(row=1, column=0, sticky="ew", padx=24, pady=(16, 0))
        auth_card.grid_columnconfigure(0, weight=1)

        tk.Label(
            auth_card,
            text="  YouTube Account",
            font=("Segoe UI", 11, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 2))

        auth_inner = tk.Frame(auth_card, bg=BG_CARD)
        auth_inner.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))
        auth_inner.grid_columnconfigure(0, weight=1)

        self.auth_status_label = tk.Label(
            auth_inner,
            text="⚪  Not connected",
            font=("Segoe UI", 10),
            fg=TEXT_MUTED,
            bg=BG_CARD,
            anchor="w",
        )
        self.auth_status_label.grid(row=0, column=0, sticky="w")

        self.auth_btn = ttk.Button(
            auth_inner,
            text="Connect YouTube",
            style="danger.TButton",
            command=self._on_auth_click,
            width=20,
        )
        self.auth_btn.grid(row=0, column=1, padx=(10, 0))

        # Credentials hint
        self.creds_hint = tk.Label(
            auth_card,
            text="",
            font=("Segoe UI", 8),
            fg=ACCENT_YELLOW,
            bg=BG_CARD,
            anchor="w",
            wraplength=700,
            justify="left",
        )
        self.creds_hint.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))

        # ── URL Input Card ─────────────────────────────────────────────────────
        url_card = tk.Frame(self, bg=BG_CARD, bd=0, highlightthickness=1,
                            highlightbackground=BORDER_COLOR)
        url_card.grid(row=2, column=0, sticky="ew", padx=24, pady=(12, 0))
        url_card.grid_columnconfigure(0, weight=1)

        tk.Label(
            url_card,
            text="  Instagram Video URL",
            font=("Segoe UI", 11, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 6))

        self.url_var = tk.StringVar()
        url_entry = tk.Entry(
            url_card,
            textvariable=self.url_var,
            font=("Segoe UI", 11),
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            bd=0,
        )
        url_entry.grid(row=1, column=0, sticky="ew", padx=(16, 8), pady=(0, 14), ipady=8)

        self.upload_btn = ttk.Button(
            url_card,
            text="⬆  Upload to YouTube",
            style="success.TButton",
            command=self._on_upload_click,
            width=22,
        )
        self.upload_btn.grid(row=1, column=1, padx=(0, 16), pady=(0, 14))

        url_card.grid_columnconfigure(0, weight=1)

        tk.Label(
            url_card,
            text="Paste a public Instagram post or Reel link above",
            font=("Segoe UI", 8),
            fg=TEXT_MUTED,
            bg=BG_CARD,
            anchor="w",
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 10))

        # ── Progress bar ───────────────────────────────────────────────────────
        prog_frame = tk.Frame(self, bg=BG_DARK)
        prog_frame.grid(row=3, column=0, sticky="ew", padx=24, pady=(10, 0))
        prog_frame.grid_columnconfigure(0, weight=1)

        self.progress = ttk.Progressbar(
            prog_frame,
            mode="indeterminate",
            bootstyle="success-striped",
            length=400,
        )
        self.progress.grid(row=0, column=0, sticky="ew")

        self.progress_label = tk.Label(
            prog_frame,
            text="",
            font=("Segoe UI", 9),
            fg=TEXT_MUTED,
            bg=BG_DARK,
        )
        self.progress_label.grid(row=1, column=0, pady=(4, 0))

        # ── Log area ───────────────────────────────────────────────────────────
        log_frame = tk.Frame(self, bg=BG_DARK)
        log_frame.grid(row=4, column=0, sticky="nsew", padx=24, pady=(10, 0))
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        tk.Label(
            log_frame,
            text="Activity Log",
            font=("Segoe UI", 10, "bold"),
            fg=TEXT_MUTED,
            bg=BG_DARK,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=("Consolas", 9),
            relief="flat",
            bd=0,
            insertbackground=TEXT_PRIMARY,
            state="disabled",
            wrap="word",
            height=12,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )
        self.log_text.grid(row=1, column=0, sticky="nsew")

        # Tag colours for log messages
        self.log_text.tag_config("success", foreground=ACCENT_GREEN)
        self.log_text.tag_config("error", foreground="#f85149")
        self.log_text.tag_config("info", foreground=TEXT_PRIMARY)
        self.log_text.tag_config("muted", foreground=TEXT_MUTED)
        self.log_text.tag_config("url", foreground="#58a6ff", underline=True)

        # ── Clear + footer ─────────────────────────────────────────────────────
        footer = tk.Frame(self, bg=BG_DARK)
        footer.grid(row=5, column=0, sticky="ew", padx=24, pady=(6, 12))

        ttk.Button(
            footer,
            text="Clear Log",
            style="secondary.Outline.TButton",
            command=self._clear_log,
            width=12,
        ).pack(side="left")

        tk.Label(
            footer,
            text=f"{APP_NAME}  •  {APP_VERSION}  •  Powered by yt-dlp & YouTube Data API v3",
            font=("Segoe UI", 8),
            fg=TEXT_MUTED,
            bg=BG_DARK,
        ).pack(side="right")

    # ── Auth Logic ─────────────────────────────────────────────────────────────

    def _check_auth_status(self):
        """Update auth label based on .env credentials and saved token."""
        if not credentials_configured():
            self.auth_status_label.config(
                text="⚠️  Credentials not set in .env",
                fg=ACCENT_YELLOW,
            )
            self.creds_hint.config(
                text=(
                    f"Open your .env file and fill in GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:\n"
                    f"  {ENV_FILE}"
                )
            )
            return

        # .env is configured — hide the hint
        self.creds_hint.config(text="")

        if yt.is_authenticated():
            self.auth_status_label.config(
                text="🟢  Connected to YouTube",
                fg=ACCENT_GREEN,
            )
            self.auth_btn.config(text="Re-connect", style="secondary.Outline.TButton")
        else:
            self.auth_status_label.config(
                text="⚪  Not connected — click to authorise",
                fg=TEXT_MUTED,
            )

    def _on_auth_click(self):
        """Start OAuth flow in a background thread."""
        if not credentials_configured():
            self._log_line(
                f"❌  Credentials not configured!\n"
                f"   Open your .env file and fill in:\n"
                f"     GOOGLE_CLIENT_ID=...",
                tag="error",
            )
            return

        self.auth_btn.config(state="disabled")
        self._log_line("🌐 Opening browser for YouTube authentication…", tag="info")

        def _do_auth():
            try:
                self._youtube_service = yt.get_authenticated_service(log=self._log_line)
                self.after(0, lambda: self.auth_status_label.config(
                    text="🟢  Connected to YouTube", fg=ACCENT_GREEN
                ))
                self.after(0, lambda: self.auth_btn.config(
                    text="Re-connect", style="secondary.Outline.TButton", state="normal"
                ))
            except Exception as exc:
                self._log_line(f"❌ Auth failed: {exc}", tag="error")
                self.after(0, lambda: self.auth_btn.config(state="normal"))

        threading.Thread(target=_do_auth, daemon=True).start()

    # ── Upload Logic ───────────────────────────────────────────────────────────

    def _on_upload_click(self):
        """Validate inputs then kick off the download+upload pipeline."""
        if self._is_running:
            return

        url = self.url_var.get().strip()
        if not url:
            self._log_line("⚠️  Please paste an Instagram URL first.", tag="error")
            return

        if not url.startswith("http"):
            self._log_line("⚠️  That doesn't look like a valid URL.", tag="error")
            return

        if not credentials_configured():
            self._log_line(
                "❌  .env credentials not configured. Cannot connect to YouTube.", tag="error"
            )
            return

        self._start_pipeline(url)

    def _start_pipeline(self, url: str):
        """Run the full download → upload pipeline in a background thread."""
        self._is_running = True
        self.upload_btn.config(state="disabled")
        self.progress.start(12)
        self._log_line(f"\n{'─'*55}", tag="muted")
        self._log_line(f"🔗 URL: {url}", tag="muted")
        self._log_line(f"{'─'*55}", tag="muted")

        def _pipeline():
            video_path = None
            try:
                # ── Step 1: Download Instagram video ─────────────────────────
                self._set_progress_label("Downloading Instagram video…")
                video_path, caption = insta.download_instagram_video(
                    url, progress_callback=self._log_line
                )

                # ── Step 2: Authenticate YouTube ──────────────────────────────
                self._set_progress_label("Connecting to YouTube…")
                if self._youtube_service is None:
                    self._log_line("🔑 Authenticating YouTube…", tag="info")
                    self._youtube_service = yt.get_authenticated_service(
                        log=self._log_line
                    )

                # ── Step 3: Upload ─────────────────────────────────────────────
                self._set_progress_label("Uploading to YouTube…")
                video_url = yt.upload_video(
                    self._youtube_service,
                    video_path,
                    caption,
                    log=self._log_line,
                )

                # ── Done ───────────────────────────────────────────────────────
                self._log_line(f"\n✅  Successfully uploaded!", tag="success")
                self._log_line(f"🔗  {video_url}", tag="url")
                self._log_line(
                    f"   (click the link or search your YouTube Studio)", tag="muted"
                )
                self._set_progress_label("✅  Done!")

                # Make URL clickable
                self.after(0, lambda u=video_url: self._make_url_clickable(u))

            except insta.InstagramDownloadError as exc:
                self._log_line(f"\n❌  Instagram error:\n   {exc}", tag="error")
                self._set_progress_label("Failed — see log above")
            except yt.YouTubeAuthError as exc:
                self._log_line(f"\n❌  YouTube auth error:\n   {exc}", tag="error")
                self._set_progress_label("Auth failed — see log above")
            except yt.YouTubeUploadError as exc:
                self._log_line(f"\n❌  Upload error:\n   {exc}", tag="error")
                self._set_progress_label("Upload failed — see log above")
            except Exception as exc:
                self._log_line(f"\n❌  Unexpected error:\n   {exc}", tag="error")
                self._set_progress_label("Error — see log above")
            finally:
                self._is_running = False
                self.after(0, lambda: self.progress.stop())
                self.after(0, lambda: self.upload_btn.config(state="normal"))

        threading.Thread(target=_pipeline, daemon=True).start()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _log_line(self, msg: str, tag: str = "info"):
        """Append a line to the scrollable log (thread-safe via `after`)."""
        def _append():
            self.log_text.config(state="normal")
            self.log_text.insert("end", msg + "\n", tag)
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.after(0, _append)

    def _set_progress_label(self, msg: str):
        self.after(0, lambda: self.progress_label.config(text=msg))

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        self.progress_label.config(text="")

    def _make_url_clickable(self, url: str):
        """Find the URL text in the log and bind a click handler to it."""
        # Search for the URL text and add a click binding via a unique tag
        start = self.log_text.search(url, "1.0", "end")
        if start:
            end = f"{start}+{len(url)}c"
            tag_name = f"link_{url}"
            self.log_text.tag_add(tag_name, start, end)
            self.log_text.tag_config(tag_name, foreground="#58a6ff", underline=True)
            self.log_text.tag_bind(
                tag_name,
                "<Button-1>",
                lambda e, u=url: webbrowser.open(u),
            )
            self.log_text.tag_bind(
                tag_name,
                "<Enter>",
                lambda e: self.log_text.config(cursor="hand2"),
            )
            self.log_text.tag_bind(
                tag_name,
                "<Leave>",
                lambda e: self.log_text.config(cursor=""),
            )
