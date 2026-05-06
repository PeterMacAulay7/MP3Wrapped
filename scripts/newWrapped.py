import pandas as pd
from pathlib import Path
from datetime import datetime
import re
import os
import json
from collections import defaultdict

from config_loader import LOG_PATH, OUTPUT_HTML, COVERS_JSON

# ---------------- CONFIG ----------------
EXCLUDED_ARTISTS = {"audiobooks"}
EXCLUDED_KEYWORDS = {"audiobook", "chapter", "part"}

ARTIST_FIXES = {
    "04-the-coolest": "Lupe Fiasco",
    "the-coolest": "Lupe Fiasco",
    "MF Presents Lupe Fiasco 13 Mixtape Pack": "Lupe Fiasco",
    "Iamdoechii": "Doechii"
}

ALBUM_FIXES = {}


def normalize(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# ---------------- LOAD COVER MAP ----------------
def load_cover_map():
    if not os.path.exists(COVERS_JSON):
        return {}
    with open(COVERS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    cover_map = {}
    for item in data:
      if item.get("album") is None or item.get("artist") is None:
        print("Bad item:", item)
      artist = normalize(item.get("artist", ""))
      album = normalize(item.get("album", ""))
      path = item.get("cover", "")
      cover_map[(artist, album)] = path
    return cover_map


COVER_MAP = load_cover_map()


# ---------------- CLEANING ----------------
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


# ---------------- COVER LOOKUP ----------------
def get_cover_path(artist, album):
    norm_artist = normalize(artist)
    norm_album = normalize(album)
    if (norm_artist, norm_album) in COVER_MAP:
        return COVER_MAP[(norm_artist, norm_album)]
    for (a, al), path in COVER_MAP.items():
        if a == norm_artist:
            if norm_album in al or al in norm_album:
                return path
    matches = [path for (a, _), path in COVER_MAP.items() if a == norm_artist]
    if len(matches) == 1:
        return matches[0]
    return None


# ---------------- PARSE ----------------
def parse_log(path):
    rows = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                ts, played_ms, total_ms, filepath = line.split(":", 3)
                p = Path(filepath)
                parts = p.parts
                artist = clean_name(parts[-3] if len(parts) >= 3 else "Unknown")
                album = clean_name(parts[-2] if len(parts) >= 2 else "Unknown")
                track = clean_name(p.stem)
                artist, album = apply_fixes(artist, album)
                if is_excluded(artist, album, track):
                    continue
                dt = datetime.fromtimestamp(int(ts))
                rows.append({
                    "timestamp": dt,
                    "hour": dt.hour,
                    "month": dt.strftime("%b"),
                    "month_num": dt.month,
                    "year": dt.year,
                    "played_ms": int(played_ms),
                    "total_ms": int(total_ms),
                    "completion": int(played_ms) / int(total_ms) if int(total_ms) else 0,
                    "artist": artist,
                    "album": album,
                    "track": track
                })
            except Exception:
                continue
    return pd.DataFrame(rows)


# ---------------- LOAD ----------------
df = parse_log(LOG_PATH)
df["played_minutes"] = df["played_ms"] / 60000

QUALIFIED = df[(df["played_ms"] > 30000) & (df["completion"] > 0.4)].copy()

# ---------------- CORE METRICS ----------------
total_minutes = df["played_minutes"].sum()
total_hours = total_minutes / 60
total_plays = len(QUALIFIED)
unique_artists = QUALIFIED["artist"].nunique()
unique_tracks = QUALIFIED["track"].nunique()
unique_albums = QUALIFIED.groupby(["artist", "album"]).ngroups

track_stats = (
    QUALIFIED.groupby(["artist", "track"])
    .agg(plays=("track", "count"), minutes=("played_minutes", "sum"),
         avg_completion=("completion", "mean"))
)
track_stats["score"] = track_stats["plays"] * 0.7 + track_stats["minutes"] * 0.3
track_stats = track_stats.sort_values("score", ascending=False)

artist_stats = (
    QUALIFIED.groupby("artist")
    .agg(plays=("track", "count"), minutes=("played_minutes", "sum"))
    .sort_values("minutes", ascending=False)
)

album_stats = (
    QUALIFIED.groupby(["artist", "album"])
    .agg(plays=("track", "count"), unique_tracks=("track", "nunique"),
         minutes=("played_minutes", "sum"))
)
album_stats["replay"] = album_stats["plays"] / album_stats["unique_tracks"]
album_stats = album_stats.sort_values("replay", ascending=False)

# ---------------- NEW METRICS ----------------
# Monthly trends
monthly = (
    QUALIFIED.groupby(["year", "month_num", "month"])
    .agg(plays=("track", "count"), minutes=("played_minutes", "sum"))
    .reset_index()
    .sort_values(["year", "month_num"])
)

# Time of day buckets
def time_bucket(h):
    if 5 <= h < 12:   return "Morning"
    if 12 <= h < 17:  return "Afternoon"
    if 17 <= h < 22:  return "Evening"
    return "Night"

QUALIFIED["time_of_day"] = QUALIFIED["hour"].apply(time_bucket)
time_dist = QUALIFIED.groupby("time_of_day").size()
time_icons = {"Morning": "🌅", "Afternoon": "☀️", "Evening": "🌆", "Night": "🌙"}

# Top artist share
top_artist = artist_stats.index[0] if len(artist_stats) > 0 else "N/A"
top_artist_minutes = artist_stats.iloc[0]["minutes"] if len(artist_stats) > 0 else 0
top_artist_pct = (top_artist_minutes / total_minutes * 100) if total_minutes > 0 else 0

# Most completed track (min 5 plays)
frequent_tracks = track_stats[track_stats["plays"] >= 5]
if len(frequent_tracks) > 0:
    most_completed = frequent_tracks["avg_completion"].idxmax()
    mc_artist, mc_track = most_completed
    mc_completion = frequent_tracks.loc[most_completed, "avg_completion"]
    mc_plays = int(frequent_tracks.loc[most_completed, "plays"])
else:
    mc_artist, mc_track, mc_completion, mc_plays = "N/A", "N/A", 0, 0

# Listening streak: longest consecutive days
if len(QUALIFIED) > 0:
    days_listened = sorted(QUALIFIED["timestamp"].dt.date.unique())
    max_streak, cur_streak = 1, 1
    for i in range(1, len(days_listened)):
        delta = (days_listened[i] - days_listened[i - 1]).days
        cur_streak = cur_streak + 1 if delta == 1 else 1
        max_streak = max(max_streak, cur_streak)
else:
    max_streak = 0

# Date range
if len(QUALIFIED) > 0:
    date_start = QUALIFIED["timestamp"].min().strftime("%b %d, %Y")
    date_end = QUALIFIED["timestamp"].max().strftime("%b %d, %Y")
else:
    date_start = date_end = "N/A"


# ---------------- HTML BUILDERS ----------------

def escape_html(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def monthly_chart_html():
    if len(monthly) == 0:
        return "<p>No data</p>"
    max_min = monthly["minutes"].max()
    bars = ""
    for _, row in monthly.iterrows():
        pct = (row["minutes"] / max_min * 100) if max_min > 0 else 0
        label = row["month"]
        mins = int(row["minutes"])
        bars += f"""
        <div class="bar-wrap">
          <div class="bar-label-top">{mins}m</div>
          <div class="bar-outer">
            <div class="bar-fill" style="height:{pct:.1f}%"></div>
          </div>
          <div class="bar-label">{label}</div>
        </div>"""
    return f'<div class="bar-chart">{bars}</div>'


def time_of_day_html():
    total_tod = time_dist.sum()
    order = ["Morning", "Afternoon", "Evening", "Night"]
    items = ""
    for tod in order:
        count = time_dist.get(tod, 0)
        pct = (count / total_tod * 100) if total_tod > 0 else 0
        icon = time_icons.get(tod, "")
        items += f"""
        <div class="tod-item">
          <div class="tod-header">
            <span class="tod-icon">{icon}</span>
            <span class="tod-name">{tod}</span>
            <span class="tod-pct">{pct:.0f}%</span>
          </div>
          <div class="tod-bar-outer">
            <div class="tod-bar-fill" style="width:{pct:.1f}%"></div>
          </div>
        </div>"""
    return items


def top_tracks_html(n=10):
    rows = ""
    for i, ((artist, track), row) in enumerate(track_stats.head(n).iterrows(), 1):
        plays = int(row["plays"])
        mins = row["minutes"]
        completion = row["avg_completion"]
        medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"#{i}"
        rows += f"""
        <div class="track-row">
          <span class="track-rank">{medal}</span>
          <div class="track-info">
            <div class="track-name">{escape_html(track)}</div>
            <div class="track-artist">{escape_html(artist)}</div>
          </div>
          <div class="track-meta">
            <span class="track-plays">{plays} plays</span>
            <span class="track-mins">{mins:.0f}m</span>
            <div class="completion-bar">
              <div class="completion-fill" style="width:{completion*100:.0f}%"></div>
            </div>
          </div>
        </div>"""
    return rows


def top_artists_html(n=8):
    max_min = artist_stats["minutes"].max() if len(artist_stats) > 0 else 1
    items = ""
    for i, (artist, row) in enumerate(artist_stats.head(n).iterrows(), 1):
        pct = (row["minutes"] / max_min * 100)
        cover = None
        # Try to find any album cover for this artist
        for (a, al), path in COVER_MAP.items():
            if normalize(artist) == a:
                cover = path
                break
        img = f'<img src="{cover}" class="artist-img" alt="">' if cover else f'<div class="artist-img artist-placeholder">{artist[0].upper()}</div>'
        items += f"""
        <div class="artist-card">
          {img}
          <div class="artist-card-info">
            <div class="artist-card-name">{escape_html(artist)}</div>
            <div class="artist-card-sub">{int(row["plays"])} plays · {row["minutes"]:.0f}m</div>
            <div class="artist-bar-outer">
              <div class="artist-bar-fill" style="width:{pct:.1f}%"></div>
            </div>
          </div>
        </div>"""
    return items


def album_cards_html(n=6):
    cards = ""
    for (artist, album), row in album_stats.head(n).iterrows():
        cover = get_cover_path(artist, album)
        img = f'<img src="{cover}" class="album-cover" alt="">' if cover else f'<div class="album-cover album-placeholder">{album[0].upper()}</div>'
        replay = row["replay"]
        plays = int(row["plays"])
        minutes = row["minutes"]
        cards += f"""
        <div class="album-card">
          {img}
          <div class="album-info">
            <div class="album-name">{escape_html(album)}</div>
            <div class="album-artist">{escape_html(artist)}</div>
            <div class="album-stats">
              <span>🔁 {replay:.1f}x avg</span>
              <span>▶ {plays} plays</span>
              <span>⏱ {minutes:.0f}m</span>
            </div>
          </div>
        </div>"""
    return cards


# ==================== HTML ====================
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🎧 Your Wrapped</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@400;700;900&family=DM+Sans:wght@300;400;500&display=swap');

  :root {{
    --bg: #0a0a0f;
    --surface: #13131a;
    --surface2: #1c1c27;
    --border: #2a2a3a;
    --green: #1ed760;
    --purple: #b042ff;
    --orange: #ff6b35;
    --pink: #ff3d7f;
    --blue: #3d9eff;
    --yellow: #ffd700;
    --text: #f0f0f8;
    --muted: #7a7a99;
    --radius: 16px;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'DM Sans', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    overflow-x: hidden;
  }}

  /* ---- HERO ---- */
  .hero {{
    position: relative;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 60px 20px;
    overflow: hidden;
  }}

  .hero-bg {{
    position: absolute; inset: 0; z-index: 0;
    background:
      radial-gradient(ellipse 80% 60% at 20% 30%, rgba(176,66,255,0.25) 0%, transparent 60%),
      radial-gradient(ellipse 70% 50% at 80% 70%, rgba(255,61,127,0.2) 0%, transparent 60%),
      radial-gradient(ellipse 60% 80% at 50% 10%, rgba(30,215,96,0.1) 0%, transparent 50%),
      var(--bg);
  }}

  .hero-bg::after {{
    content: '';
    position: absolute; inset: 0;
    background-image: url("data:image/svg+xml,%3Csvg width='60' height='60' xmlns='http://www.w3.org/2000/svg'%3E%3Ccircle cx='1' cy='1' r='1' fill='rgba(255,255,255,0.03)'/%3E%3C/svg%3E");
  }}

  .hero-content {{ position: relative; z-index: 1; }}

  .hero-eyebrow {{
    font-family: 'Unbounded', sans-serif;
    font-size: 0.7rem;
    letter-spacing: 0.3em;
    color: var(--green);
    text-transform: uppercase;
    margin-bottom: 16px;
    opacity: 0;
    animation: fadeUp 0.6s 0.2s forwards;
  }}

  .hero-title {{
    font-family: 'Unbounded', sans-serif;
    font-size: clamp(3rem, 10vw, 7rem);
    font-weight: 900;
    line-height: 0.95;
    background: linear-gradient(135deg, #fff 0%, var(--green) 40%, var(--purple) 80%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 24px;
    opacity: 0;
    animation: fadeUp 0.7s 0.4s forwards;
  }}

  .hero-date {{
    font-size: 1rem;
    color: var(--muted);
    margin-bottom: 50px;
    opacity: 0;
    animation: fadeUp 0.6s 0.6s forwards;
  }}

  .hero-stats {{
    display: flex;
    gap: 40px;
    flex-wrap: wrap;
    justify-content: center;
    opacity: 0;
    animation: fadeUp 0.7s 0.8s forwards;
  }}

  .hero-stat {{
    display: flex;
    flex-direction: column;
    align-items: center;
  }}

  .hero-stat-num {{
    font-family: 'Unbounded', sans-serif;
    font-size: 2.5rem;
    font-weight: 900;
    background: linear-gradient(135deg, var(--green), var(--blue));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }}

  .hero-stat-label {{
    font-size: 0.75rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 4px;
  }}

  .hero-divider {{
    width: 1px;
    height: 50px;
    background: var(--border);
    align-self: center;
  }}

  /* ---- SECTION ---- */
  .section {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 80px 24px;
  }}

  .section-label {{
    font-family: 'Unbounded', sans-serif;
    font-size: 0.65rem;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: var(--green);
    margin-bottom: 12px;
  }}

  .section-title {{
    font-family: 'Unbounded', sans-serif;
    font-size: clamp(1.8rem, 4vw, 2.8rem);
    font-weight: 900;
    margin-bottom: 40px;
    line-height: 1.1;
  }}

  /* ---- HIGHLIGHT CARDS ---- */
  .highlight-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 20px;
    margin-bottom: 80px;
  }}

  .highlight-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 28px;
    position: relative;
    overflow: hidden;
    transition: transform 0.2s, border-color 0.2s;
  }}

  .highlight-card:hover {{
    transform: translateY(-4px);
    border-color: var(--green);
  }}

  .highlight-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
  }}

  .highlight-card.green::before  {{ background: var(--green); }}
  .highlight-card.purple::before {{ background: var(--purple); }}
  .highlight-card.orange::before {{ background: var(--orange); }}
  .highlight-card.pink::before   {{ background: var(--pink); }}
  .highlight-card.blue::before   {{ background: var(--blue); }}
  .highlight-card.yellow::before {{ background: var(--yellow); }}

  .hc-emoji {{ font-size: 2rem; margin-bottom: 12px; }}
  .hc-value {{
    font-family: 'Unbounded', sans-serif;
    font-size: 1.8rem;
    font-weight: 900;
    margin-bottom: 4px;
    line-height: 1.1;
  }}
  .hc-label {{ font-size: 0.85rem; color: var(--muted); }}
  .hc-sub   {{ font-size: 0.8rem; color: var(--muted); margin-top: 8px; font-style: italic; }}

  /* ---- MONTHLY CHART ---- */
  .chart-section {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 36px;
    margin-bottom: 80px;
  }}

  .bar-chart {{
    display: flex;
    align-items: flex-end;
    gap: 12px;
    height: 180px;
    padding-top: 30px;
  }}

  .bar-wrap {{
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    height: 100%;
  }}

  .bar-label-top {{
    font-size: 0.6rem;
    color: var(--muted);
    margin-bottom: 4px;
    white-space: nowrap;
  }}

  .bar-outer {{
    flex: 1;
    width: 100%;
    background: var(--surface2);
    border-radius: 6px 6px 0 0;
    display: flex;
    align-items: flex-end;
    overflow: hidden;
  }}

  .bar-fill {{
    width: 100%;
    background: linear-gradient(180deg, var(--green), rgba(30,215,96,0.4));
    border-radius: 6px 6px 0 0;
    transition: height 1s cubic-bezier(0.34, 1.56, 0.64, 1);
    min-height: 4px;
  }}

  .bar-label {{
    font-size: 0.7rem;
    color: var(--muted);
    margin-top: 8px;
    font-family: 'Unbounded', sans-serif;
  }}

  /* ---- TIME OF DAY ---- */
  .tod-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 80px;
  }}

  .tod-item {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
  }}

  .tod-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
  }}

  .tod-icon  {{ font-size: 1.4rem; }}
  .tod-name  {{ font-family: 'Unbounded', sans-serif; font-size: 0.75rem; flex: 1; }}
  .tod-pct   {{ font-family: 'Unbounded', sans-serif; font-size: 1rem; font-weight: 700; color: var(--green); }}

  .tod-bar-outer {{
    height: 6px; background: var(--surface2); border-radius: 3px; overflow: hidden;
  }}
  .tod-bar-fill {{
    height: 100%;
    background: linear-gradient(90deg, var(--green), var(--blue));
    border-radius: 3px;
  }}

  /* ---- TOP TRACKS ---- */
  .tracks-list {{
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 80px;
  }}

  .track-row {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    transition: border-color 0.2s, transform 0.2s;
  }}

  .track-row:hover {{
    border-color: var(--green);
    transform: translateX(4px);
  }}

  .track-rank {{
    font-family: 'Unbounded', sans-serif;
    font-size: 1.1rem;
    min-width: 36px;
    text-align: center;
  }}

  .track-info {{ flex: 1; min-width: 0; }}
  .track-name   {{ font-size: 0.95rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .track-artist {{ font-size: 0.8rem; color: var(--muted); margin-top: 2px; }}

  .track-meta {{ display: flex; align-items: center; gap: 12px; flex-shrink: 0; }}
  .track-plays {{ font-size: 0.8rem; color: var(--green); font-family: 'Unbounded', sans-serif; }}
  .track-mins  {{ font-size: 0.8rem; color: var(--muted); }}

  .completion-bar {{ width: 60px; height: 4px; background: var(--surface2); border-radius: 2px; overflow: hidden; }}
  .completion-fill {{ height: 100%; background: linear-gradient(90deg, var(--green), var(--blue)); border-radius: 2px; }}

  /* ---- ARTISTS ---- */
  .artists-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 16px;
    margin-bottom: 80px;
  }}

  .artist-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
    display: flex;
    align-items: center;
    gap: 14px;
    transition: transform 0.2s, border-color 0.2s;
  }}

  .artist-card:hover {{ transform: scale(1.02); border-color: var(--purple); }}

  .artist-img {{
    width: 56px; height: 56px;
    border-radius: 50%;
    object-fit: cover;
    flex-shrink: 0;
  }}

  .artist-placeholder {{
    background: linear-gradient(135deg, var(--purple), var(--pink));
    display: flex; align-items: center; justify-content: center;
    font-family: 'Unbounded', sans-serif;
    font-size: 1.2rem; font-weight: 900;
    color: #fff;
  }}

  .artist-card-info {{ flex: 1; min-width: 0; }}
  .artist-card-name {{ font-size: 0.95rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .artist-card-sub  {{ font-size: 0.75rem; color: var(--muted); margin: 4px 0 8px; }}

  .artist-bar-outer {{ height: 4px; background: var(--surface2); border-radius: 2px; overflow: hidden; }}
  .artist-bar-fill  {{ height: 100%; background: linear-gradient(90deg, var(--purple), var(--pink)); border-radius: 2px; }}

  /* ---- ALBUMS ---- */
  .albums-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 20px;
    margin-bottom: 80px;
  }}

  .album-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    transition: transform 0.2s, border-color 0.2s;
  }}

  .album-card:hover {{ transform: translateY(-6px); border-color: var(--orange); }}

  .album-cover {{
    width: 100%;
    aspect-ratio: 1;
    object-fit: cover;
    display: block;
  }}

  .album-placeholder {{
    width: 100%; aspect-ratio: 1;
    background: linear-gradient(135deg, var(--orange), var(--pink));
    display: flex; align-items: center; justify-content: center;
    font-family: 'Unbounded', sans-serif;
    font-size: 3rem; font-weight: 900; color: #fff;
  }}

  .album-info {{ padding: 16px; }}
  .album-name   {{ font-size: 0.95rem; font-weight: 500; margin-bottom: 4px; }}
  .album-artist {{ font-size: 0.8rem; color: var(--muted); margin-bottom: 12px; }}
  .album-stats  {{ display: flex; gap: 10px; flex-wrap: wrap; }}
  .album-stats span {{
    font-size: 0.72rem;
    background: var(--surface2);
    border-radius: 20px;
    padding: 4px 10px;
    color: var(--muted);
  }}

  /* ---- FOOTER ---- */
  .footer {{
    text-align: center;
    padding: 60px 20px;
    color: var(--muted);
    font-size: 0.8rem;
    border-top: 1px solid var(--border);
  }}

  .footer-logo {{
    font-family: 'Unbounded', sans-serif;
    font-size: 1.2rem;
    font-weight: 900;
    background: linear-gradient(135deg, var(--green), var(--blue));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 12px;
  }}

  /* ---- DIVIDER ---- */
  .section-divider {{
    max-width: 1100px;
    margin: 0 auto;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border), transparent);
  }}

  @keyframes fadeUp {{
    from {{ opacity: 0; transform: translateY(30px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}

  @media (max-width: 600px) {{
    .hero-stats {{ gap: 20px; }}
    .hero-divider {{ display: none; }}
    .track-meta {{ display: none; }}
  }}
</style>
</head>
<body>

<!-- ============ HERO ============ -->
<section class="hero">
  <div class="hero-bg"></div>
  <div class="hero-content">
    <div class="hero-eyebrow">Your Listening Report</div>
    <h1 class="hero-title">Wrapped</h1>
    <div class="hero-date">{date_start} — {date_end}</div>
    <div class="hero-stats">
      <div class="hero-stat">
        <span class="hero-stat-num">{total_hours:.0f}h</span>
        <span class="hero-stat-label">Total Time</span>
      </div>
      <div class="hero-divider"></div>
      <div class="hero-stat">
        <span class="hero-stat-num">{total_plays}</span>
        <span class="hero-stat-label">Plays</span>
      </div>
      <div class="hero-divider"></div>
      <div class="hero-stat">
        <span class="hero-stat-num">{unique_artists}</span>
        <span class="hero-stat-label">Artists</span>
      </div>
      <div class="hero-divider"></div>
      <div class="hero-stat">
        <span class="hero-stat-num">{unique_albums}</span>
        <span class="hero-stat-label">Albums</span>
      </div>
      <div class="hero-divider"></div>
      <div class="hero-stat">
        <span class="hero-stat-num">{unique_tracks}</span>
        <span class="hero-stat-label">Tracks</span>
      </div>
    </div>
  </div>
</section>

<!-- ============ HIGHLIGHTS ============ -->
<div class="section">
  <div class="section-label">Your Standouts</div>
  <h2 class="section-title">By the Numbers</h2>
  <div class="highlight-grid">

    <div class="highlight-card green">
      <div class="hc-emoji">🎧</div>
      <div class="hc-value">{total_hours:.1f}h</div>
      <div class="hc-label">Total Listening Time</div>
      <div class="hc-sub">{total_minutes:.0f} minutes of music</div>
    </div>

    <div class="highlight-card purple">
      <div class="hc-emoji">👑</div>
      <div class="hc-value">{escape_html(top_artist[:20])}</div>
      <div class="hc-label">Top Artist</div>
      <div class="hc-sub">{top_artist_pct:.0f}% of your total listening</div>
    </div>

    <div class="highlight-card orange">
      <div class="hc-emoji">🔁</div>
      <div class="hc-value">{escape_html(mc_track[:20])}</div>
      <div class="hc-label">Most Completed Track</div>
      <div class="hc-sub">{mc_completion*100:.0f}% avg · {mc_plays} plays · {escape_html(mc_artist)}</div>
    </div>

    <div class="highlight-card pink">
      <div class="hc-emoji">🔥</div>
      <div class="hc-value">{max_streak} days</div>
      <div class="hc-label">Longest Listening Streak</div>
      <div class="hc-sub">Consecutive days with music</div>
    </div>

    <div class="highlight-card blue">
      <div class="hc-emoji">💿</div>
      <div class="hc-value">{unique_albums}</div>
      <div class="hc-label">Albums Explored</div>
      <div class="hc-sub">Across {unique_artists} artists</div>
    </div>

    <div class="highlight-card yellow">
      <div class="hc-emoji">🎵</div>
      <div class="hc-value">{int(total_minutes / total_plays):.0f}m</div>
      <div class="hc-label">Avg Session Length</div>
      <div class="hc-sub">Per qualified play</div>
    </div>

  </div>
</div>

<div class="section-divider"></div>

<!-- ============ MONTHLY TRENDS ============ -->
<div class="section">
  <div class="section-label">Over Time</div>
  <h2 class="section-title">Monthly Listening</h2>
  <div class="chart-section">
    {monthly_chart_html()}
  </div>
</div>

<div class="section-divider"></div>

<!-- ============ TIME OF DAY ============ -->
<div class="section">
  <div class="section-label">When You Listen</div>
  <h2 class="section-title">Time of Day</h2>
  <div class="tod-grid">
    {time_of_day_html()}
  </div>
</div>

<div class="section-divider"></div>

<!-- ============ TOP TRACKS ============ -->
<div class="section">
  <div class="section-label">Your Anthems</div>
  <h2 class="section-title">Top Tracks</h2>
  <div class="tracks-list">
    {top_tracks_html()}
  </div>
</div>

<div class="section-divider"></div>

<!-- ============ TOP ARTISTS ============ -->
<div class="section">
  <div class="section-label">Who You Ride With</div>
  <h2 class="section-title">Top Artists</h2>
  <div class="artists-grid">
    {top_artists_html()}
  </div>
</div>

<div class="section-divider"></div>

<!-- ============ TOP ALBUMS ============ -->
<div class="section">
  <div class="section-label">Most Revisited</div>
  <h2 class="section-title">Top Albums</h2>
  <div class="albums-grid">
    {album_cards_html()}
  </div>
</div>

<!-- ============ FOOTER ============ -->
<footer class="footer">
  <div class="footer-logo">🎧 Wrapped</div>
  <div>Generated {datetime.now().strftime("%B %d, %Y")} &nbsp;·&nbsp; {total_plays} plays &nbsp;·&nbsp; {unique_artists} artists</div>
</footer>

</body>
</html>"""

with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\n✅ Wrapped generated: {OUTPUT_HTML}")
print(f"   {total_plays} plays | {unique_artists} artists | {total_hours:.1f}h total")