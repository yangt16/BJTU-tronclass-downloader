"""并发下载路径的自动化测试（本地 HTTP 服务器 + 在进程内跑 lectures.main）。

验证：
  * --jobs 3 真的同时发起请求（服务器用 Barrier 证明 ≥3 个并发）
  * 3 节都完整落盘、字节一致
  * 并发模式有每节进度行、有小节报告
  * 第二次运行走预扫描跳过，不再发请求

不依赖 ffmpeg：把 lectures.check_media / notify_done 换成打桩实现。
"""
import contextlib
import http.server
import io
import os
import pathlib
import re
import shutil
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import lectures  # noqa: E402
import ledger  # noqa: E402

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


DATA = (b"concurrent-test-" * 65536)[:1024 * 1024]
BARRIER_N = 3
state = {"active": 0, "max": 0, "requests": 0, "lock": threading.Lock()}
barrier = threading.Barrier(BARRIER_N)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        with state["lock"]:
            state["active"] += 1
            state["max"] = max(state["max"], state["active"])
            state["requests"] += 1
        try:
            barrier.wait(timeout=3)
        except threading.BrokenBarrierError:
            pass
        try:
            rng = self.headers.get("Range")
            m = re.match(r"bytes=(\d+)-(\d*)", rng or "")
            start = int(m.group(1)) if m else 0
            end = min((int(m.group(2)) if m and m.group(2) else len(DATA) - 1),
                      len(DATA) - 1)
            body = DATA[start:end + 1]
            self.send_response(206 if rng else 200)
            if rng:
                self.send_header("Content-Range",
                                 f"bytes {start}-{end}/{len(DATA)}")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        finally:
            with state["lock"]:
                state["active"] -= 1


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = ROOT / "tmp" / f"testconc_{os.getpid()}"
shutil.rmtree(BASE, ignore_errors=True)
BASE.mkdir(parents=True)
LIST = BASE / "并发测试.txt"
URL = f"http://127.0.0.1:{srv.server_port}/videos/outbound1/bjtu/room1"
items = [("20261030", "101000-120500-1"), ("20261104", "080000-095500-1"),
         ("20261106", "162000-181500-1")]
LIST.write_text("".join(f"{URL}/{d}/{s}/ENCODER-a?ts=1&token=x\n" for d, s in items),
                encoding="utf-8")
DEST = BASE / "out"

# 打桩：跳过 ffprobe 校验和响铃；启动检查也指向已存在的 python 可执行文件
# （CI 的 Linux/Windows runner 上没有 ffmpeg/ffprobe）
lectures.FFMPEG = pathlib.Path(sys.executable)
lectures.FFPROBE = pathlib.Path(sys.executable)
ledger.LEDGER_PATH = BASE / "downloaded.jsonl"   # 台账写到临时目录
lectures.check_media = lambda path, probe=None: (True, "打桩")
lectures.notify_done = lambda: None
# --keep-list 分支会调 make_index；打桩避免往真实 lists\ 写 out.md
import make_index  # noqa: E402
make_index.rebuild = lambda outdir: None


def run_main():
    old_argv = sys.argv
    sys.argv = ["lectures.py", "--urls", str(LIST), "--dest", str(DEST),
                "--no-audio", "--jobs", "3", "--keep-list"]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = lectures.main()
    finally:
        sys.argv = old_argv
    return rc, buf.getvalue()


try:
    rc1, out1 = run_main()
    files = sorted(DEST.rglob("*.mp4"))
    check("第一次运行成功", rc1, 0)
    check("下载了 3 节", len(files), 3)
    check("文件字节一致", all(f.read_bytes() == DATA for f in files), True)
    check("并发路数日志", "[jobs] 并发 3 路" in out1, True)
    check("服务器见证 ≥3 并发", state["max"] >= 3, True)
    progress_lines = re.findall(r"\[\d+/3\] \S+ +\d+%", out1)
    check("有每节进度行", len(progress_lines) >= 1, True)
    check("有下载报告", "[报告]" in out1 and "平均" in out1, True)

    requests_after_first = state["requests"]
    # 第二轮：预扫描应全部跳过（不再发请求）
    barrier.abort()
    rc2, out2 = run_main()
    check("第二次运行成功", rc2, 0)
    check("跳过已下载", "[skip] 已下载 3 节" in out2, True)
    check("第二轮零请求", state["requests"], requests_after_first)
finally:
    srv.shutdown()
    shutil.rmtree(BASE, ignore_errors=True)

print()
print("全部通过" if bad == 0 else f"{bad} 项失败")
sys.exit(0 if bad == 0 else 1)
