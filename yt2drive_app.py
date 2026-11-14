#!/usr/bin/env python3
"""
YT -> Drive  (desktop app for yt2drive)

Paste YouTube links, press Start. The app downloads each video, makes it Instagram-safe,
uploads it to your Google Drive ("YT Uploads" folder) and gives you a direct MP4 link,
with live progress bars for every step. Every result is also saved to links.csv, exactly
like yt2drive.py does, so nothing else in your workflow changes.

Only use this for videos you own or have permission to reuse.

Run:   double-click RUN_APP.bat      (or:  python yt2drive_app.py)
Demo:  python yt2drive_app.py --demo (simulated progress, no network, no Google login)
"""
import csv
import json
import os
import queue
import re
import sys
import random
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
DEMO = "--demo" in sys.argv
AUTO = "--autostart" in sys.argv
FIND_N = int(sys.argv[sys.argv.index("--find") + 1]) if "--find" in sys.argv[:-1] else None
LINKS_FILE = sys.argv[sys.argv.index("--file") + 1] if "--file" in sys.argv[:-1] else None

# ------------------------------------------------------------------ theme
BG = "#0e1015"
CARD = "#161a22"
CARD2 = "#1b202a"
LINE = "#2a3040"
FG = "#e9ecf3"
MUTED = "#8a93a8"
ACCENT = "#6d8dff"
GREEN = "#37d29a"
AMBER = "#f2b94b"
RED = "#ff6b6b"
TROUGH = "#242a37"

URL_RE = re.compile(r"https?://[^\s\"'<>]+")
YT_ID_RE = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})")

# how much each step counts towards the overall bar
W_DL, W_PROC, W_UL, W_CHECK = 0.45, 0.05, 0.45, 0.05


class Cancelled(Exception):
    pass


# ------------------------------------------------------------------ helpers
def fmt_bytes(n):
    if not n:
        return "0 MB"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def fmt_speed(bps):
    return f"{fmt_bytes(bps)}/s" if bps else "…"


def fmt_eta(sec):
    if sec is None:
        return "…"
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


def youtube_id(url):
    m = YT_ID_RE.search(url or "")
    return m.group(1) if m else None


def parse_urls(text):
    seen, out = set(), []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for u in URL_RE.findall(line):
            u = u.rstrip(".,);]")
            key = youtube_id(u) or u
            if key not in seen:
                seen.add(key)
                out.append(u)
    return out


def open_path(p):
    p = str(p)
    if sys.platform.startswith("win"):
        os.startfile(p)  # noqa
    elif sys.platform == "darwin":
        os.system(f'open "{p}"')
    else:
        os.system(f'xdg-open "{p}" >/dev/null 2>&1 &')


class QWriter:
    """Routes print() output of yt2drive.py into the log pane."""

    def __init__(self, q):
        self.q = q

    def write(self, s):
        s = s.replace("\r", "\n")
        for line in s.split("\n"):
            if line.strip():
                self.q.put(("log", line.strip()))

    def flush(self):
        pass


# ------------------------------------------------------------------ worker
def already_uploaded():
    """source video id -> direct link, from links.csv"""
    found = {}
    f = HERE / "links.csv"
    if not f.exists():
        return found
    try:
        with f.open(newline="", encoding="utf-8", errors="ignore") as fh:
            for row in csv.DictReader(fh):
                vid = youtube_id(row.get("source_url", ""))
                if vid and row.get("link_ok", "").lower() == "true":
                    found[vid] = row.get("direct_mp4_link", "")
    except Exception:
        pass
    return found


# ------------------------------------------------------------------ video finder
SPS = ["CAMSBBgBMAE%253D", "EgIwAQ%253D%253D"]
TOPICS = ['watercolor landscape tutorial', 'watercolor portrait', 'watercolor birds', 'watercolor trees', 'watercolor mountains', 'watercolor ocean', 'watercolor leaves', 'loose watercolor', 'watercolor galaxy', 'gouache landscape', 'gouache tutorial', 'acrylic portrait painting', 'acrylic seascape', 'acrylic night sky painting', 'acrylic fluid art', 'acrylic palette knife', 'palette knife painting', 'impasto painting', 'oil painting portrait', 'oil painting still life', 'oil painting clouds', 'oil painting sky', 'oil painting tips', 'underpainting', 'color theory painting', 'limited palette painting', 'painting trees tutorial', 'painting water reflections', 'painting mountains', 'painting snow', 'painting roses', 'painting sunflowers', 'painting fruit', 'painting eyes', 'painting skin tones', 'drawing hands tutorial', 'drawing hair tutorial', 'drawing nose', 'drawing ears', 'drawing eyes step by step', 'drawing faces from different angles', 'gesture drawing', 'figure drawing tips', 'life drawing', 'drawing perspective', 'one point perspective', 'two point perspective', 'drawing shadows', 'drawing light and shadow', 'cross hatching', 'hatching and stippling', 'stippling art', 'pen and ink drawing', 'fineliner drawing', 'ballpoint pen drawing', 'graphite drawing', 'graphite portrait', 'colored pencil tutorial', 'colored pencil blending', 'prismacolor', 'polychromos', 'pencil drawing realistic', 'sketchbook tour', 'sketchbook tips', 'urban sketching', 'plein air painting', 'landscape sketch ink', 'architecture sketch', 'still life drawing', 'fruit drawing', 'flower drawing easy', 'rose drawing', 'tree drawing', 'mountain drawing', 'ocean drawing', 'sky drawing clouds', 'drawing for beginners', 'easy drawing ideas', 'art tips', 'art techniques', 'art hacks', 'art challenge', 'art process', 'time lapse painting', 'time lapse drawing', 'digital art tips', 'digital art tutorial', 'digital illustration process', 'photoshop brushes', 'illustrator tutorial', 'affinity designer', 'vector art tutorial', 'concept art tutorial', 'environment design art', 'character design tips', 'color palette tips', 'composition tips art', 'art fundamentals', 'art anatomy', 'art studio', 'artist at work', 'mural painting', 'canvas painting ideas', 'abstract art tutorial', 'abstract painting easy', 'texture painting', 'resin art', 'alcohol ink art', 'ink painting', 'brush calligraphy', 'hand lettering tutorial', 'modern calligraphy', 'bullet journal art', 'mandala art', 'zentangle', 'doodle art', 'sticker art', 'watercolor lettering', 'paper art', 'sculpture process', 'pottery painting', 'ceramic painting', 'linoleum print', 'woodcut print', 'monoprint', 'gelli plate printing', 'collage tutorial', 'mixed media tutorial']
ART_RE = re.compile(r"draw|sketch|paint|watercolou?r|acrylic|gouache|pastel|charcoal|pencil|ink|calligraph|lettering|doodle|illustrat|portrait|art\b|artist|canvas|brush|procreate|dibuj|pint|color mixing|colour mixing|shading|anatomy|perspective", re.I)
BAD_RE = re.compile(r"logo|brand|nezuko|naruto|goku|anime|manga|berserk|squid ?game|titanic|k-?pop|newjeans|ive\b|bts|blackpink|celebrit|connery|horse|breyer|warhammer|disney|pokemon|pikachu|spider|batman|superman|barbie|mario|sonic|movie|film|trailer|roblox|fan ?anim|simpsons|marvel|avenger|iron ?man|poppy|sprunki|hazbin|ddlc|meme|prank|rhymes|squishmallow|minecraft|fortnite|skibidi|brainrot|indian|aunty|aunties|animal|cat\b|dog\b|house|wall\b|walls\b|body ?paint|face ?paint|yoga|fondant|apartment|decor|roof|fence|furniture|corpse|costume|dark souls|castlevania|molang|ratajkowski|jolie|fnaf|freddy|winx|totoro|jolie|karambit|knife|weapon|gun\b|blender|maya\b|makeup|tattoo|ishowspeed|kids|children|toddler|cartoon network|racing|drift|krishna|ganesh|ice spice|actor|singer|song\b|lyrics|bob ?ross|zelda|link\b|naruto|ghibli|sailor|umamusume|loid|spy x", re.I)


def _ytdlp(args):
    kw = {"creationflags": 0x08000000} if sys.platform.startswith("win") else {}
    r = subprocess.run([sys.executable, "-m", "yt_dlp", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore", **kw)
    return r.stdout


def _num(x):
    try:
        return int(float(x))
    except Exception:
        return 0


def used_ids():
    ids = set()
    for p in list(HERE.glob("links.csv")) + list(HERE.glob("b*_picks.json")) + list(HERE.glob("find_picks*.json")):
        try:
            ids.update(re.findall(r"[\w-]{11}", p.read_text(encoding="utf-8", errors="ignore")))
        except Exception:
            pass
    return ids


def run_find(opts, q, cancel):
    if DEMO:
        want = opts["count"]
        for i in range(21):
            if cancel.is_set():
                q.put(("find_end", [], "Search cancelled"))
                return
            q.put(("find", i * 5, f"Demo search  ·  {i * want // 20} found"))
            time.sleep(0.08)
        q.put(("find_end", [f"https://www.youtube.com/watch?v=DEMO{n:07d}x" for n in range(min(want, 6))], ""))
        return
    want = opts["count"]
    custom = [t.strip() for t in opts["topics"].split(",") if t.strip()]
    topics = custom or random.sample(TOPICS, len(TOPICS))
    q.put(("find", 1, "Searching YouTube…"))
    used = used_ids()
    found = {}
    try:
        for i, t in enumerate(topics):
            if cancel.is_set() or len(found) >= want * 3:
                break
            for sp in SPS:
                url = f"https://www.youtube.com/results?search_query={t.replace(' ', '+')}&sp={sp}"
                out = _ytdlp(["--flat-playlist", "--no-warnings", "--print",
                              "%(id)s|%(view_count)s|%(duration)s|%(channel)s|%(title)s", url])
                for line in out.splitlines():
                    p = line.split("|", 4)
                    if len(p) < 5:
                        continue
                    vid, views, dur, ch, title = p
                    d = _num(dur)
                    if vid in used or vid in found or not (10 <= d <= 180) or _num(views) < 500:
                        continue
                    if not custom and (not ART_RE.search(title) or BAD_RE.search(title + " " + ch)):
                        continue
                    found[vid] = dict(id=vid, channel=ch, title=title, views=_num(views), duration=d)
            pct = min(40, max(len(found) / (want * 3), (i + 1) / len(topics)) * 40)
            q.put(("find", pct, f"Searching “{t}”  ·  {len(found)} candidates"))
        cands = sorted(found.values(), key=lambda v: -v["views"])
        picks, per = [], {}
        for n, v in enumerate(cands):
            if cancel.is_set() or len(picks) >= want:
                break
            if per.get(v["channel"], 0) >= 3:
                continue
            ok = True
            if opts["cc_only"]:
                lic = _ytdlp(["--no-warnings", "--skip-download", "--print", "%(license)s",
                              f"https://www.youtube.com/watch?v={v['id']}"]).strip()
                ok = "Creative Commons Attribution" in lic
            if ok:
                picks.append(v)
                per[v["channel"]] = per.get(v["channel"], 0) + 1
            q.put(("find", 40 + len(picks) / want * 60,
                   f"Checking licences  ·  {len(picks)} of {want} picked  ·  checked {n + 1} of {len(cands)}"))
        if cancel.is_set():
            q.put(("find_end", [], "Search cancelled"))
            return
        (HERE / "find_picks.json").write_text(json.dumps(picks, ensure_ascii=False, indent=1), encoding="utf-8")
        urls = [f"https://www.youtube.com/watch?v={v['id']}" for v in picks]
        q.put(("find_end", urls, ""))
    except Exception as e:
        q.put(("find_end", [], f"Search failed: {e}"))


def run_demo(urls, opts, q, cancel):
    import random
    q.put(("folder", "demo"))
    for i, url in enumerate(urls):
        if cancel.is_set():
            q.put(("cancelled_rest", i))
            break
        q.put(("start", i, url))
        q.put(("title", i, f"Demo video {i + 1}: " + ("Patrick saying Friend meme", "Oil painting tutorial",
                                                         "Funny cat daily routine")[i % 3]))
        total = random.randint(4, 40) * 1024 * 1024
        done = 0
        while done < total:
            if cancel.is_set():
                break
            done = min(total, done + total // 40)
            q.put(("dl", i, done / total * 100, 3.5e6 + random.random() * 2e6, (total - done) / 4e6, done, total))
            time.sleep(0.04)
        if cancel.is_set():
            q.put(("status", i, "Cancelled"))
            q.put(("cancelled_rest", i + 1))
            break
        q.put(("stage", i, "process"))
        time.sleep(0.9)
        q.put(("stage", i, "upload"))
        done = 0
        while done < total:
            if cancel.is_set():
                break
            done = min(total, done + total // 30)
            q.put(("ul", i, done / total * 100, done, total, 2.2e6 + random.random() * 1e6))
            time.sleep(0.05)
        if cancel.is_set():
            q.put(("status", i, "Cancelled"))
            q.put(("cancelled_rest", i + 1))
            break
        q.put(("stage", i, "check"))
        time.sleep(0.5)
        if i == 1 and len(urls) > 2:
            q.put(("fail", i, "Demo: simulated failure (video unavailable)"))
            continue
        q.put(("done_item", i, f"https://drive.usercontent.google.com/download?id=DEMO{i}&export=download&confirm=t",
               True, total / 1048576))
    q.put(("finished",))


def run_real(urls, opts, q, cancel):
    try:
        import yt2drive as Y
        import yt_dlp
        from googleapiclient.http import MediaFileUpload
    except Exception as e:  # missing libs
        q.put(("fatal", f"A required library is missing:\n\n{e}\n\n"
                        "Run RUN.bat once (it installs everything), then open the app again."))
        return

    q.put(("global", "Signing in to Google…"))
    try:
        drive = Y.get_drive()
        folder_id = Y.get_or_create_folder(drive, Y.DRIVE_FOLDER_NAME)
    except SystemExit as e:
        q.put(("fatal", str(e)))
        return
    except Exception as e:
        q.put(("fatal", f"Google sign-in failed:\n\n{e}"))
        return
    q.put(("folder", folder_id))
    q.put(("global", ""))

    done_map = already_uploaded() if opts["skip_done"] else {}

    for i, url in enumerate(urls):
        if cancel.is_set():
            q.put(("cancelled_rest", i))
            break
        q.put(("start", i, url))
        vid = youtube_id(url)
        if vid and vid in done_map:
            q.put(("skip", i, done_map[vid]))
            continue
        path = None
        try:
            # ---------------- download
            files = {}

            def hook(d):
                if cancel.is_set():
                    raise Cancelled()
                info = d.get("info_dict") or {}
                if info.get("title") and not files.get("_titled"):
                    files["_titled"] = True
                    q.put(("title", i, info["title"]))
                fn = d.get("filename") or ""
                if d["status"] == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    files[fn] = (d.get("downloaded_bytes") or 0, total)
                elif d["status"] == "finished":
                    t = d.get("total_bytes") or d.get("downloaded_bytes") or 0
                    files[fn] = (t, t)
                else:
                    return
                parts = [v for k, v in files.items() if k != "_titled"]
                done = sum(p[0] for p in parts)
                tot = sum(p[1] for p in parts)
                exp = 0
                for rf in info.get("requested_formats") or []:
                    exp += rf.get("filesize") or rf.get("filesize_approx") or 0
                tot = max(tot, exp)
                pct = min(99.0, done / tot * 100) if tot else 0
                q.put(("dl", i, pct, d.get("speed"), d.get("eta"), done, tot))

            Y.DOWNLOAD_DIR.mkdir(exist_ok=True)
            ydl_opts = {
                "format": ("bv*[vcodec^=avc1][ext=mp4]+ba[ext=m4a]/b[vcodec^=avc1][ext=mp4]/bv*+ba/b"),
                "merge_output_format": "mp4",
                "outtmpl": str(Y.DOWNLOAD_DIR / "%(title).80s [%(id)s].%(ext)s"),
                "restrictfilenames": True,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
                "progress_hooks": [hook],
                **({"ffmpeg_location": Y.FFMPEG} if Y.FFMPEG else {}),
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                path = Path(ydl.prepare_filename(info)).with_suffix(".mp4")
            if not path.exists():
                raise RuntimeError(f"Download finished but file not found: {path.name}")
            title = info.get("title", "")
            q.put(("title", i, title))
            q.put(("dl", i, 100, None, 0, 1, 1))
            if cancel.is_set():
                raise Cancelled()

            # ---------------- process (ffmpeg)
            q.put(("stage", i, "process"))
            path = Y.make_instagram_safe(path, force=opts["reencode"])
            size = path.stat().st_size
            size_mb = size / 1_048_576
            if cancel.is_set():
                raise Cancelled()

            # ---------------- upload
            q.put(("stage", i, "upload"))
            meta = {"name": path.name, "parents": [folder_id]}
            media = MediaFileUpload(str(path), mimetype="video/mp4", resumable=True, chunksize=1024 * 1024)
            req = drive.files().create(body=meta, media_body=media, fields="id, name, size")
            resp, t0 = None, time.time()
            while resp is None:
                if cancel.is_set():
                    raise Cancelled()
                status, resp = req.next_chunk(num_retries=3)
                if status:
                    sent = status.resumable_progress
                    q.put(("ul", i, status.progress() * 100, sent, size, sent / max(0.1, time.time() - t0)))
            q.put(("ul", i, 100, size, size, size / max(0.1, time.time() - t0)))
            file_id = resp["id"]
            drive.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"}).execute()

            # ---------------- check link
            q.put(("stage", i, "check"))
            link = Y.direct_link(file_id)
            ok, ctype = Y.check_link(link)
            import datetime as dt
            Y.log([dt.datetime.now().isoformat(timespec="seconds"), url, title, file_id, link, ok,
                   f"{size_mb:.1f}", opts["caption"] or ""])
            if not opts["keep"]:
                path.unlink(missing_ok=True)
            if ok:
                q.put(("done_item", i, link, True, size_mb))
            else:
                q.put(("done_item", i, link, False, size_mb))
        except Cancelled:
            q.put(("status", i, "Cancelled"))
            q.put(("cancelled_rest", i + 1))
            break
        except Exception as e:
            msg = str(e).replace("ERROR: ", "")
            q.put(("fail", i, msg[:300]))
    q.put(("finished",))


# ------------------------------------------------------------------ UI widgets
class StepRow:
    """label + progress bar + percent + detail line"""

    def __init__(self, parent, row, name, style):
        self.style = style
        self.name = tk.Label(parent, text=name, bg=CARD, fg=FG, font=("Segoe UI", 10, "bold"), width=11, anchor="w")
        self.bar = ttk.Progressbar(parent, style=style, mode="determinate", maximum=100)
        self.pct = tk.Label(parent, text="—", bg=CARD, fg=MUTED, font=("Segoe UI", 12, "bold"), width=6, anchor="e")
        self.info = tk.Label(parent, text="", bg=CARD, fg=MUTED, font=("Segoe UI", 9), anchor="w")
        self.name.grid(row=row * 2, column=0, sticky="w", pady=(4, 0))
        self.bar.grid(row=row * 2, column=1, sticky="ew", padx=12, pady=(4, 0))
        self.pct.grid(row=row * 2, column=2, sticky="e", pady=(4, 0))
        self.info.grid(row=row * 2 + 1, column=1, sticky="w", padx=12)
        self.reset()

    def reset(self):
        self.bar.stop()
        self.bar.configure(mode="determinate")
        self.bar["value"] = 0
        self.pct.configure(text="—", fg=MUTED)
        self.info.configure(text="")

    def set(self, pct, info=None, color=FG):
        if str(self.bar["mode"]) != "determinate":
            self.bar.stop()
            self.bar.configure(mode="determinate")
        self.bar["value"] = pct
        self.pct.configure(text=f"{pct:.0f}%", fg=color)
        if info is not None:
            self.info.configure(text=info)

    def spin(self, info=""):
        self.bar.configure(mode="indeterminate")
        self.bar.start(14)
        self.pct.configure(text="…", fg=AMBER)
        self.info.configure(text=info)

    def finish(self, info=None):
        self.set(100, info, GREEN)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YT → Drive" + ("  (demo)" if DEMO else ""))
        self.geometry("1020x1000")
        self.minsize(900, 820)
        self.configure(bg=BG)
        self.q = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.items = []
        self.frac = []
        self.folder_id = None
        self.running = False
        self.finding = False
        self.t_start = 0

        sys.stdout = QWriter(self.q)
        sys.stderr = QWriter(self.q)

        self._style()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-Return>", lambda e: self.start())
        self.after(50, self._poll)
        if LINKS_FILE and Path(LINKS_FILE).exists():
            self.txt.insert("1.0", Path(LINKS_FILE).read_text(encoding="utf-8", errors="ignore"))
            if AUTO:
                self.after(900, self.start)
        if FIND_N:
            self.after(700, self.find)

    # ---------------------------------------------------------- styling
    def _style(self):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        names = set(tkfont.families())
        self.ff = "Segoe UI" if "Segoe UI" in names else ("Helvetica" if "Helvetica" in names else "TkDefaultFont")
        s = ttk.Style(self)
        s.theme_use("clam")
        for name, color in (("Find", "#b48cff"), ("Dl", ACCENT), ("Proc", AMBER), ("Ul", GREEN), ("All", ACCENT)):
            s.configure(f"{name}.Horizontal.TProgressbar", troughcolor=TROUGH, background=color,
                        bordercolor=TROUGH, lightcolor=color, darkcolor=color, thickness=16 if name != "All" else 10)
        s.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=FG, rowheight=30,
                    borderwidth=0, font=(self.ff, 10))
        s.map("Treeview", background=[("selected", "#27304a")], foreground=[("selected", FG)])
        s.configure("Treeview.Heading", background=CARD2, foreground=MUTED, borderwidth=0,
                    font=(self.ff, 9, "bold"), relief="flat")
        s.map("Treeview.Heading", background=[("active", CARD2)])
        s.configure("Vertical.TScrollbar", background=CARD2, troughcolor=CARD, bordercolor=CARD,
                    arrowcolor=MUTED, lightcolor=CARD2, darkcolor=CARD2)
        s.configure("TCheckbutton", background=CARD, foreground=FG, font=(self.ff, 10))
        s.map("TCheckbutton", background=[("active", CARD)], foreground=[("active", FG)])

    def _btn(self, parent, text, cmd, kind="ghost", **kw):
        colors = {"primary": (ACCENT, "#0b1020", "#8aa4ff"), "danger": ("#3a2328", RED, "#4a2a30"),
                  "ghost": (CARD2, FG, "#252c3a")}
        bg, fg, hov = colors[kind]
        b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, activebackground=hov, activeforeground=fg,
                      relief="flat", bd=0, padx=16, pady=8, cursor="hand2", font=(self.ff, 10, "bold"), **kw)
        b.bind("<Enter>", lambda e: b.configure(bg=hov) if str(b["state"]) == "normal" else None)
        b.bind("<Leave>", lambda e: b.configure(bg=bg))
        b._base = bg
        return b

    def _card(self, parent, **grid):
        f = tk.Frame(parent, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        f.grid(**grid)
        return f

    # ---------------------------------------------------------- layout
    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        pad = 18

        # header
        hd = tk.Frame(self, bg=BG)
        hd.grid(row=0, column=0, sticky="ew", padx=pad, pady=(16, 8))
        hd.columnconfigure(0, weight=1)
        tk.Label(hd, text="YT  →  Drive", bg=BG, fg=FG, font=(self.ff, 20, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(hd, text="Download videos, upload them to Google Drive, get direct MP4 links.",
                 bg=BG, fg=MUTED, font=(self.ff, 10)).grid(row=1, column=0, sticky="w")
        self.pill = tk.Label(hd, text="  Idle  ", bg=CARD2, fg=MUTED, font=(self.ff, 10, "bold"), padx=8, pady=4)
        self.pill.grid(row=0, column=1, rowspan=2, sticky="e")

        # find card
        fc = self._card(self, row=1, column=0, sticky="ew", padx=pad, pady=6)
        fc.columnconfigure(1, weight=1)
        tk.Label(fc, text="Find videos", bg=CARD, fg=FG, font=(self.ff, 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 2))
        tk.Label(fc, text="Searches YouTube, checks licences, and fills the list below.",
                 bg=CARD, fg=MUTED, font=(self.ff, 9)).grid(row=0, column=1, sticky="w", padx=8, pady=(12, 2))
        fr = tk.Frame(fc, bg=CARD)
        fr.grid(row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(4, 12))
        fr.columnconfigure(3, weight=1)
        tk.Label(fr, text="How many", bg=CARD, fg=MUTED, font=(self.ff, 10)).grid(row=0, column=0, padx=(0, 6))
        self.v_count = tk.IntVar(value=FIND_N or 50)
        tk.Spinbox(fr, from_=1, to=200, width=5, textvariable=self.v_count, bg="#10131a", fg=FG, relief="flat",
                   buttonbackground=CARD2, insertbackground=FG, font=(self.ff, 10), highlightthickness=1,
                   highlightbackground=LINE).grid(row=0, column=1, ipady=4, padx=(0, 14))
        tk.Label(fr, text="Topics", bg=CARD, fg=MUTED, font=(self.ff, 10)).grid(row=0, column=2, padx=(0, 6))
        self.topics = tk.Entry(fr, bg="#10131a", fg=FG, insertbackground=FG, relief="flat", bd=0,
                               font=(self.ff, 10), highlightthickness=1, highlightbackground=LINE,
                               highlightcolor=ACCENT)
        self.topics.grid(row=0, column=3, sticky="ew", ipady=5, padx=(0, 14))
        self.v_cc = tk.BooleanVar(value=True)
        self.v_auto = tk.BooleanVar(value=True)
        ttk.Checkbutton(fr, text="Creative Commons only", variable=self.v_cc).grid(row=0, column=4, padx=(0, 10))
        ttk.Checkbutton(fr, text="Upload right after", variable=self.v_auto).grid(row=0, column=5, padx=(0, 14))
        self.b_find = self._btn(fr, "🔍  Find videos", self.find, "primary")
        self.b_find.grid(row=0, column=6)
        tk.Label(fr, text="Leave Topics empty for the built-in art topics, or type your own, separated by commas.",
                 bg=CARD, fg=MUTED, font=(self.ff, 9)).grid(row=1, column=0, columnspan=7, sticky="w", pady=(6, 0))

        # top: input + options
        top = self._card(self, row=2, column=0, sticky="ew", padx=pad, pady=6)
        top.columnconfigure(0, weight=1)
        tk.Label(top, text="Video links  (one per line)", bg=CARD, fg=FG, font=(self.ff, 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 4))
        self.txt = tk.Text(top, height=3, bg="#10131a", fg=FG, insertbackground=FG, relief="flat", bd=0,
                           font=("Consolas", 10), padx=10, pady=8, wrap="none", highlightthickness=1,
                           highlightbackground=LINE, highlightcolor=ACCENT)
        self.txt.grid(row=1, column=0, columnspan=2, sticky="ew", padx=14)
        side = tk.Frame(top, bg=CARD)
        side.grid(row=0, column=1, sticky="e", padx=14, pady=(10, 0))
        self._btn(side, "Paste", self._paste).pack(side="left", padx=(0, 6))
        self._btn(side, "Open file…", self._open_file).pack(side="left", padx=(0, 6))
        self._btn(side, "Clear", lambda: self.txt.delete("1.0", "end")).pack(side="left")

        opt = tk.Frame(top, bg=CARD)
        opt.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(10, 4))
        self.v_re = tk.BooleanVar(value=False)
        self.v_keep = tk.BooleanVar(value=False)
        self.v_skip = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt, text="Re-encode for Instagram", variable=self.v_re).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(opt, text="Keep local files", variable=self.v_keep).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(opt, text="Skip links already uploaded", variable=self.v_skip).pack(side="left", padx=(0, 16))
        tk.Label(opt, text="Caption:", bg=CARD, fg=MUTED, font=(self.ff, 10)).pack(side="left", padx=(8, 4))
        self.caption = tk.Entry(opt, bg="#10131a", fg=FG, insertbackground=FG, relief="flat", bd=0,
                                font=(self.ff, 10), highlightthickness=1, highlightbackground=LINE,
                                highlightcolor=ACCENT)
        self.caption.pack(side="left", fill="x", expand=True, ipady=5)

        act = tk.Frame(top, bg=CARD)
        act.grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(8, 14))
        act.columnconfigure(2, weight=1)
        self.b_start = self._btn(act, "▶  Start   (Ctrl+Enter)", self.start, "primary")
        self.b_start.grid(row=0, column=0, sticky="w")
        self.b_cancel = self._btn(act, "Cancel", self.stop, "danger")
        self.b_cancel.grid(row=0, column=1, padx=8)
        self.b_cancel.configure(state="disabled")
        self.lbl_global = tk.Label(act, text="", bg=CARD, fg=MUTED, font=(self.ff, 10), anchor="e")
        self.lbl_global.grid(row=0, column=2, sticky="e")

        # middle: current + queue
        mid = tk.Frame(self, bg=BG)
        mid.grid(row=3, column=0, sticky="nsew", padx=pad, pady=6)
        mid.columnconfigure(0, weight=1)
        mid.rowconfigure(1, weight=1)

        cur = self._card(mid, row=0, column=0, sticky="ew")
        cur.columnconfigure(0, weight=1)
        head = tk.Frame(cur, bg=CARD)
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))
        head.columnconfigure(0, weight=1)
        self.lbl_title = tk.Label(head, text="Nothing running", bg=CARD, fg=FG, font=(self.ff, 12, "bold"),
                                  anchor="w", justify="left")
        self.lbl_title.grid(row=0, column=0, sticky="ew")
        self.lbl_count = tk.Label(head, text="", bg=CARD, fg=MUTED, font=(self.ff, 10, "bold"))
        self.lbl_count.grid(row=0, column=1, sticky="e")
        steps = tk.Frame(cur, bg=CARD)
        steps.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 4))
        steps.columnconfigure(1, weight=1)
        self.r_find = StepRow(steps, 0, "Finding", "Find.Horizontal.TProgressbar")
        self.r_dl = StepRow(steps, 1, "Download", "Dl.Horizontal.TProgressbar")
        self.r_pr = StepRow(steps, 2, "Processing", "Proc.Horizontal.TProgressbar")
        self.r_ul = StepRow(steps, 3, "Upload", "Ul.Horizontal.TProgressbar")
        ov = tk.Frame(cur, bg=CARD)
        ov.grid(row=2, column=0, sticky="ew", padx=14, pady=(8, 14))
        ov.columnconfigure(1, weight=1)
        tk.Label(ov, text="Overall", bg=CARD, fg=FG, font=(self.ff, 10, "bold"), width=11, anchor="w").grid(row=0, column=0)
        self.bar_all = ttk.Progressbar(ov, style="All.Horizontal.TProgressbar", maximum=100)
        self.bar_all.grid(row=0, column=1, sticky="ew", padx=12)
        self.lbl_all = tk.Label(ov, text="0%", bg=CARD, fg=FG, font=(self.ff, 12, "bold"), width=6, anchor="e")
        self.lbl_all.grid(row=0, column=2)
        self.lbl_all_info = tk.Label(ov, text="", bg=CARD, fg=MUTED, font=(self.ff, 9), anchor="w")
        self.lbl_all_info.grid(row=1, column=1, sticky="w", padx=12)

        qc = self._card(mid, row=1, column=0, sticky="nsew", pady=(10, 0))
        qc.columnconfigure(0, weight=1)
        qc.rowconfigure(1, weight=1)
        qh = tk.Frame(qc, bg=CARD)
        qh.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(10, 6))
        qh.columnconfigure(0, weight=1)
        tk.Label(qh, text="Queue & results", bg=CARD, fg=FG, font=(self.ff, 10, "bold")).grid(row=0, column=0, sticky="w")
        bt = tk.Frame(qh, bg=CARD)
        bt.grid(row=0, column=1, sticky="e")
        self._btn(bt, "Copy link", self.copy_selected).pack(side="left", padx=3)
        self._btn(bt, "Copy all links", self.copy_all).pack(side="left", padx=3)
        self._btn(bt, "links.csv", lambda: self._open_local("links.csv")).pack(side="left", padx=3)
        self._btn(bt, "Drive folder", self.open_drive).pack(side="left", padx=3)
        cols = ("n", "title", "status", "size")
        self.tree = ttk.Treeview(qc, columns=cols, show="headings", selectmode="browse", height=7)
        for c, t, w, a in (("n", "#", 40, "center"), ("title", "Video", 470, "w"),
                           ("status", "Status", 300, "w"), ("size", "Size", 80, "e")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=a, stretch=(c == "title"))
        sb = ttk.Scrollbar(qc, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(14, 0), pady=(0, 12))
        sb.grid(row=1, column=1, sticky="ns", padx=(0, 10), pady=(0, 12))
        for tag, col in (("queued", MUTED), ("active", ACCENT), ("done", GREEN), ("warn", AMBER),
                         ("fail", RED), ("skip", MUTED)):
            self.tree.tag_configure(tag, foreground=col)
        self.tree.bind("<Double-1>", lambda e: self.copy_selected())

        # bottom: log
        bot = tk.Frame(self, bg=BG)
        bot.grid(row=4, column=0, sticky="ew", padx=pad, pady=(2, 14))
        bot.columnconfigure(0, weight=1)
        self.v_log = tk.BooleanVar(value=False)
        self.b_log = tk.Label(bot, text="▸ Show log", bg=BG, fg=MUTED, font=(self.ff, 9, "bold"), cursor="hand2")
        self.b_log.grid(row=0, column=0, sticky="w")
        self.b_log.bind("<Button-1>", lambda e: self._toggle_log())
        self.log = tk.Text(bot, height=7, bg="#0a0c11", fg="#a8b0c4", relief="flat", bd=0, font=("Consolas", 9),
                           padx=8, pady=6, state="disabled", wrap="word")
        self._log_visible = False

    # ---------------------------------------------------------- actions
    def _paste(self):
        try:
            t = self.clipboard_get()
        except tk.TclError:
            return
        cur = self.txt.get("1.0", "end").strip()
        self.txt.insert("end", ("\n" if cur else "") + t.strip() + "\n")

    def _open_file(self):
        p = filedialog.askopenfilename(initialdir=str(HERE), title="Choose a text file with links",
                                       filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if p:
            self.txt.delete("1.0", "end")
            self.txt.insert("1.0", Path(p).read_text(encoding="utf-8", errors="ignore"))

    def _toggle_log(self):
        self._log_visible = not self._log_visible
        if self._log_visible:
            self.log.grid(row=1, column=0, sticky="ew", pady=(4, 0))
            self.b_log.configure(text="▾ Hide log")
        else:
            self.log.grid_remove()
            self.b_log.configure(text="▸ Show log")

    def _log(self, s):
        self.log.configure(state="normal")
        self.log.insert("end", s + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _open_local(self, name):
        p = HERE / name
        if p.exists():
            open_path(p)
        else:
            messagebox.showinfo("Not found", f"{name} doesn't exist yet.")

    def open_drive(self):
        if self.folder_id and self.folder_id != "demo":
            webbrowser.open(f"https://drive.google.com/drive/folders/{self.folder_id}")
        else:
            webbrowser.open("https://drive.google.com/drive/my-drive")

    def _copy(self, text, what):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.lbl_global.configure(text=f"Copied {what}", fg=GREEN)
        self.after(2500, lambda: self.lbl_global.configure(text="", fg=MUTED))

    def copy_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        it = self.items[int(sel[0])]
        if it.get("link"):
            self._copy(it["link"], "link")
        else:
            self.lbl_global.configure(text="No link for this row yet", fg=AMBER)

    def copy_all(self):
        links = [it["link"] for it in self.items if it.get("link")]
        if links:
            self._copy("\n".join(links), f"{len(links)} links")

    # ---------------------------------------------------------- run control
    def find(self):
        if self.running or self.finding:
            return
        try:
            n = max(1, min(200, int(self.v_count.get())))
        except Exception:
            n = 50
        self.cancel.clear()
        self.finding = True
        self.r_find.reset()
        self.lbl_title.configure(text="Finding videos…")
        self._pill("Searching", "#b48cff")
        for b in (self.b_start, self.b_find):
            b.configure(state="disabled", bg=CARD2, fg=MUTED)
        self.b_cancel.configure(state="normal")
        opts = {"count": n, "topics": self.topics.get().strip(), "cc_only": self.v_cc.get()}
        threading.Thread(target=run_find, args=(opts, self.q, self.cancel), daemon=True).start()

    def _find_done(self, urls, err):
        self.finding = False
        self.b_start.configure(state="normal", bg=ACCENT, fg="#0b1020")
        self.b_find.configure(state="normal", bg=ACCENT, fg="#0b1020")
        self.b_cancel.configure(state="disabled")
        if err or not urls:
            self.r_find.reset()
            self._pill("Idle", MUTED)
            self.lbl_title.configure(text=err or "No matching videos found — try other topics or untick Creative Commons")
            return
        self.r_find.finish(f"Found {len(urls)} videos")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", "\n".join(urls) + "\n")
        self.lbl_title.configure(text=f"Found {len(urls)} videos")
        self._pill("Ready", GREEN)
        if self.v_auto.get():
            self.after(600, self.start)

    def start(self):
        if self.running or self.finding:
            return
        urls = parse_urls(self.txt.get("1.0", "end"))
        if not urls:
            messagebox.showinfo("No links", "Paste at least one video link first.")
            return
        self.items = [{"url": u, "title": u, "status": "Queued", "link": "", "size": ""} for u in urls]
        self.frac = [0.0] * len(urls)
        self.tree.delete(*self.tree.get_children())
        for i, it in enumerate(self.items):
            self.tree.insert("", "end", iid=str(i), values=(i + 1, it["title"], "Queued", ""), tags=("queued",))
        self.cancel.clear()
        self.running = True
        self.t_start = time.time()
        self.b_start.configure(state="disabled", bg=CARD2, fg=MUTED)
        self.b_find.configure(state="disabled", bg=CARD2, fg=MUTED)
        self.b_cancel.configure(state="normal")
        self._pill("Running", ACCENT)
        self.lbl_count.configure(text=f"0 / {len(urls)}")
        self._overall()
        opts = {"reencode": self.v_re.get(), "keep": self.v_keep.get(), "skip_done": self.v_skip.get(),
                "caption": self.caption.get().strip()}
        fn = run_demo if DEMO else run_real
        self.worker = threading.Thread(target=fn, args=(urls, opts, self.q, self.cancel), daemon=True)
        self.worker.start()

    def stop(self):
        if self.running or self.finding:
            self.cancel.set()
            self.lbl_global.configure(text="Cancelling after the current step…", fg=AMBER)
            self.b_cancel.configure(state="disabled")

    def _on_close(self):
        if (self.running or self.finding) and not messagebox.askyesno("Quit", "A job is still running. Cancel it and quit?"):
            return
        self.cancel.set()
        self.destroy()
        os._exit(0)

    def _pill(self, text, color):
        self.pill.configure(text=f"  {text}  ", fg=color)

    # ---------------------------------------------------------- tree/overall helpers
    def _row(self, i, status=None, tag=None, title=None, size=None):
        it = self.items[i]
        if status is not None:
            it["status"] = status
        if title is not None:
            it["title"] = title
        if size is not None:
            it["size"] = size
        kw = {"values": (i + 1, it["title"], it["status"], it["size"])}
        if tag:
            kw["tags"] = (tag,)
        self.tree.item(str(i), **kw)

    def _overall(self):
        n = max(1, len(self.items))
        pct = sum(self.frac) / n * 100
        self.bar_all["value"] = pct
        self.lbl_all.configure(text=f"{pct:.0f}%")
        done = sum(1 for it in self.items if it["status"].startswith(("Done", "Skipped", "Failed", "Cancelled", "Link")))
        self.lbl_count.configure(text=f"{done} / {len(self.items)}")
        if self.running and pct > 3:
            el = time.time() - self.t_start
            eta = el / (pct / 100) - el
            self.lbl_all_info.configure(text=f"Elapsed {fmt_eta(el)}  ·  about {fmt_eta(eta)} left")

    def _reset_rows(self):
        for r in (self.r_dl, self.r_pr, self.r_ul):
            r.reset()

    # ---------------------------------------------------------- event loop
    def _poll(self):
        try:
            for _ in range(200):
                self._handle(self.q.get_nowait())
        except queue.Empty:
            pass
        self.after(50, self._poll)

    def _handle(self, ev):
        k = ev[0]
        if k == "log":
            self._log(ev[1])
        elif k == "find":
            self.r_find.set(ev[1], ev[2])
        elif k == "find_end":
            self._find_done(ev[1], ev[2])
        elif k == "global":
            self.lbl_global.configure(text=ev[1], fg=MUTED)
        elif k == "folder":
            self.folder_id = ev[1]
        elif k == "start":
            i, url = ev[1], ev[2]
            self._reset_rows()
            self.lbl_title.configure(text=url)
            self._row(i, "Downloading…", "active")
            self.tree.see(str(i))
            self.tree.selection_set(str(i))
        elif k == "title":
            i, t = ev[1], ev[2]
            self.lbl_title.configure(text=t)
            self._row(i, title=t)
        elif k == "dl":
            _, i, pct, speed, eta, done, tot = ev
            self.r_dl.set(pct, f"{fmt_bytes(done)} of {fmt_bytes(tot) if tot else '?'}   ·   {fmt_speed(speed)}   ·   {fmt_eta(eta)} left")
            self.frac[i] = W_DL * pct / 100
            self._row(i, f"Downloading… {pct:.0f}%", "active")
            self._overall()
        elif k == "stage":
            i, st = ev[1], ev[2]
            if st == "process":
                self.r_dl.finish("Download complete")
                self.r_pr.spin("Making it Instagram-safe (H.264 + AAC, fast-start)…")
                self.frac[i] = W_DL
                self._row(i, "Processing…", "warn")
            elif st == "upload":
                self.r_pr.finish("Ready to upload")
                self.frac[i] = W_DL + W_PROC
                self._row(i, "Uploading…", "active")
            elif st == "check":
                self.r_ul.finish("Upload complete")
                self.frac[i] = W_DL + W_PROC + W_UL
                self._row(i, "Checking link…", "warn")
            self._overall()
        elif k == "ul":
            _, i, pct, sent, tot, speed = ev
            self.r_ul.set(pct, f"{fmt_bytes(sent)} of {fmt_bytes(tot)}   ·   {fmt_speed(speed)}")
            self.frac[i] = W_DL + W_PROC + W_UL * pct / 100
            self._row(i, f"Uploading… {pct:.0f}%", "active")
            self._overall()
        elif k == "done_item":
            _, i, link, ok, size_mb = ev
            self.items[i]["link"] = link
            self.frac[i] = 1.0
            self.r_ul.finish("Upload complete")
            if ok:
                self._row(i, "Done ✓", "done", size=f"{size_mb:.1f} MB")
            else:
                self._row(i, "Link check failed — file may be too big for Drive", "warn", size=f"{size_mb:.1f} MB")
            self._overall()
        elif k == "skip":
            i, link = ev[1], ev[2]
            self.items[i]["link"] = link
            self.frac[i] = 1.0
            self._row(i, "Skipped (already uploaded)", "skip")
            self._overall()
        elif k == "fail":
            i, msg = ev[1], ev[2]
            self.frac[i] = 1.0
            self._row(i, f"Failed: {msg}", "fail")
            self.lbl_title.configure(text=self.items[i]["title"])
            self._log(f"FAILED {self.items[i]['url']}: {msg}")
            self._overall()
        elif k == "status":
            self._row(ev[1], ev[2], "skip")
            self._overall()
        elif k == "cancelled_rest":
            for j in range(ev[1], len(self.items)):
                if self.items[j]["status"] == "Queued":
                    self.frac[j] = 1.0
                    self._row(j, "Cancelled", "skip")
            self._overall()
        elif k == "fatal":
            self._finish(fatal=True)
            messagebox.showerror("Can't start", ev[1])
        elif k == "finished":
            self._finish()

    def _finish(self, fatal=False):
        self.running = False
        self.b_start.configure(state="normal", bg=ACCENT, fg="#0b1020")
        self.b_find.configure(state="normal", bg=ACCENT, fg="#0b1020")
        self.b_cancel.configure(state="disabled")
        self.r_pr.bar.stop()
        self.lbl_global.configure(text="" if fatal else self.lbl_global.cget("text"))
        n_ok = sum(1 for it in self.items if it["status"].startswith("Done"))
        n_skip = sum(1 for it in self.items if it["status"].startswith("Skipped"))
        n_fail = sum(1 for it in self.items if it["status"].startswith(("Failed", "Link")))
        if fatal:
            self._pill("Stopped", RED)
        elif self.cancel.is_set():
            self._pill("Cancelled", AMBER)
        else:
            self._pill("Finished", GREEN if not n_fail else AMBER)
            self.bar_all["value"] = 100
            self.lbl_all.configure(text="100%")
        el = time.time() - self.t_start
        self.lbl_all_info.configure(text=f"{n_ok} uploaded · {n_skip} skipped · {n_fail} failed  ·  took {fmt_eta(el)}")
        self.lbl_title.configure(text="All done — double-click a row to copy its link" if n_ok or n_skip else "Finished")
        if n_ok:
            self.copy_all()


if __name__ == "__main__":
    App().mainloop()
