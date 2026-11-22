"""验证「清单带轨名」与「只解析要用的轨」（A+B 优化）。

用法: python tools/test_tracks.py

不联网：本地起一个会 302 的假 incast（previewToken -> 直链），
统计到底发了几次解析请求、是否并发、分组是否正确。
"""
import http.server
import os
import pathlib
import shutil
import sys
import threading
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import batch  # noqa: E402
import lectures  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

bad = 0


def check(name, got, want):
    global bad
    ok = got == want
    print(f"[{'PASS' if ok else 'FAIL'}] {name:36s} got={got!r} want={want!r}")
    if not ok:
        bad += 1


BASE = ROOT / "tmp" / f"testtracks_{os.getpid()}"
shutil.rmtree(BASE, ignore_errors=True)
BASE.mkdir(parents=True)

hits = []
barrier = threading.Barrier(2)
parallel = {"ok": False}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if "/captures/" in self.path and "previewToken=" in self.path:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            token = q.get("previewToken", [""])[0]
            hits.append(token)
            # 两节并行解析时才能同时到达 barrier
            try:
                barrier.wait(timeout=5)
                parallel["ok"] = True
            except threading.BrokenBarrierError:
                pass
            date, span, track = token.split("_")
            loc = (f"http://127.0.0.1:{PORT}/videos/o/site/{date}/{span}/"
                   f"{track}-abc?ts=1&token=x")
            self.send_response(302)
            self.send_header("Location", loc)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
PORT = srv.server_port
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASEURL = f"http://127.0.0.1:{PORT}"

try:
    # ---------- 1) 清单格式：TRACK 前缀 ----------
    LST = BASE / "T课.txt"
    LST.write_text(
        f"# 测试清单\n"
        f"ENCODER {BASEURL}/captures/aaa/videos/1/preview?previewToken=20261029_080000-095500_ENCODER\n"
        f"STUDENTS {BASEURL}/captures/aaa/videos/2/preview?previewToken=20261029_080000-095500_STUDENTS\n"
        f"INSTRUCTOR {BASEURL}/captures/aaa/videos/3/preview?previewToken=20261029_080000-095500_INSTRUCTOR\n"
        f"STUDENTS {BASEURL}/captures/bbb/videos/1/preview?previewToken=20261105_100000-120000_STUDENTS\n"
        f"INSTRUCTOR {BASEURL}/captures/bbb/videos/2/preview?previewToken=20261105_100000-120000_INSTRUCTOR\n",
        encoding="utf-8")
    entries = lectures.load_urls(LST)
    check("读到 5 条", len(entries), 5)
    check("轨名解析", [e["track"] for e in entries],
          ["ENCODER", "STUDENTS", "INSTRUCTOR", "STUDENTS", "INSTRUCTOR"])

    # ---------- 2) 只解析要用的轨 ----------
    CACHE = BASE / "resolve-cache.json"
    lectures.resolve_entries(entries, cache_path=CACHE)
    check("只发了 2 次解析请求", len(hits), 2)
    check("两次解析是并发的", parallel["ok"], True)
    check("ENCODER 优先被解析",
          any(t.endswith("_ENCODER") for t in hits), True)

    # ---------- 2b) 缓存命中：第二次零请求 ----------
    cache = lectures.load_resolve_cache(CACHE)
    check("缓存写入 2 节", len(cache), 2)
    entries2 = lectures.load_urls(LST)
    before = len(hits)
    lectures.resolve_entries(entries2, cache_path=CACHE)
    check("缓存命中不发请求", len(hits), before)
    labels2 = {e["label"] for e in entries2}
    check("缓存命中也有标签", labels2,
          {"20261029_080000-095500", "20261105_100000-120000"})
    bad_cache = BASE / "bad-cache.json"
    bad_cache.write_text('{"h1": "not-a-label", "h2": 123}', encoding="utf-8")
    check("坏缓存行被忽略", lectures.load_resolve_cache(bad_cache), {})

    # 缓存命中后：已下载的节离线跳过（零请求）
    out2 = BASE / "out2"
    for d in ("20261029", "20261105"):
        (out2 / d).mkdir(parents=True)
    for f in ("out2_20261029.mp4", "out2_20261105.mp4"):
        d = f.split("_")[1].split(".")[0]
        (out2 / d / f).write_bytes(b"x")
    groups2 = lectures.group_by_label(entries2)
    before = len(hits)
    todo2, skipped2, _ = lectures.plan_sections(
        groups2, out2, "video", "ENCODER")
    check("已下载的节直接跳过", (len(todo2), len(skipped2)), (0, 2))
    check("跳过过程零解析请求", len(hits), before)
    # 真要下时才解析一条新鲜直链
    lectures.ensure_real(entries2[0])
    check("下载前才解析直链", len(hits), before + 1)
    groups = lectures.group_by_label(entries)
    check("分成 2 节", sorted(groups), ["20261029_080000-095500",
                                        "20261105_100000-120000"])
    a = groups["20261029_080000-095500"]
    check("同节三条轨都在一组", len(a), 3)
    check("同节共享标签", {e["label"] for e in a}, {"20261029_080000-095500"})
    check("只解析了要用的轨", (bool(a[0].get("real")), bool(a[1].get("real"))),
          (True, False))

    # ---------- 3) 预扫描：默认选 ENCODER；没 ENCODER 退而用第一条 ----------
    todo, skipped, archived = lectures.plan_sections(
        groups, BASE / "out", "both", "ENCODER", dry_run=True)
    picks = {j["label"]: lectures.entry_track(j["pick"]) for j in todo}
    check("有 ENCODER 用 ENCODER", picks["20261029_080000-095500"], "ENCODER")
    check("没 ENCODER 用第一条", picks["20261105_100000-120000"], "STUDENTS")

    # ---------- 4) 旧格式（不带轨名）：按 hash 每节只解析一条 ----------
    hits.clear()
    barrier.reset()
    parallel["ok"] = False
    OLD = BASE / "O课.txt"
    OLD.write_text(
        f"{BASEURL}/captures/ccc/videos/1/preview?previewToken=20261029_080000-095500_ENCODER\n"
        f"{BASEURL}/captures/ccc/videos/2/preview?previewToken=20261029_080000-095500_STUDENTS\n"
        f"{BASEURL}/captures/ccc/videos/3/preview?previewToken=20261029_080000-095500_INSTRUCTOR\n",
        encoding="utf-8")
    old_entries = lectures.load_urls(OLD)
    check("旧格式也能读", len(old_entries), 3)
    lectures.resolve_entries(old_entries, cache_path=BASE / "old-cache.json")
    check("旧格式也只解析 1 次", len(hits), 1)
    old_groups = lectures.group_by_label(old_entries)
    check("旧格式分组正常", len(old_groups), 1)
    check("旧格式解出 ENCODER 轨",
          lectures.entry_track(old_groups["20261029_080000-095500"][0]),
          "ENCODER")

    # ---------- 5) batch 节数估算：带轨名前缀 ----------
    check("节数估算（带前缀）", batch.count_sections(LST), 2)
    check("节数估算（旧格式）", batch.count_sections(OLD), 1)
finally:
    srv.shutdown()
    shutil.rmtree(BASE, ignore_errors=True)

print()
print("全部通过" if bad == 0 else f"{bad} 项失败")
sys.exit(0 if bad == 0 else 1)
