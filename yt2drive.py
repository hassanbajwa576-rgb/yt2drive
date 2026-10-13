#!/usr/bin/env python3
"""
yt2drive - download a video, upload it to Google Drive, and print a direct MP4 link
that a scheduler (e.g. Universal Scheduler) can fetch.

Only use this for videos you own or have permission/licence to reuse.

Usage:
    python yt2drive.py URL [URL ...]
    python yt2drive.py --file links.txt
    python yt2drive.py URL --reencode        # force Instagram-safe H.264/AAC MP4
    python yt2drive.py URL --caption "My caption #tags"
"""

import argparse
import csv
import datetime as dt
import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests
import yt_dlp
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# drive.file = the app can only see/manage files it created itself (safest scope)
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
HERE = Path(__file__).resolve().parent
CREDENTIALS = HERE / "credentials.json"
TOKEN = HERE / "token.json"
DOWNLOAD_DIR = HERE / "downloads"
LOG_FILE = HERE / "links.csv"
DRIVE_FOLDER_NAME = "YT Uploads"
try:
    FFMPEG = shutil.which("ffmpeg") or __import__("imageio_ffmpeg").get_ffmpeg_exe()
except Exception:
    FFMPEG = None
INSTAGRAM_MAX_MB = 100  # Instagram's own limit for video posts via API is larger for Reels,
                        # but small files are far more reliable over Drive direct links.


# ---------------------------------------------------------------- Google auth
def get_drive():
    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS.exists():
                sys.exit(f"Missing {CREDENTIALS.name}. Put it next to this script.")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
            creds = flow.run_local_server(port=0)  # opens your browser once
        TOKEN.write_text(creds.to_json())
    return build("drive", "v3", credentials=creds)


def get_or_create_folder(drive, name):
    q = (f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' "
         "and trashed = false")
    found = drive.files().list(q=q, fields="files(id)").execute().get("files", [])
    if found:
        return found[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    return drive.files().create(body=meta, fields="id").execute()["id"]


# ---------------------------------------------------------------- download
def download(url):
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    opts = {
        # Prefer H.264 video + AAC audio in MP4 (what Instagram accepts)
        "format": ("bv*[vcodec^=avc1][ext=mp4]+ba[ext=m4a]/"
                   "b[vcodec^=avc1][ext=mp4]/bv*+ba/b"),
        "merge_output_format": "mp4",
        "outtmpl": str(DOWNLOAD_DIR / "%(title).80s [%(id)s].%(ext)s"),
        "restrictfilenames": True,
        "noplaylist": True,
        **({"ffmpeg_location": FFMPEG} if FFMPEG else {}),
        "quiet": False,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info)).with_suffix(".mp4")
    if not path.exists():
        sys.exit(f"Download finished but file not found: {path}")
    return path, info


def probe_codecs(path):
    """Read codec names from ffmpeg's stream info (no ffprobe needed)."""
    import re
    try:
        err = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)],
                             capture_output=True, text=True).stderr
        return set(re.findall(r"Stream #.*?(?:Video|Audio): (\w+)", err))
    except Exception:
        return set()


def make_instagram_safe(path, force=False):
    """Re-encode to H.264/AAC MP4 with moov atom at the front (faststart)."""
    if not FFMPEG:
        print("! ffmpeg not found - skipping re-encode check.")
        return path
    codecs = probe_codecs(path)
    if not force and {"h264", "aac"} <= codecs:
        # Just move the moov atom to the front (fast, no quality loss)
        out = path.with_name(path.stem + "_ig.mp4")
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(path),
                        "-c", "copy", "-movflags", "+faststart", str(out)], check=True)
    else:
        print(f"Re-encoding to H.264/AAC (found codecs: {codecs or 'unknown'}) ...")
        out = path.with_name(path.stem + "_ig.mp4")
        subprocess.run([
            FFMPEG, "-y", "-loglevel", "error", "-i", str(path),
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-movflags", "+faststart", str(out)], check=True)
    path.unlink(missing_ok=True)
    return out


# ---------------------------------------------------------------- upload
def upload(drive, path, folder_id):
    meta = {"name": path.name, "parents": [folder_id]}
    media = MediaFileUpload(str(path), mimetype="video/mp4", resumable=True,
                            chunksize=8 * 1024 * 1024)
    req = drive.files().create(body=meta, media_body=media, fields="id, name, size")
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"  uploading... {int(status.progress() * 100)}%", end="\r")
    print("  uploading... 100%")
    file_id = resp["id"]
    # Anyone with the link can view (needed so the scheduler can fetch it)
    drive.permissions().create(
        fileId=file_id, body={"type": "anyone", "role": "reader"}).execute()
    return file_id


def direct_link(file_id):
    # confirm=t skips Drive's "can't scan for viruses" page for larger files
    return (f"https://drive.usercontent.google.com/download?id={file_id}"
            "&export=download&confirm=t")


def check_link(url):
    """Fetch the first bytes and confirm Drive returns a video, not an HTML page."""
    try:
        r = requests.get(url, headers={"Range": "bytes=0-1023"},
                         stream=True, timeout=30, allow_redirects=True)
        ctype = r.headers.get("Content-Type", "")
        r.close()
        return r.status_code in (200, 206) and not ctype.startswith("text/html"), ctype
    except requests.RequestException as e:
        return False, str(e)


def log(row):
    new = not LOG_FILE.exists()
    with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "source_url", "title", "drive_file_id",
                        "direct_mp4_link", "link_ok", "size_mb", "caption"])
        w.writerow(row)


# ---------------------------------------------------------------- main
def process(drive, folder_id, url, caption, reencode, keep):
    print(f"\n=== {url}")
    path, info = download(url)
    path = make_instagram_safe(path, force=reencode)
    size_mb = path.stat().st_size / 1_048_576
    print(f"File: {path.name} ({size_mb:.1f} MB)")
    if size_mb > INSTAGRAM_MAX_MB:
        print(f"! Over {INSTAGRAM_MAX_MB} MB - the Drive link and Instagram may reject it.")

    file_id = upload(drive, path, folder_id)
    link = direct_link(file_id)
    ok, ctype = check_link(link)

    print(f"Drive file ID : {file_id}")
    print(f"Direct MP4    : {link}")
    print(f"Link check    : {'OK' if ok else 'FAILED'} ({ctype})")
    if caption:
        print(f"Caption       : {caption}")
    if not ok:
        print("  -> Drive returned a web page instead of the video. Try a smaller "
              "file, or host it on Dropbox/R2 instead.")

    log([dt.datetime.now().isoformat(timespec="seconds"), url,
         info.get("title", ""), file_id, link, ok, f"{size_mb:.1f}", caption or ""])
    if not keep:
        path.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*", help="video URL(s)")
    ap.add_argument("--file", help="text file with one URL per line")
    ap.add_argument("--caption", help="caption to save alongside the link")
    ap.add_argument("--reencode", action="store_true",
                    help="always re-encode to Instagram-safe H.264/AAC")
    ap.add_argument("--keep", action="store_true",
                    help="keep the local MP4 after uploading")
    args = ap.parse_args()

    urls = list(args.urls)
    if args.file:
        urls += [l.strip() for l in Path(args.file).read_text().splitlines()
                 if l.strip() and not l.startswith("#")]
    if not urls:
        ap.print_help()
        sys.exit(1)

    drive = get_drive()
    folder_id = get_or_create_folder(drive, DRIVE_FOLDER_NAME)
    for url in urls:
        try:
            process(drive, folder_id, url, args.caption, args.reencode, args.keep)
        except Exception as e:
            print(f"! Failed on {url}: {e}")
    print(f"\nAll links saved to {LOG_FILE.name}")


if __name__ == "__main__":
    main()
