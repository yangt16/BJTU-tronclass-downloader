"""update.py - 一键更新到 GitHub 最新 Release（不需要 git）。

保留这些数据，绝不覆盖：
    media/  lists/  har_archive/  logs/  python/  release/  tmp/  .git/  .menu.json

用法:
    python tools\\update.py             # 检查并更新
    python tools\\update.py --check     # 只看有没有新版
    python tools\\update.py --platform mac   # 强制平台（默认按当前系统）

测试用参数（正常用户不需要）：
    --root DIR      指定项目根目录
    --base-url URL  指定 GitHub 仓库地址
    --zip FILE      直接用本地 zip，不联网
"""
import argparse
import os
import pathlib
import re
import shutil
import sys
import urllib.error
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_BASE = "https://github.com/yangt16/BJTU-tronclass-downloader"
UA = "tronclass-downloader-updater"
# 这些顶层目录/文件属于用户数据，更新时跳过
KEEP_TOP = {"media", "lists", "har_archive", "logs", "python",
            "release", "tmp", ".git"}
KEEP_FILES = {".menu.json"}
# 先直连（或环境变量代理），失败再试本机常见代理端口（Clash）
PROXIES = ["", "http://127.0.0.1:7897"]

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def current_version(root):
    """从 CHANGELOG.md 读当前版本号，例如 'v4.2'。"""
    path = pathlib.Path(root) / "CHANGELOG.md"
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return "未知"
    m = re.search(r"^## (v\d+(?:\.\d+)*)", text, re.M)
    return m.group(1) if m else "未知"


def version_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or ""))


def is_newer(latest, current):
    """latest 是否比 current 新（远端可能仍是旧 Release）。"""
    a, b = version_tuple(latest), version_tuple(current)
    if not a:
        return False
    return a > b


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open(url, timeout=20, proxy=""):
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    else:
        handlers.append(urllib.request.ProxyHandler())
    handlers.append(_NoRedirect())
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return opener.open(req, timeout=timeout)


def latest_tag(base_url=DEFAULT_BASE, timeout=20):
    """取最新 Release 的 tag（v4.2）。不需要 API token，也不受 API 限流影响。"""
    url = base_url.rstrip("/") + "/releases/latest"
    errors = []
    for proxy in PROXIES:
        try:
            try:
                r = _open(url, timeout=timeout, proxy=proxy)
                final = r.geturl()
                r.close()
            except urllib.error.HTTPError as e:
                final = e.headers.get("Location", "") or ""
                e.close()
            m = re.search(r"/tag/(v\d+(?:\.\d+)*)", final)
            if m:
                return m.group(1)
            errors.append(f"{proxy or '直连'}: 跳转地址里没有 tag ({final[:80]})")
        except Exception as e:
            errors.append(f"{proxy or '直连'}: {e}")
    raise RuntimeError("连不上 GitHub（" + "；".join(errors) + "）")


def platform_name():
    return "win64" if os.name == "nt" else "mac"


def asset_url(base_url, tag, platform):
    name = f"tronclass-downloader-{tag}-{platform}.zip"
    return base_url.rstrip("/") + f"/releases/download/{tag}/{name}"


def download(url, dest, timeout=180):
    """下载到 dest（先直连/环境代理，失败再试本机 7897 代理）。"""
    errors = []
    for proxy in PROXIES:
        try:
            r = _open(url, timeout=timeout, proxy=proxy)
            dest = pathlib.Path(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as fh:
                shutil.copyfileobj(r, fh)
            r.close()
            if dest.stat().st_size <= 0:
                raise RuntimeError("下载到 0 字节")
            return dest
        except Exception as e:
            errors.append(f"{proxy or '直连'}: {e}")
    raise RuntimeError("下载失败（" + "；".join(errors) + "）")


def overlay(zip_path, root):
    """把 zip 里的程序文件覆盖到 root，跳过数据目录。

    返回 (新增文件数, 覆盖文件数)。
    """
    root = pathlib.Path(root)
    added = updated = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            if name.endswith("/"):
                continue
            parts = name.split("/", 1)
            if len(parts) < 2 or not parts[1]:
                continue          # 顶层目录本身
            rel = parts[1]
            if rel.split("/", 1)[0] in KEEP_TOP or rel in KEEP_FILES:
                continue
            dest = root / rel
            if dest.exists():
                updated += 1
            else:
                added += 1
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(dest, "wb") as fh:
                shutil.copyfileobj(src, fh)
            if os.name != "nt" and dest.suffix in (".sh", ".command"):
                try:
                    os.chmod(dest, 0o755)
                except Exception:
                    pass
    return added, updated


def main(argv=None):
    ap = argparse.ArgumentParser(description="更新到 GitHub 最新 Release（保留数据）")
    ap.add_argument("--check", action="store_true", help="只检查，不更新")
    ap.add_argument("--root", default="", help="项目根目录（默认自动）")
    ap.add_argument("--base-url", default=DEFAULT_BASE, help="GitHub 仓库地址")
    ap.add_argument("--zip", default="", help="用本地 zip 代替下载（测试用）")
    ap.add_argument("--platform", choices=["win64", "mac"], default="",
                    help="目标平台（默认按当前系统）")
    a = ap.parse_args(argv)

    root = pathlib.Path(a.root) if a.root else ROOT
    plat = a.platform or platform_name()
    cur = current_version(root)
    print(f"[update] 当前版本: {cur}")
    print(f"[update] 项目目录: {root}")

    try:
        if a.zip:
            tag, zip_path = "本地 zip", pathlib.Path(a.zip)
            print(f"[update] 使用本地包: {zip_path}")
        else:
            tag = latest_tag(a.base_url)
            print(f"[update] 最新版本: {tag}")
            if a.check:
                if is_newer(tag, cur):
                    print(f"[update] 有新版可更新: {cur} -> {tag}")
                else:
                    print("[update] 已是最新版本")
                return 0
            if not is_newer(tag, cur):
                print("[update] 已是最新版本，无需更新")
                return 0
            url = asset_url(a.base_url, tag, plat)
            print(f"[update] 下载: {url}")
            zip_path = pathlib.Path(root) / "tmp" / ".update_download.zip"
            download(url, zip_path)
            print(f"[update] 下载完成: {zip_path.stat().st_size/1e6:.1f} MB")
    except Exception as e:
        print(f"[update] 失败: {e}")
        print("[update] 如果连不上 GitHub：先启动代理/梯子再双击本文件；")
        print("[update] 或者手动下载最新 Release 的 zip 覆盖解压（数据目录不会丢）。")
        return 1

    if a.check:
        return 0

    try:
        added, updated = overlay(zip_path, root)
    except Exception as e:
        print(f"[update] 解压失败: {e}")
        return 1
    finally:
        if not a.zip:
            try:
                zip_path.unlink()
            except Exception:
                pass

    new = current_version(root)
    print(f"[update] 覆盖 {updated} 个文件，新增 {added} 个")
    print(f"[update] 完成: {cur} -> {new}")
    print("[update] 提示：")
    print("  Windows: 可直接双击 1-开始下载.cmd（无需重新首次安装）")
    print("  macOS/Linux: 若提示权限不足，运行 chmod +x *.command tools/*.sh")
    print("  如果书签导出的是纯 https 地址（没有 ENCODER 前缀），请重新导入 dist/bookmarks.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
