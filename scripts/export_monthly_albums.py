"""
export_monthly_albums.py
------------------------
Parses master.log and writes the top 5 albums
of the current month to JSON for your website sidebar.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

from config_loader import LOG_PATH, OUTPUT_JSON, COVERS_JSON

# ---------------- CONFIG ----------------

TOP_N = 5

EXCLUDED_ARTISTS = {"audiobooks"}
EXCLUDED_KEYWORDS = {"audiobook", "chapter", "part"}

ARTIST_FIXES = {
    "04-the-coolest": "Lupe Fiasco",
    "the-coolest": "Lupe Fiasco",
    "MF Presents Lupe Fiasco 13 Mixtape Pack": "Lupe Fiasco",
    "Iamdoechii": "Doechii",
}
ALBUM_FIXES = {}


# ---------------- HELPERS ----------------
def normalize(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def clean_name(name):
    name = name.replace("_", " ")
    name = re.sub(r"^\d+[-. ]*", "", name)
    return name.strip()

def apply_fixes(artist, album):
    return ARTIST_FIXES.get(artist, artist), ALBUM_FIXES.get(album, album)

def is_excluded(artist, album, track):
    text = f"{artist} {album} {track}".lower()
    if artist.lower() in EXCLUDED_ARTISTS:
        return True
    return any(k in text for k in EXCLUDED_KEYWORDS)


# ---------------- COVER MAP ----------------
def load_cover_map():
    if not os.path.exists(COVERS_JSON):
        return {}

    with open(COVERS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        (normalize(item.get("artist", "")), normalize(item.get("album", ""))): item.get("cover", "")
        for item in data
    }

def get_cover(cover_map, artist, album):
    na, nal = normalize(artist), normalize(album)

    if (na, nal) in cover_map:
        return cover_map[(na, nal)]

    for (a, al), path in cover_map.items():
        if a == na and (nal in al or al in nal):
            return path

    matches = [p for (a, _), p in cover_map.items() if a == na]
    return matches[0] if len(matches) == 1 else ""


# ---------------- PARSE ----------------
def parse_current_month(log_path):
    now = datetime.now()
    rows = []

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            try:
                ts, played_ms, total_ms, filepath = line.split(":", 3)
                dt = datetime.fromtimestamp(int(ts))

                # filter current month
                if dt.year != now.year or dt.month != now.month:
                    continue

                played_ms = int(played_ms)
                total_ms = int(total_ms)

                if total_ms == 0:
                    continue

                completion = played_ms / total_ms

                # quality filter
                if played_ms <= 30000 or completion <= 0.4:
                    continue

                p = Path(filepath)
                parts = p.parts

                artist = clean_name(parts[-3] if len(parts) >= 3 else "Unknown")
                album  = clean_name(parts[-2] if len(parts) >= 2 else "Unknown")
                track  = clean_name(p.stem)

                artist, album = apply_fixes(artist, album)

                if is_excluded(artist, album, track):
                    continue

                rows.append({
                    "artist": artist,
                    "album": album,
                    "played_min": played_ms / 60000,
                })

            except Exception:
                continue

    return rows


# ---------------- RANK ----------------
def rank_albums(rows, cover_map, top_n=5):
    tally = {}

    for r in rows:
        key = (r["artist"], r["album"])
        if key not in tally:
            tally[key] = {"plays": 0, "minutes": 0}

        tally[key]["plays"] += 1
        tally[key]["minutes"] += r["played_min"]

    scored = []
    for (artist, album), v in tally.items():
        scored.append({
            "artist": artist,
            "album": album,
            "plays": v["plays"],
            "minutes": round(v["minutes"], 1),
            "score": v["plays"] * 0.7 + v["minutes"] * 0.3,
            "cover": get_cover(cover_map, artist, album),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]


# ---------------- MAIN ----------------
def main():
    now = datetime.now()
    print(f"[monthly albums] {now.strftime('%B %Y')}")

    if not os.path.exists(LOG_PATH):
        print("❌ master.log not found")
        return

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

    cover_map = load_cover_map()
    rows = parse_current_month(LOG_PATH)

    if not rows:
        print("⚠️ No plays this month")
        return

    albums = rank_albums(rows, cover_map, TOP_N)

    output = {
        "month": now.strftime("%B %Y"),
        "updated": now.isoformat(),
        "albums": albums
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"✅ Wrote {len(albums)} albums → {OUTPUT_JSON}")


if __name__ == "__main__":
    main()