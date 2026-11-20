"""get_media 的集成测试：起一个本地假 HTTP 服务器，验证下载核心链路。

覆盖的是"没有真实网络也应该对"的部分：
  * 完整下载，字节与服务器一致
  * 断点续传：已有半个文件时只请求剩余部分
  * 服务器 500 时自动重试并最终成功
  * 服务器忽略 Range 时给出明确错误（而不是静默写坏文件）
  * 403 时 probe/download 给出可读错误
  * resolve() 能读出 302 的 Location

不联网，Windows / macOS / Linux 都能跑。

用法: python tools/test_download.py
"""
import http.server
import json
import pathlib
import re
import shutil
import sys
import threading
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from get_media import download, probe, resolve  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 3 MB + 17 字节：非整数块，能顺带暴露切片边界错误
DATA = (b"0123456789abcdef" * 196609)[:3 * 1024 * 1024 + 17]

bad = 0


def check(name, ok, detail=""):
    global bad
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        bad += 1


class Handler(http.server.BaseHTTPRequestHandler):
    ranges = {}
    flaky_left = 1

    def log_message(self, *a):
        pass

    def _range(self):
        h = self.headers.get("Range")
        if not h:
            return None
        m = re.match(r"bytes=(\d+)-(\d*)", h)
        if not m:
            return None
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else len(DATA) - 1
        return start, min(end, len(DATA) - 1)

    def _send_full(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(DATA)))
        self.end_headers()
        self.wfile.write(DATA)

    def _send_slice(self, start, end):
        body = DATA[start:end + 1]
        self.send_response(206)
        self.send_header("Content-Range", f"bytes {start}-{end}/{len(DATA)}")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        rng = self._range()
        Handler.ranges.setdefault(path, []).append(self.headers.get("Range"))

        if path == "/forbidden":
            self.send_error(403)
            return

        if path == "/preview":
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/media.bin")
            self.end_headers()
            return

        if path == "/norange.bin":
            # 完全不看 Range，永远返回 200 全量
            self._send_full()
            return

        if path == "/flaky.bin" and rng != (0, 0):
            # 只让"分块请求"失败，probe（bytes=0-0）正常
            if Handler.flaky_left > 0:
                Handler.flaky_left -= 1
                self.send_error(500)
                return

        if rng is None:
            self._send_full()
        else:
            self._send_slice(*rng)


class Server:
    def __enter__(self):
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        return False

    def url(self, path):
        return f"http://127.0.0.1:{self.httpd.server_port}{path}"


BASE = ROOT / "tmp" / f"testdl_{__import__('os').getpid()}"
shutil.rmtree(BASE, ignore_errors=True)
BASE.mkdir(parents=True, exist_ok=True)

try:
    with Server() as srv:
        handler = srv

        # ---------- 1. probe ----------
        ok, total, err = probe(handler.url("/media.bin"))
        check("probe 成功且拿到长度", ok and total == len(DATA), f"{ok} {total} {err}")

        # ---------- 2. 完整下载 ----------
        out = BASE / "full.bin"
        download(handler.url("/media.bin"), out)
        check("完整下载字节一致", out.read_bytes() == DATA,
              f"{out.stat().st_size} vs {len(DATA)}")

        # ---------- 3. 断点续传 ----------
        half = BASE / "half.bin"
        cut = 1024 * 1024
        half.write_bytes(DATA[:cut])
        Handler.ranges["/media.bin"] = []
        download(handler.url("/media.bin"), half)
        check("续传后字节一致", half.read_bytes() == DATA)
        resent = Handler.ranges["/media.bin"]
        check("续传从断点开始请求",
              any(r and r.startswith(f"bytes={cut}-") for r in resent), resent[:3])

        # ---------- 4. 服务器 500 自动重试 ----------
        flaky = BASE / "flaky.bin"
        Handler.flaky_left = 1
        try:
            download(handler.url("/flaky.bin"), flaky)
            check("500 后重试成功", flaky.read_bytes() == DATA)
        except Exception as e:
            check("500 后重试成功", False, f"{type(e).__name__}: {e}")
        attempts = len(Handler.ranges.get("/flaky.bin", []))
        check("确实重试过（请求数 > 2）", attempts > 2, attempts)

        # ---------- 5. 服务器忽略 Range -> 明确报错 ----------
        try:
            download(handler.url("/norange.bin"), BASE / "norange.bin")
            check("忽略 Range 时报错", False, "居然成功了")
        except RuntimeError as e:
            check("忽略 Range 时报错", "长度" in str(e), str(e))

        # ---------- 6. 403 ----------
        ok, total, err = probe(handler.url("/forbidden"))
        check("403 时 probe 失败并说明原因", (not ok) and "403" in err, err)
        try:
            download(handler.url("/forbidden"), BASE / "forbidden.bin")
            check("403 时 download 报错", False, "居然成功了")
        except RuntimeError as e:
            check("403 时 download 报错", "403" in str(e), str(e))

        # ---------- 7. resolve 读 302 ----------
        preview = handler.url("/preview?previewToken=abc")
        got = resolve(preview)
        check("resolve 取到 Location", got == handler.url("/media.bin"), got)
        via = BASE / "via_redirect.bin"
        download(got, via)
        check("经 302 拿到的地址可下载", via.read_bytes() == DATA)

        # ---------- 8. 已是直链时 resolve 原样返回 ----------
        plain = handler.url("/media.bin")
        check("resolve 不动直链", resolve(plain) == plain)

        # ---------- 9. 单文件多连接分段下载 ----------
        seg = BASE / "seg.bin"
        download(handler.url("/media.bin"), seg, segments=4)
        check("分段下载字节一致", seg.read_bytes() == DATA)
        check("分段状态文件已清理", not (BASE / "seg.bin.segstate").exists())

        # 断点：第 1 段已下一半，状态文件记录进度
        seg2 = BASE / "seg2.bin"
        total = len(DATA)
        n = 4
        per = (total + n - 1) // n
        half = per // 2
        buf = bytearray(total)
        buf[:half] = DATA[:half]
        seg2.write_bytes(bytes(buf))
        (BASE / "seg2.bin.segstate").write_text(
            json.dumps({"total": total, "n": n, "done": [half, 0, 0, 0]}),
            encoding="utf-8")
        download(handler.url("/media.bin"), seg2, segments=4)
        check("分段续传字节一致", seg2.read_bytes() == DATA)
        check("续传后状态文件已清理", not (BASE / "seg2.bin.segstate").exists())

        # 不整除：3 MB 拆 7 段
        seg3 = BASE / "seg3.bin"
        download(handler.url("/media.bin"), seg3, segments=7)
        check("分段不整除字节一致", seg3.read_bytes() == DATA)

        # ---------- 10. 进度回调 ----------
        seen = []
        out_cb = BASE / "cb.bin"
        download(handler.url("/media.bin"), out_cb,
                 progress_cb=lambda d, t: seen.append((d, t)))
        check("普通下载回调到总长", bool(seen) and seen[-1][0] == len(DATA),
              seen[-1] if seen else None)
        check("回调进度单调",
              all(b >= a for (a, _), (b, _) in zip(seen, seen[1:])), True)
        seen2 = []
        out_cb2 = BASE / "cb2.bin"
        download(handler.url("/media.bin"), out_cb2, segments=4,
                 progress_cb=lambda d, t: seen2.append((d, t)))
        check("分段下载回调到总长",
              bool(seen2) and seen2[-1][0] == len(DATA),
              seen2[-1] if seen2 else None)
finally:
    shutil.rmtree(BASE, ignore_errors=True)

print()
print("全部通过" if bad == 0 else f"{bad} 项失败")
sys.exit(0 if bad == 0 else 1)
