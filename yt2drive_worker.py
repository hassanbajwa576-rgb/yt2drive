#!/usr/bin/env python3
"""
YT -> Drive worker (runs on YOUR PC).

The web panel on Vercel only sends commands (find / start / cancel). This worker polls it,
does the real work with the same engine as the desktop app (search, download, convert, upload
to your Google Drive) and posts live progress back so the web page can show the bars.

Setup: worker_config.json next to this file:   {"url": "https://YOUR-PANEL.vercel.app", "key": "WORKER_KEY",
                                 "scheduler": {"url": "https://universalscheduler.vercel.app", "key": "SCHEDULER_API_KEY"}}
Run:   double-click RUN_WORKER.bat
"""
import json
import os
import queue
import sys
import threading
import datetime as dt
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.argv = [sys.argv[0]]  # the app module reads launch flags from argv; keep it clean

import yt2drive_app as A  # noqa: E402  (engine: run_find / run_real / helpers)

CFG_FILE = HERE / "worker_config.json"


def load_cfg():
    if not CFG_FILE.exists():
        raise SystemExit(f"Missing {CFG_FILE.name}. Create it with: "
                         '{"url": "https://YOUR-PANEL.vercel.app", "key": "WORKER_KEY"}')
    cfg = json.loads(CFG_FILE.read_text(encoding="utf-8"))
    cfg["url"] = cfg["url"].rstrip("/")
    return cfg


class Panel:
    def __init__(self, cfg):
        self.url, self.key = cfg["url"], cfg["key"]

    def _req(self, method, body=None):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(f"{self.url}/api/worker", data=data, method=method, headers={
            "x-worker-key": self.key, "Content-Type": "application/json", "User-Agent": "yt2drive-worker/1"})
        with urllib.request.urlopen(r, timeout=25) as resp:
            return json.loads(resp.read().decode() or "{}")

    def commands(self):
        return self._req("GET").get("commands", [])

    def push(self, state):
        self._req("POST", state)


from sched_lib import schedule_items  # noqa: E402  (shared captions + scheduling)


class Worker:
    def __init__(self, panel, scfg=None):
        self.panel = panel
        self.scfg = scfg
        self.schedule = None
        self.q = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.job_opts = {}
        self.items, self.frac = [], []
        self.t_start = 0
        self.found_id = 0
        self.s = self._blank()
        self.dirty = True
        sys.stdout = A.QWriter(self.q)
        sys.stderr = A.QWriter(self.q)

    # ------------------------------------------------------------ state
    @staticmethod
    def _blank():
        return {"phase": "idle", "pill": "Idle", "title": "Nothing running", "count": "",
                "find": None, "dl": None, "pr": None, "ul": None, "overall": {"pct": 0, "info": ""},
                "items": [], "log": [], "found": [], "foundId": 0}

    def _row(self, i, status=None, tag=None, title=None, size=None):
        it = self.items[i]
        if status is not None:
            it["status"] = status
        if tag is not None:
            it["tag"] = tag
        if title is not None:
            it["title"] = title
        if size is not None:
            it["size"] = size

    def _overall(self):
        n = max(1, len(self.items))
        pct = sum(self.frac) / n * 100
        done = sum(1 for it in self.items if it["status"].startswith(("Done", "Skipped", "Failed", "Cancelled", "Link")))
        self.s["count"] = f"{done} / {len(self.items)}" if self.items else ""
        info = ""
        if self.busy and self.s["phase"] == "running" and pct > 3:
            el = time.time() - self.t_start
            info = f"Elapsed {A.fmt_eta(el)}  ·  about {A.fmt_eta(el / (pct / 100) - el)} left"
        self.s["overall"] = {"pct": pct, "info": info}

    def _reset_steps(self):
        self.s["dl"] = self.s["pr"] = self.s["ul"] = None

    # ------------------------------------------------------------ events (mirror of the desktop app)
    def handle(self, ev):
        k, s = ev[0], self.s
        self.dirty = True
        if k == "log":
            s["log"] = (s["log"] + [ev[1]])[-60:]
        elif k == "global":
            pass
        elif k == "sched":
            s["title"] = ev[1]
            s["log"] = (s["log"] + [ev[1]])[-60:]
        elif k == "folder":
            s["folder"] = ev[1]
        elif k == "find":
            s["find"] = {"pct": ev[1], "info": ev[2]}
        elif k == "find_end":
            urls, err = ev[1], ev[2]
            if err or not urls:
                s.update(find=None, phase="idle", pill="Idle",
                         title=err or "No matching videos found. Try other topics or untick Creative Commons.")
                self.busy = False
            else:
                self.found_id += 1
                s.update(find={"pct": 100, "info": f"Found {len(urls)} videos"}, found=urls, foundId=self.found_id,
                         title=f"Found {len(urls)} videos", pill="Ready")
                if self.auto_after_find:
                    self.start_job(urls, self.job_opts)
                else:
                    s["phase"] = "idle"
                    self.busy = False
        elif k == "start":
            i, url = ev[1], ev[2]
            self._reset_steps()
            s["title"] = url
            self._row(i, "Downloading…", "active")
        elif k == "title":
            s["title"] = ev[2]
            self._row(ev[1], title=ev[2])
        elif k == "dl":
            _, i, pct, speed, eta, done, tot = ev
            s["dl"] = {"pct": pct, "info": f"{A.fmt_bytes(done)} of {A.fmt_bytes(tot) if tot else '?'}  ·  {A.fmt_speed(speed)}  ·  {A.fmt_eta(eta)} left"}
            self.frac[i] = A.W_DL * pct / 100
            self._row(i, f"Downloading… {pct:.0f}%", "active")
            self._overall()
        elif k == "stage":
            i, st = ev[1], ev[2]
            if st == "process":
                s["dl"] = {"pct": 100, "info": "Download complete"}
                s["pr"] = {"pct": 50, "spin": True, "info": "Making it Instagram-safe (H.264 + AAC, fast-start)…"}
                self.frac[i] = A.W_DL
                self._row(i, "Processing…", "warn")
            elif st == "upload":
                s["pr"] = {"pct": 100, "info": "Ready to upload"}
                self.frac[i] = A.W_DL + A.W_PROC
                self._row(i, "Uploading…", "active")
            elif st == "check":
                s["ul"] = {"pct": 100, "info": "Upload complete"}
                self.frac[i] = A.W_DL + A.W_PROC + A.W_UL
                self._row(i, "Checking link…", "warn")
            self._overall()
        elif k == "ul":
            _, i, pct, sent, tot, speed = ev
            s["ul"] = {"pct": pct, "info": f"{A.fmt_bytes(sent)} of {A.fmt_bytes(tot)}  ·  {A.fmt_speed(speed)}"}
            self.frac[i] = A.W_DL + A.W_PROC + A.W_UL * pct / 100
            self._row(i, f"Uploading… {pct:.0f}%", "active")
            self._overall()
        elif k == "done_item":
            _, i, link, ok, size_mb = ev
            self.items[i]["link"] = link
            self.frac[i] = 1.0
            s["ul"] = {"pct": 100, "info": "Upload complete"}
            if ok:
                self._row(i, "Done ✓", "done", size=f"{size_mb:.1f} MB")
            else:
                self._row(i, "Link check failed. The file may be too big for Drive.", "warn", size=f"{size_mb:.1f} MB")
            self._overall()
        elif k == "skip":
            self.items[ev[1]]["link"] = ev[2]
            self.frac[ev[1]] = 1.0
            self._row(ev[1], "Skipped (already uploaded)", "skip")
            self._overall()
        elif k == "fail":
            self.frac[ev[1]] = 1.0
            self._row(ev[1], f"Failed: {ev[2]}", "fail")
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
            s.update(phase="idle", pill="Stopped", title=ev[1].split("\n")[0][:200])
            self.busy = False
        elif k == "finished":
            ok = sum(1 for it in self.items if it["status"].startswith("Done"))
            skip = sum(1 for it in self.items if it["status"].startswith("Skipped"))
            fail = sum(1 for it in self.items if it["status"].startswith(("Failed", "Link")))
            s.update(phase="idle", pill="Cancelled" if self.cancel.is_set() else "Finished",
                     title=f"{ok} uploaded · {skip} skipped · {fail} failed")
            if not self.cancel.is_set():
                s["overall"] = {"pct": 100, "info": f"took {A.fmt_eta(time.time() - self.t_start)}"}
            self.busy = False
            sc = self.schedule
            if sc and sc.get("enabled") and ok and not self.cancel.is_set():
                s["title"] += "  ·  scheduling…"
                items = [dict(i) for i in self.items]
                threading.Thread(target=self._schedule_thread, args=(items, sc), daemon=True).start()

    def _schedule_thread(self, items, sc):
        try:
            schedule_items(items, sc, self.scfg, lambda m: self.q.put(("sched", m)))
        except Exception as e:
            self.q.put(("sched", f"Scheduling failed: {e}"))

    # ------------------------------------------------------------ jobs
    auto_after_find = False

    def start_job(self, urls, opts):
        urls = A.parse_urls("\n".join(urls))
        self.items = [{"url": u, "title": u, "status": "Queued", "tag": "queued", "link": "", "size": ""} for u in urls]
        self.frac = [0.0] * len(urls)
        self.s.update(items=self.items, phase="running", pill="Running", title="Starting…")
        self._reset_steps()
        self.s["overall"] = {"pct": 0, "info": ""}
        self.t_start = time.time()
        self.cancel.clear()
        self.busy = True
        self.job_opts = opts
        self.dirty = True
        o = {"reencode": opts.get("reencode", False), "keep": opts.get("keep", False),
             "skip_done": opts.get("skip_done", True), "caption": opts.get("caption", "")}
        threading.Thread(target=A.run_real, args=(urls, o, self.q, self.cancel), daemon=True).start()

    def start_find(self, c):
        self.items, self.frac = [], []
        self.s.update(items=[], phase="finding", pill="Searching", title="Finding videos…", find={"pct": 1, "info": "Starting…"})
        self._reset_steps()
        self.s["overall"] = {"pct": 0, "info": ""}
        self.cancel.clear()
        self.busy = True
        self.auto_after_find = bool(c.get("auto"))
        self.job_opts = c.get("opts", {})
        self.dirty = True
        o = {"count": int(c.get("count", 50)), "topics": c.get("topics", ""), "cc_only": bool(c.get("cc_only", True))}
        threading.Thread(target=A.run_find, args=(o, self.q, self.cancel), daemon=True).start()

    def command(self, c):
        t = c.get("type")
        if t == "cancel":
            self.cancel.set()
            self.s["title"] = "Cancelling after the current step…"
            self.dirty = True
        elif self.busy:
            return  # ignore a new job while one is running
        elif t == "find":
            self.schedule = c.get("schedule")
            self.start_find(c)
        elif t == "start":
            self.schedule = c.get("schedule")
            self.start_job(c.get("urls", []), c.get("opts", {}))

    # ------------------------------------------------------------ main loop
    def run(self):
        print("Worker running. Leave this window/app open.", file=sys.__stdout__) if sys.__stdout__ else None
        last_poll = last_push = 0
        while True:
            try:
                while True:
                    self.handle(self.q.get_nowait())
            except queue.Empty:
                pass
            now = time.time()
            try:
                if now - last_poll >= (2 if self.busy else 3):
                    last_poll = now
                    for c in self.panel.commands():
                        self.command(c)
                if (self.dirty and now - last_push >= 1.5) or now - last_push >= 10:
                    last_push = now
                    self.dirty = False
                    self.panel.push(self.s)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                self.s["log"] = (self.s["log"] + [f"Panel unreachable: {e}"])[-60:]
                time.sleep(5)
            except Exception as e:
                self.s["log"] = (self.s["log"] + [f"Worker error: {e}"])[-60:]
                time.sleep(3)
            time.sleep(0.4)


if __name__ == "__main__":
    _cfg = load_cfg()
    Worker(Panel(_cfg), _cfg.get("scheduler")).run()
