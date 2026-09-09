"""
main.py — Entry point for the Instagram → YouTube Bot.
Run this file with: python main.py
"""

import sys
import tkinter as tk
from tkinter import messagebox


def check_dependencies() -> bool:
    """Verify all required third-party packages are installed."""
    missing = []

    packages = {
        "ttkbootstrap": "ttkbootstrap",
        "yt_dlp": "yt-dlp",
        "googleapiclient": "google-api-python-client",
        "google.auth": "google-auth",
        "google_auth_oauthlib": "google-auth-oauthlib",
    }

    for module, pip_name in packages.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(pip_name)

    if missing:
        # Show a basic tkinter error before the full GUI loads
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Missing Dependencies",
            "The following packages are not installed:\n\n"
            + "\n".join(f"  • {p}" for p in missing)
            + "\n\nRun this command to install them:\n\n"
            + "  pip install -r requirements.txt",
        )
        root.destroy()
        return False

    return True


def main():
    if not check_dependencies():
        sys.exit(1)

    # Import GUI only after confirming dependencies are present
    from gui import App

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
