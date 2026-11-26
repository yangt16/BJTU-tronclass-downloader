"""验证 update.py：检查最新版 -> 下载 -> 覆盖，且数据目录不被覆盖。

用法: python tools/test_update.py

不联网：本地起一个假的 GitHub（releases/latest 302 -> /tag/v9.9，
下载地址返回准备好的 zip），再跑 tools/update.py --root/--base-url。
"""
import http.server
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import urllib.parse
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import update  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

bad = 0


def check(name, got, want):
    global bad
    ok = got == want
    print(f"[{'PASS' if ok else 'FAIL'}] {name:40s} got={got!r} want={want!r}")
    if not ok:
        bad += 1


BASE = ROOT / "tmp" / f"testupdate_{os.getpid()}"
shutil.rmtree(BASE, ignore_errors=True)
BASE.mkdir(parents=True)


def write(path, data, binary=False):
    p = BASE / path
    p.parent.mkdir(parents=True, exist_ok=True)
    if binary:
        p.write_bytes(data)
    else:
        p.write_text(data, encoding="utf-8")


# ---------- 旧版项目 ----------
write("CHANGELOG.md", "# 更新日志\n\n## v1.0 — 2026-01-01\n")
write("1-开始下载.cmd", "old-entry")
write("tools/menu.py", "old-menu")
write("media/keep.mp4", b"video-data", binary=True)
write("lists/keep.txt", "https://keep", binary=False)
write("har_archive/keep.txt", "archive", binary=False)
write("logs/keep.log", "log", binary=False)
write("python/python.exe", b"portable-python", binary=True)
write(".menu.json", '{"mode":"1"}')

# ---------- 假的新 Release zip ----------
ZIP = BASE / "new.zip"
with zipfile.ZipFile(ZIP, "w") as z:
    z.writestr("pkg/CHANGELOG.md", "# 更新日志\n\n## v9.9 — 2026-12-01\n")
    z.writestr("pkg/1-开始下载.cmd", "new-entry")
    z.writestr("pkg/tools/menu.py", "new-menu")
    z.writestr("pkg/tools/update_probe.py", "new-probe")
    # 这些必须被跳过（不能覆盖用户数据）
    z.writestr("pkg/media/evil.mp4", b"evil")
    z.writestr("pkg/lists/evil.txt", "evil")
    z.writestr("pkg/.menu.json", '{"mode":"2"}')
ZIP_BYTES = ZIP.read_bytes()

hits = {}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        hits[self.path] = hits.get(self.path, 0) + 1
        port = self.server.server_port
        if self.path == "/releases/latest":
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{port}/tag/v9.9")
            self.end_headers()
            return
        if self.path == "/tag/v9.9":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        if self.path.startswith("/releases/download/v9.9/"):
            self.send_response(200)
            self.send_header("Content-Length", str(len(ZIP_BYTES)))
            self.end_headers()
            self.wfile.write(ZIP_BYTES)
            return
        self.send_response(404)
        self.end_headers()


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
PORT = srv.server_port
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASEURL = f"http://127.0.0.1:{PORT}"


def run(*args):
    return subprocess.run(
        [sys.executable, str(HERE / "update.py"), "--root", str(BASE),
         "--base-url", BASEURL, "--platform", "win64"] + list(args),
        capture_output=True, text=True, encoding="utf-8", errors="replace")


try:
    # ---------- 单元函数 ----------
    check("读当前版本", update.current_version(BASE), "v1.0")
    check("平台参数拼 URL", update.asset_url(BASEURL, "v3.2", "win64"),
          f"{BASEURL}/releases/download/v3.2/tronclass-downloader-v3.2-win64.zip")

    check("版本比较: 新版", update.is_newer("v9.9", "v1.0"), True)
    check("版本比较: 旧于本地", update.is_newer("v4.0", "v4.2"), False)
    check("版本比较: 同一版", update.is_newer("v4.2", "v4.2"), False)

    # ---------- --check 不写文件 ----------
    r = run("--check")
    check("--check 退出码", r.returncode, 0)
    check("--check 报告有新版", "v1.0 -> v9.9" in r.stdout, True)
    check("--check 不改 CHANGELOG",
          (BASE / "CHANGELOG.md").read_text(encoding="utf-8").count("v9.9"), 0)

    # ---------- 真正更新 ----------
    r = run()
    check("更新退出码", r.returncode, 0)
    check("报告版本变化", "完成: v1.0 -> v9.9" in r.stdout, True)
    check("CHANGELOG 已更新",
          "v9.9" in (BASE / "CHANGELOG.md").read_text(encoding="utf-8"), True)
    check("程序文件已覆盖",
          (BASE / "1-开始下载.cmd").read_text(encoding="utf-8"), "new-entry")
    check("新增文件写入",
          (BASE / "tools/update_probe.py").read_text(encoding="utf-8"), "new-probe")

    # ---------- 数据目录必须原样保留 ----------
    check("media 保留", (BASE / "media/keep.mp4").read_bytes(), b"video-data")
    check("lists 保留",
          (BASE / "lists/keep.txt").read_text(encoding="utf-8"), "https://keep")
    check("har_archive 保留",
          (BASE / "har_archive/keep.txt").read_text(encoding="utf-8"), "archive")
    check("python 目录保留",
          (BASE / "python/python.exe").read_bytes(), b"portable-python")
    check("菜单记忆保留",
          (BASE / ".menu.json").read_text(encoding="utf-8"), '{"mode":"1"}')
    check("没写入 media/evil", (BASE / "media/evil.mp4").exists(), False)
    check("没写入 lists/evil", (BASE / "lists/evil.txt").exists(), False)

    # ---------- 已是最新时不下载 ----------
    def downloads():
        return sum(v for k, v in hits.items() if k.startswith("/releases/download/"))

    before = downloads()
    r = run()
    check("已最新退出码", r.returncode, 0)
    check("已最新提示", "已是最新版本" in r.stdout, True)
    check("已最新不下载", downloads(), before)
finally:
    srv.shutdown()
    shutil.rmtree(BASE, ignore_errors=True)

print()
print("全部通过" if bad == 0 else f"{bad} 项失败")
sys.exit(0 if bad == 0 else 1)
