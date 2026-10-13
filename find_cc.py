#!/usr/bin/env python3
"""
find_cc.py - search YouTube's Creative Commons results and keep only videos whose licence is
confirmed as Creative Commons Attribution, short enough for a Reel. Writes cc_candidates.json.
"""
import json
import sys
from pathlib import Path

import yt_dlp

HERE = Path(__file__).resolve().parent
OUT = HERE / "cc_candidates.json"
LOG = HERE / "find_log.txt"

QUERIES = sys.argv[1:] or [
    "AI tutorial", "ChatGPT tips", "AI tools", "prompt engineering", "how to use AI",
    "AI productivity", "motivation", "motivational speech", "mindset", "discipline success",
    "self improvement", "habits",
]
# YouTube search filters: sorted by view count + Creative Commons + under 4 minutes
SP_VARIANTS = ["CAMSBBgBMAE%253D", "CAMSBBgBMAE%3D"]
PER_QUERY = 15
MAX_SECONDS = 90


def log(msg):
    print(msg, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


def search(query):
    for sp in SP_VARIANTS:
        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}&sp={sp}"
        opts = {"quiet": True, "extract_flat": True, "playlistend": PER_QUERY, "skip_download": True}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            entries = [e for e in (info.get("entries") or []) if e and e.get("id")]
            if entries:
                return entries
        except Exception as e:  # try the other encoding
            log(f"  search error ({sp}): {str(e)[:120]}")
    return []


def main():
    LOG.write_text("", encoding="utf-8")
    seen, found = set(), []
    full = yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True})
    for q in QUERIES:
        entries = search(q)
        log(f"[{q}] {len(entries)} results")
        for e in entries:
            vid = e["id"]
            if vid in seen:
                continue
            seen.add(vid)
            dur = e.get("duration")
            if dur and dur > MAX_SECONDS:
                continue
            try:
                info = full.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
            except Exception as ex:
                log(f"  skip {vid}: {str(ex)[:80]}")
                continue
            lic = info.get("license") or ""
            dur = info.get("duration") or 0
            if "creative commons" not in lic.lower() or dur > MAX_SECONDS or dur < 8:
                continue
            found.append({
                "query": q,
                "id": vid,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "title": info.get("title"),
                "channel": info.get("channel"),
                "channel_followers": info.get("channel_follower_count"),
                "views": info.get("view_count"),
                "likes": info.get("like_count"),
                "duration": dur,
                "upload_date": info.get("upload_date"),
                "license": lic,
                "description": (info.get("description") or "")[:600],
                "categories": info.get("categories"),
                "tags": (info.get("tags") or [])[:12],
            })
            log(f"  + {info.get('title')[:70]} | {info.get('channel')} | {info.get('view_count')} views | {dur}s")
        OUT.write_text(json.dumps(found, indent=1, ensure_ascii=False), encoding="utf-8")
    log(f"DONE: {len(found)} Creative Commons candidates saved to {OUT.name}")


if __name__ == "__main__":
    main()
