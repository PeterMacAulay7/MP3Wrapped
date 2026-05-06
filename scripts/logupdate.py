import os
import json
import shutil
from datetime import datetime

from config_loader import LOG_PATH, STATE_FILE, RAW_DIR, PROCESSED_DIR

MASTER_FILE = LOG_PATH  # alias used below

os.makedirs(PROCESSED_DIR, exist_ok=True)

def parse_time(line):
    if "Time" in line:
        try:
            t = line.split("Time")[1].strip()
            return datetime.strptime(t, "%y%m%d-%H%M%S")
        except:
            return None
    return None

# Load last processed timestamp safely
if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r") as f:
            content = f.read().strip()
            if content:
                state = json.loads(content)
                last_time = datetime.fromisoformat(state["last_time"])
            else:
                last_time = datetime.min
    except:
        last_time = datetime.min
else:
    last_time = datetime.min

new_entries = []  # (timestamp, text_block)

# Collect entries from all files first
for filename in os.listdir(RAW_DIR):
    if not filename.endswith(".log"):
        continue

    path = os.path.join(RAW_DIR, filename)

    with open(path, "r", encoding="utf-8") as f:
        entry = []
        entry_time = None

        for line in f:
            if "# Started" in line and entry:
                if entry_time and entry_time > last_time:
                    new_entries.append((entry_time, "".join(entry)))
                entry = []
                entry_time = None

            entry.append(line)

            if entry_time is None:
                entry_time = parse_time(line)

        # last entry
        if entry and entry_time and entry_time > last_time:
            new_entries.append((entry_time, "".join(entry)))

# Sort entries by timestamp
new_entries.sort(key=lambda x: x[0])

# Deduplicate by full content
seen = set()
clean_entries = []

for t, text in new_entries:
    if text not in seen:
        seen.add(text)
        clean_entries.append((t, text))

# Append to master log
with open(MASTER_FILE, "a", encoding="utf-8") as f:
    for _, text in clean_entries:
        f.write(text)

# Update state
if clean_entries:
    latest_time = max(t for t, _ in clean_entries)
else:
    latest_time = last_time

with open(STATE_FILE, "w") as f:
    json.dump({"last_time": latest_time.isoformat()}, f)

# Move processed files
for filename in os.listdir(RAW_DIR):
    if not filename.endswith(".log"):
        continue

    src = os.path.join(RAW_DIR, filename)
    dst = os.path.join(PROCESSED_DIR, filename)
    shutil.move(src, dst)

print(f"Added {len(clean_entries)} entries. Last timestamp: {latest_time}")