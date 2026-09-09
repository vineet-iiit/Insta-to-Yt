FROM python:3.11-slim

# Install ffmpeg (required by yt-dlp for merging video+audio)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

# Create token/temp dirs
RUN mkdir -p tokens /tmp/insta_yt_bot

EXPOSE 5000

CMD ["python", "web_server.py"]
