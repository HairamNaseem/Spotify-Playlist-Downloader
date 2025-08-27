# Spotify-Playlist-Downloader

# Spotify Private Playlist Downloader

This project lets you **download songs from a private Spotify playlist** by:
1. Logging into Spotify with Selenium.
2. Extracting the playlist tracks via the embedded `__NEXT_DATA__` JSON.
3. Downloading the corresponding songs from YouTube (best audio) using [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) + FFmpeg.

Songs are saved as `.mp3` files in the `songs/` folder. A log file prevents re-downloading the same tracks.

---

## ⚙️ Features
- Extracts tracks from **private playlists** (requires your Spotify login).
- Downloads songs as high-quality MP3s using YouTube.
- Keeps a `downloaded_songs.txt` log to skip duplicates.
- Auto-manages ChromeDriver with `webdriver-manager`.

---

## 🛠️ Requirements
- Python 3.9+
- Google Chrome installed
- [FFmpeg](https://ffmpeg.org/download.html) (binary path set in script or added to system `PATH`)

   git clone https://github.com/yourusername/spotify-downloader.git
   cd spotify-downloader
