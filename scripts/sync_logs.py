import os
import shutil
import subprocess
import string

# === CONFIG ===
DEST_RAW = r"C:\Users\peter\OneDrive\Desktop\My Stuff\wrapped\mp3-logs\raw"
LOGUPDATE_SCRIPT = r"C:\Users\peter\OneDrive\Desktop\My Stuff\wrapped\mp3-logs\scripts\logupdate.py"

def find_rockbox():
    for drive in string.ascii_uppercase:
        drive_path = f"{drive}:\\"
        if os.path.exists(drive_path):
            rockbox_path = os.path.join(drive_path, ".rockbox")
            if os.path.exists(rockbox_path):
                return rockbox_path
    return None

def copy_logs(src_dir, dest_dir):
    copied = 0
    for file in os.listdir(src_dir):
        if file.startswith("playback") and file.endswith(".log"):
            src = os.path.join(src_dir, file)
            dst = os.path.join(dest_dir, file)
            shutil.copy2(src, dst)
            copied += 1
    return copied

def main():
    rockbox = find_rockbox()

    if not rockbox:
        print("❌ Could not find .rockbox folder on any drive")
        return

    print(f"✅ Found Rockbox at: {rockbox}")

    logs_copied = copy_logs(rockbox, DEST_RAW)
    print(f"📁 Copied {logs_copied} log files")

    if logs_copied == 0:
        print("⚠️ No new logs found")
        return

    print("🚀 Running logupdate.py...")
    subprocess.run(["python", LOGUPDATE_SCRIPT])

if __name__ == "__main__":
    main()