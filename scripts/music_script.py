import os
import json
import re
import requests
from mutagen import File as MutagenFile
from PIL import Image
from io import BytesIO
import time

from config_loader import MUSIC_FOLDER, OUTPUT_DIR, COVERS_JSON, COVER_FOLDER, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, MUSIC_BRAINZ_USER_AGENT

# -------------------------
# CONFIG
# -------------------------

OUTPUT_FOLDER = OUTPUT_DIR
JSON_PATH     = COVERS_JSON

CLIENT_ID = SPOTIFY_CLIENT_ID
CLIENT_SECRET = SPOTIFY_CLIENT_SECRET

os.makedirs(COVER_FOLDER, exist_ok=True)
Image.MAX_IMAGE_PIXELS = None

# -------------------------
# Helpers
# -------------------------

def clean_slug(text):
    return re.sub(r'[^a-zA-Z0-9]', '', text)

def clean_artist(artist):
    if not artist:
        return artist
    # only remove feat, keep &
    artist = re.split(r'feat\.?|featuring', artist, flags=re.IGNORECASE)[0]
    return artist.strip()

def normalize_for_search(text):
    if not text:
        return text

    replacements = {
        "’": "'",
        "“": '"',
        "”": '"',
        "…": "...",
        "–": "-",
        "—": "-"
    }

    for k, v in replacements.items():
        text = text.replace(k, v)

    return text

def load_existing():
    if not os.path.exists(JSON_PATH):
        return []
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data):
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_audio_files(folder):
    exts = (".mp3", ".flac", ".m4a", ".opus", ".wav")
    return [f for f in os.listdir(folder) if f.lower().endswith(exts)]

def read_metadata(file_path):
    try:
        audio = MutagenFile(file_path, easy=True)
        if not audio:
            return None
        return {
            "title": audio.get("title", [None])[0],
            "artist": audio.get("albumartist", audio.get("artist", [None]))[0],
            "album": audio.get("album", [None])[0],
            "tracknumber": audio.get("tracknumber", ["0"])[0]
        }
    except:
        return None

def sort_tracks(tracks):
    def track_key(t):
        try:
            return int(t.get("tracknumber", "0").split("/")[0])
        except:
            return 0
    return sorted(tracks, key=track_key)

# -------------------------
# MusicBrainz
# -------------------------

def search_musicbrainz(artist, album):
    url = "https://musicbrainz.org/ws/2/release/"
    headers = {
        "User-Agent": MUSIC_BRAINZ_USER_AGENT
    }

    queries = [
        f'artist:"{artist}" AND release:"{album}"',
        f'{artist} {album}',
        album
    ]

    for query in queries:
        try:
            res = requests.get(url, params={
                "query": query,
                "fmt": "json",
                "limit": 1
            }, headers=headers, timeout=10)

            time.sleep(1.1)

            data = res.json()
            if data.get("releases"):
                return data["releases"][0]["id"]
        except:
            pass

    return None


def download_cover_musicbrainz(release_id, output_path):
    base_url = f"https://coverartarchive.org/release/{release_id}"

    urls = [
        f"{base_url}/front",
        f"{base_url}/0"
    ]

    for url in urls:
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                img = Image.open(BytesIO(res.content)).convert("RGB")
                img.save(output_path, "WEBP", quality=80, method=6)
                return True
        except:
            pass

    return False

# -------------------------
# Spotify
# -------------------------

def get_spotify_token():
    url = "https://accounts.spotify.com/api/token"
    res = requests.post(url, data={
        "grant_type": "client_credentials"
    }, auth=(CLIENT_ID, CLIENT_SECRET))

    return res.json().get("access_token")


def search_spotify_cover(artist, album, token):
    url = "https://api.spotify.com/v1/search"
    headers = {
        "Authorization": f"Bearer {token}"
    }

    query = f"album:{album} artist:{artist}"

    try:
        res = requests.get(url, headers=headers, params={
            "q": query,
            "type": "album",
            "limit": 1
        })

        data = res.json()
        items = data.get("albums", {}).get("items", [])

        if items:
            images = items[0].get("images", [])
            if images:
                return images[0]["url"]
    except:
        pass

    return None


def download_image_to_webp(url, output_path):
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            img = Image.open(BytesIO(res.content)).convert("RGB")
            img.save(output_path, "WEBP", quality=80, method=6)
            return True
    except:
        pass
    return False

# -------------------------
# Main
# -------------------------

existing_data = load_existing()
existing_lookup = {(a["artist"], a["album"]) for a in existing_data}

new_entries = []
spotify_token = None

for artist_folder in os.listdir(MUSIC_FOLDER):
    artist_path = os.path.join(MUSIC_FOLDER, artist_folder)
    if not os.path.isdir(artist_path):
        continue

    for album_folder in os.listdir(artist_path):
        album_path = os.path.join(artist_path, album_folder)
        if not os.path.isdir(album_path):
            continue

        audio_files = get_audio_files(album_path)
        if not audio_files:
            continue

        # metadata
        meta = None
        for file in audio_files:
            meta = read_metadata(os.path.join(album_path, file))
            if meta and meta["artist"] and meta["album"]:
                break

        if not meta:
            print(f"Skipping (no metadata): {album_folder}")
            continue

        artist = clean_artist(meta["artist"])
        album = meta["album"]

        if (artist, album) in existing_lookup:
            print(f"Skipping (exists): {artist} - {album}")
            continue

        print(f"Processing: {artist} - {album}")

        # tracks
        tracks_meta = []
        for file in audio_files:
            data = read_metadata(os.path.join(album_path, file))
            if data and data["title"]:
                tracks_meta.append(data)

        tracks_meta = sort_tracks(tracks_meta)
        tracks = [t["title"] for t in tracks_meta]

        search_artist = normalize_for_search(artist)
        search_album = normalize_for_search(album)

        slug = clean_slug(f"{artist}{album}")
        cover_filename = f"{slug}.webp"
        cover_path = os.path.join(COVER_FOLDER, cover_filename)

        cover_relative = None

        if os.path.exists(cover_path):
            cover_relative = f"covers/{cover_filename}"
        else:
            cover_found = False

            # --- MusicBrainz ---
            release_id = search_musicbrainz(search_artist, search_album)
            if release_id:
                cover_found = download_cover_musicbrainz(release_id, cover_path)

            # --- Spotify fallback ---
            if not cover_found:
                print(f"Trying Spotify: {artist} - {album}")

                if not spotify_token:
                    spotify_token = get_spotify_token()

                image_url = search_spotify_cover(artist, album, spotify_token)
                if image_url:
                    cover_found = download_image_to_webp(image_url, cover_path)

            if cover_found:
                cover_relative = f"covers/{cover_filename}"
            else:
                print(f"No cover found: {artist} - {album}")

        new_entries.append({
            "artist": artist,
            "album": album,
            "cover": cover_relative,
            "tracks": tracks
        })

# save
final_data = existing_data + new_entries
save_json(final_data)

print(f"\nDone! Added {len(new_entries)} new albums.")