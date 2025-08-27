import os
import re
import json
import time
from urllib.parse import urlparse
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from yt_dlp import YoutubeDL

SONGS_DIR = "songs"
LOG_FILE = os.path.join(SONGS_DIR, "downloaded_songs.txt")
FFMPEG_BIN = r"C:\ffmpeg\bin"

def extract_playlist_id(url_or_id: str) -> str:
    """Accepts a full Spotify playlist URL or a raw id and returns the playlist id."""
    if re.fullmatch(r"[A-Za-z0-9]+", url_or_id):
        return url_or_id
    try:
        path = urlparse(url_or_id).path
        # /playlist/<id>
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "playlist":
            return parts[1]
    except Exception:
        pass
    raise ValueError("Could not extract playlist id from PLAYLIST_URL")

def load_downloaded_songs():
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def log_downloaded_song(song_name):
    os.makedirs(SONGS_DIR, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(song_name + "\n")

def safe_filename(name: str) -> str:
    return "".join(c for c in name if c not in r'\/:*?"<>|').strip()

def download_song(search_query: str, ffmpeg_bin: str, downloaded_songs: set):
    os.makedirs(SONGS_DIR, exist_ok=True)
    if search_query in downloaded_songs:
        print(f"⚠️ Skipped (already logged): {search_query}")
        return

    mp3_path = os.path.join(SONGS_DIR, f"{safe_filename(search_query)}.mp3")

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'outtmpl': mp3_path.replace(".mp3", ".%(ext)s"),
        'quiet': True,
        'ffmpeg_location': ffmpeg_bin,  # remove if ffmpeg is already in PATH
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    with YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([f"ytsearch:{f'{search_query} official audio'}"])
            print(f"✅ Downloaded: {search_query}")
        except Exception as e:
            print(f"❌ Failed to download: {search_query} - {e}")
            return

    # Log it so we don't re-download the same song
    log_downloaded_song(search_query)

def login_and_open_private_playlist_get_tracks(email: str, password: str, playlist_url: str) -> list[str]:
    """
    Logs into Spotify with Selenium, opens the playlist embed page using the authenticated session,
    then extracts track list from __NEXT_DATA__ JSON.
    """
    playlist_id = extract_playlist_id(playlist_url)

    chrome_opts = ChromeOptions()
    # chrome_opts.add_argument("--headless=new")  # uncomment to run without a visible window
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--window-size=1280,900")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_opts)
    wait = WebDriverWait(driver, 20)

    try:
        # 1) Go to login
        driver.get("https://accounts.spotify.com/en/login")

        # Handle possible flows
        try:
            email_input = wait.until(EC.presence_of_element_located((By.ID, "login-username")))
            email_input.clear()
            email_input.send_keys(email)
        except Exception:
            pass

        try:
            cont = wait.until(EC.element_to_be_clickable((By.ID, "login-button")))
            cont.click()
        except Exception:
            pass

        try:
            pw_toggle = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Log in with a password')]"))
            )
            pw_toggle.click()
        except Exception:
            pass

        try:
            email_input = wait.until(EC.presence_of_element_located((By.ID, "login-username")))
            email_input.clear()
            email_input.send_keys(email)
        except Exception:
            pass

        password_input = wait.until(EC.presence_of_element_located((By.ID, "login-password")))
        password_input.clear()
        password_input.send_keys(password)

        try:
            login_btn = wait.until(EC.element_to_be_clickable((By.ID, "login-button")))
            login_btn.click()
        except Exception:
            password_input.submit()

        time.sleep(5)  

        # 2) Open the embed page authenticated
        embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
        driver.get(embed_url)
        time.sleep(7)

        # Wait for JSON
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "script#_next, script#__NEXT_DATA__")))
        time.sleep(1)

        # Read __NEXT_DATA__
        next_data_json = driver.execute_script("""
            const el = document.querySelector('script#__NEXT_DATA__');
            return el ? el.textContent : null;
        """)

        if not next_data_json:
            raise RuntimeError("Could not locate __NEXT_DATA__ on embed page (are you logged in / is the playlist accessible?).")

        data = json.loads(next_data_json)

        # Extract track list (known path, with fallback)
        track_list_raw = None
        try:
            track_list_raw = data['props']['pageProps']['state']['data']['entity']['trackList']
        except KeyError:
            def dfs(obj):
                if isinstance(obj, dict):
                    if all(k in obj for k in ("title", "subtitle")):
                        return [obj]
                    for v in obj.values():
                        r = dfs(v)
                        if r:
                            return r
                elif isinstance(obj, list):
                    if obj and isinstance(obj[0], dict) and "title" in obj[0] and "subtitle" in obj[0]:
                        return obj
                    for v in obj:
                        r = dfs(v)
                        if r:
                            return r
                return None
            track_list_raw = dfs(data)

        if not track_list_raw:
            raise RuntimeError("Track list not found in embed JSON (structure may have changed).")

        tracks = []
        for t in track_list_raw:
            title = t.get("title")
            subtitle = t.get("subtitle")
            if title and subtitle:
                tracks.append(f"{subtitle} - {title}")

        return tracks

    finally:
        driver.quit()

if __name__ == "__main__":
    load_dotenv()
    EMAIL = os.getenv("SPOTIFY_EMAIL")
    PASSWORD = os.getenv("SPOTIFY_PASSWORD")
    PLAYLIST_URL = os.getenv("PLAYLIST_URL")

    if not EMAIL or not PASSWORD or not PLAYLIST_URL:
        raise SystemExit("Please set SPOTIFY_EMAIL, SPOTIFY_PASSWORD, PLAYLIST_URL in your .env")

    # 1) Login with Selenium and extract tracks from the private playlist
    tracks = login_and_open_private_playlist_get_tracks(EMAIL, PASSWORD, PLAYLIST_URL)

    # 2) Prepare local state
    downloaded_songs = load_downloaded_songs()

    print(f"🎵 Found {len(tracks)} songs")
    for t in tracks:
        print("•", t)

    # 3) Download (no speed-up) + log
    for t in tracks:
        download_song(t, FFMPEG_BIN, downloaded_songs)
