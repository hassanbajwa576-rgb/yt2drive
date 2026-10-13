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
