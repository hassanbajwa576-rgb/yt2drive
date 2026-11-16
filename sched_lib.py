"""Shared scheduling helpers: build captions and queue finished uploads on the Universal Scheduler."""
import datetime as dt
import json
import urllib.error
import urllib.request

HASHTAGS_IG = "#cartoon #funny #memes #reels #viral #ad"
HASHTAGS_LI = "#cartoon #funny #memes #reels #viral"
AFFILIATE = [
    ("XPPen Artist Ultra 16", "_c4NCCBNl"),
    ("Huion Kamvas 13 Gen 3", "_c3Niagwj"),
    ("Huion Kamvas 22", "_c36qnKCf"),
    ("Huion Kamvas Pro 13", "_c2woqGD1"),
]
HOOKS = ["Tag someone who needs to see this. 😂", "Wait for it. 😂", "Save this for later. 🔖",
         "Bring back the childhood. 📺", "Who remembers this? 😂"]


def post_json(url, key, body):
    r = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "yt2drive/1"})
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {"error": str(e)}


def _clean(title):
    t = (title or "").strip()
    return t[:147] + "..." if len(t) > 150 else t


def _yt_url(url):
    return url


def ig_caption(title, url, n):
    name, code = AFFILIATE[n % len(AFFILIATE)]
    return (f"🛒 Digital art tool I recommend: {name}\n"
            f"👉 https://s.click.aliexpress.com/e/{code} (affiliate link, I earn a small commission at no cost to you #ad)\n"
            f"🔗 Link also in bio.\n{HOOKS[n % len(HOOKS)]}\n"
            f"🎬 \"{_clean(title)}\" (source: {url})\n"
            f"Follow @hassanbajwa for practical AI tips, daily laughs and motivation. 🚀")


def li_caption(title, url, n):
    return (f"{HOOKS[n % len(HOOKS)]}\n🎬 \"{_clean(title)}\" (source: {url})\n"
            f"Follow for practical AI tips, daily laughs and motivation. 🚀")


def schedule_items(items, sched, scfg, say):
    """items: dicts with url/title/link/status. sched: {interval, startTime?, instagram, linkedin}."""
    if not scfg or not scfg.get("key"):
        say("Not scheduled: no scheduler key in worker_config.json")
        return
    base = scfg["url"].rstrip("/")
    done = [it for it in items if str(it.get("status", "")).startswith("Done") and it.get("link")]
    if not done:
        say("Nothing to schedule (no finished uploads)")
        return
    interval = max(1, int(sched.get("interval", 60)))
    if sched.get("startTime"):
        start = dt.datetime.fromisoformat(sched["startTime"].replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=dt.timezone.utc)
    else:
        start = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=2)
    results = []
    for platform, path, cap, tags in (("Instagram", "/api/posts", ig_caption, HASHTAGS_IG),
                                      ("LinkedIn", "/api/linkedin/posts", li_caption, HASHTAGS_LI)):
        if not sched.get(platform.lower()):
            continue
        posts = [{"caption": cap(it["title"], it["url"], n), "video_url": it["link"], "hashtags": tags}
                 for n, it in enumerate(done)]
        ok_total, err = 0, ""
        for b in range(0, len(posts), 50):
            chunk = posts[b:b + 50]
            when = start + dt.timedelta(minutes=interval * b)
            code, data = post_json(base + path, scfg["key"], {
                "posts": chunk, "interval": interval, "startTime": when.isoformat().replace("+00:00", "Z")})
            if code == 200 and data.get("success"):
                ok_total += len(chunk)
            else:
                err = f"{code}: {data.get('error', 'failed')}"
                break
        results.append(f"{platform}: {ok_total} scheduled" + (f" ({err})" if err else ""))
    say("Scheduled. " + "  ·  ".join(results) if results else "No platform selected for scheduling")
