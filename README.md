# 📸 Insta → ▶ YouTube Bot  v1.2

Automatically download a public Instagram video and upload it to your YouTube channel — with the original caption as the video's title and description.

---

## 🚀 Quick Start

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up Google OAuth credentials (one-time setup)

This app uses the official **YouTube Data API v3** to upload videos to your channel. You need a Google Cloud project with OAuth credentials:

| Step | Action |
|------|--------|
| 1 | Go to [console.cloud.google.com](https://console.cloud.google.com/) |
| 2 | Create a new project (e.g. "Insta YT Bot") |
| 3 | Go to **APIs & Services → Library** |
| 4 | Search for **YouTube Data API v3** → Click **Enable** |
| 5 | Go to **APIs & Services → Credentials** |
| 6 | Click **Create Credentials → OAuth 2.0 Client IDs** |
| 7 | Choose **Desktop app** → Give it any name → Click **Create** |
| 8 | Copy your **Client ID** and **Client Secret** |

### 3. Add credentials to `.env`

Open the `.env` file in the project folder and fill in your credentials:

```env
GOOGLE_CLIENT_ID=123456789-abc.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your_secret_here
```

> **OAuth Consent Screen**: If prompted, set it to "External" and add your Google account as a Test User.
> Your `.env` file is listed in `.gitignore` and will **never** be committed to version control.

### 3. Run the app

```bash
python main.py
```

---

## 🖥️ Using the App

1. **Click "Connect YouTube"** — a browser tab opens for Google sign-in. Sign in and allow the permissions. This only happens once (token is saved automatically).

2. **Paste an Instagram URL** — any public Instagram post or Reel URL, e.g.:
   ```
   https://www.instagram.com/reel/ABC123xyz/
   https://www.instagram.com/p/ABC123xyz/
   ```

3. **Click "⬆ Upload to YouTube"** — the app will:
   - Download the video from Instagram
   - Use the post caption as the YouTube title + description
   - Upload the video publicly to your YouTube channel
   - Show a clickable link to the uploaded video

---

## 📁 Project Structure

```
V1.2 insta yt bot/
├── main.py              ← Run this
├── gui.py               ← GUI window
├── instagram.py         ← Instagram download logic
├── youtube.py           ← YouTube upload logic
├── config.py            ← Paths & constants
├── requirements.txt     ← Python dependencies
├── credentials/
│   └── client_secret.json   ← ⬅ Place your Google credentials here
└── tokens/
    └── token.json           ← Auto-generated after first login
```

---

## ⚠️ Important Notes

| Topic | Detail |
|-------|--------|
| **Public posts only** | Works on public Instagram posts/Reels. Private posts require login (not supported). |
| **YouTube title limit** | YouTube titles max out at 100 characters. Long captions are automatically truncated. |
| **API quota** | YouTube API allows ~6 uploads/day on the free tier (10,000 units/day). Resets daily. |
| **ffmpeg** | `yt-dlp` may need [ffmpeg](https://ffmpeg.org/download.html) installed for best video quality. Add it to your system PATH. |

---

## 🔧 Troubleshooting

**"client_secret.json not found"**
→ Complete Step 2 of the setup above.

**"yt-dlp failed to download"**
→ Make sure the Instagram post is **public**. Try updating yt-dlp: `pip install -U yt-dlp`

**"YouTube API error 403"**
→ You may have hit the daily quota. Wait 24 hours and try again.

**"Token refresh failed"**
→ Delete `tokens/token.json` and re-connect your YouTube account.
