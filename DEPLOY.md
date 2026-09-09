# 🚀 Deploy to Railway — Step by Step

This guide gets your Instagram → YouTube Bot running 24/7 in the cloud so you can use it **from your phone anywhere, no PC required**.

---

## Prerequisites

- [ ] [GitHub account](https://github.com) (free)
- [ ] [Railway account](https://railway.app) (free, sign in with GitHub)
- [ ] Google Cloud credentials (`GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET`)

---

## Step 1 — Push Code to GitHub

### If you don't have git:
Download from [git-scm.com](https://git-scm.com) and install.

### In PowerShell, from your project folder:
```powershell
cd "C:\Users\vc\Desktop\V1.2 insta yt bot"
git init
git add .
git commit -m "Initial commit"
```

### Create a GitHub repo:
1. Go to [github.com/new](https://github.com/new)
2. Name it `insta-yt-bot` (private recommended)
3. **Don't** add README or .gitignore (we have our own)
4. Click **Create repository**

### Push to GitHub:
```powershell
git remote add origin https://github.com/YOUR_USERNAME/insta-yt-bot.git
git branch -M main
git push -u origin main
```

---

## Step 2 — Deploy on Railway

1. Go to [railway.app](https://railway.app) → **New Project**
2. Click **Deploy from GitHub repo**
3. Select your `insta-yt-bot` repository
4. Railway auto-detects the `Dockerfile` and starts building

---

## Step 3 — Add a Public Domain

1. In Railway, go to your service → **Settings** → **Networking**
2. Click **Generate Domain** — you'll get a URL like:
   ```
   https://insta-yt-bot-production.up.railway.app
   ```
3. **Copy this URL** — you need it for the next steps

---

## Step 4 — Add Environment Variables in Railway

Go to your service → **Variables** → add all of these:

| Variable | Value |
|----------|-------|
| `GOOGLE_CLIENT_ID` | Your Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Your Google OAuth client secret |
| `APP_URL` | Your Railway URL (e.g. `https://insta-yt-bot-xxx.railway.app`) |
| `SECRET_KEY` | Run `python -c "import secrets; print(secrets.token_hex(32))"` and paste the output |
| `APP_ENV` | `production` |
| `YOUTUBE_PRIVACY` | `public` |

---

## Step 5 — Update Google Cloud Console

Your OAuth app in Google Cloud needs to allow the Railway callback URL.

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. APIs & Services → **Credentials** → click your OAuth 2.0 Client ID
3. Under **Authorized redirect URIs**, click **Add URI**
4. Add: `https://your-app.railway.app/oauth/callback`
   *(replace with your actual Railway URL)*
5. Also add: `http://localhost:5000/oauth/callback` *(for local testing)*
6. Click **Save**

> ⚠️ **Important**: Change the OAuth client type to **Web application** if it's currently set to "Desktop app". Web application supports redirect URIs.

---

## Step 6 — Connect Your YouTube Account

1. Open your Railway app URL in your phone's browser
2. Tap **"Connect YouTube"** — a Google sign-in popup opens
3. Sign in and click **Allow**
4. After success, you'll see a **token JSON** — copy it!
5. Go to Railway → Variables → add `GOOGLE_TOKEN_JSON` = (paste the token)
6. Railway auto-redeploys with the token saved permanently

---

## Step 7 — Install as App on Phone

**Android:**
- Open your Railway URL in Chrome
- Tap the **Install** banner at the bottom
- It adds to your home screen like a real app!

**iPhone:**
- Open in Safari → tap Share button (□↑) → **"Add to Home Screen"**

---

## 🎉 Done!

Now you can:
- Open the app from your phone home screen
- Paste any Instagram link
- Tap **Upload to YouTube**
- Done — works from anywhere, 24/7!

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Build fails | Check Railway build logs for errors |
| OAuth error "redirect_uri_mismatch" | Make sure Railway URL is in Google Cloud Console redirect URIs |
| Token expires | Re-connect YouTube and update `GOOGLE_TOKEN_JSON` env var |
| Download fails | Some Instagram posts may be region-restricted; try another post |
| yt-dlp fails | Update yt-dlp: push a commit, Railway auto-redeploys |
