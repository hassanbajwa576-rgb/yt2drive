yt2drive - Video -> Google Drive -> direct MP4 link for Universal Scheduler
=======================================================================

Use only for videos you own or have permission to reuse.

EASIEST WAY (Windows)
1. Put your video URLs in links.txt (one per line).
2. Double-click RUN.bat. It installs Python and the libraries if needed,
   then processes every link and opens links.csv with the results.

Before the first run, make sure the Google Drive API is ENABLED in your
Google Cloud project, and your Gmail is listed under
Google Auth Platform -> Audience -> Test users.

COMMAND LINE (optional)
   python yt2drive.py "https://www.youtube.com/watch?v=VIDEO_ID"
   python yt2drive.py URL1 URL2 URL3
   python yt2drive.py --file links.txt            (one URL per line)
   python yt2drive.py URL --caption "My caption #reels"

First run opens your browser to sign in to Google. You'll see
"Google hasn't verified this app" - click Continue (it's your own app).
After that, token.json remembers you.

WHAT IT DOES
- Downloads the video as MP4 (H.264 video + AAC audio, what Instagram accepts)
- Fixes/re-encodes it if needed so Instagram accepts it
- Uploads it to a "YT Uploads" folder in your Drive
- Sets it to "Anyone with the link can view"
- Prints a direct MP4 link and tests that it returns the video, not a web page
- Saves everything to links.csv

Paste the "Direct MP4" link into Universal Scheduler's video link field.

OPTIONS
  --reencode   always re-encode (use if Instagram rejects a video)
  --keep       keep the local MP4 after uploading

TIPS
- Keep Reels under ~100 MB and 90 seconds for the most reliable results.
- If "Link check: FAILED", the file is probably too large for Drive's direct link.
- Keep credentials.json and token.json private. Never upload them to GitHub.

DESKTOP APP (progress bars + built-in video search)
   Double-click RUN_APP.bat  (or run CREATE_SHORTCUT.bat once for a desktop icon).
   - Paste links or use "Find videos" to search YouTube (Creative Commons filter).
   - Live bars for search, download, processing, upload and overall progress.
   - Results go to links.csv, same as yt2drive.py.
   Try it without logging in:  python yt2drive_app.py --demo

WEB PANEL (control it from any browser)
   web/            = the panel (deployed on Vercel, password protected)
   yt2drive_worker.py = runs on your PC and does the real work for the panel
   Start the worker with RUN_WORKER.bat (INSTALL_WORKER_STARTUP.bat makes it start with Windows).
   worker_config.json holds the panel URL and worker key. It is NOT committed to GitHub.

RUN_CARTOON50.bat: finds 50 non-Creative-Commons cartoon clips (SpongeBob, Tom and Jerry, Looney Tunes ...),
uploads them to Drive, then schedules them on Instagram (affiliate captions) and LinkedIn (general captions)
every 30 minutes starting about 2 minutes after the last upload. Needs worker_config.json (scheduler key).

RUN_CREATORS50.bat: finds 50 non-Creative-Commons clips from famous content creators (MrBeast, IShowSpeed, Kai Cenat,
Markiplier, PewDiePie ...), uploads them, then schedules them on Instagram (affiliate captions) and LinkedIn every 30 minutes.
The start time is set after the previous queue; if you run it later than that, it starts about 2 minutes after the last upload.
