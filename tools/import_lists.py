r"""
import_lists.py - 把抓取清单收编进 lists\\，用户不用手动复制。

收编三类来源：
  1. 下载文件夹 / 桌面里的抓取 txt（scrape_course.js 导出，含 previewToken）
  2. lists\\ 里形如 "课程名 (1).txt" 的副本
     （手动复制到 lists 时 Windows 会问是否替换；选"保留两份"就会产生这个）
  3. 同名清单按 URL 去重合并 —— 老地址不会丢，新地址追加在后

抓取导出的清单本身是全量的，所以合并后不会丢节次。

用法:
    python import_lists.py                 # 扫下载 + 桌面 + lists 里的副本
    python import_lists.py --downloads D:\some\dir   # 只扫指定目录（测试用）
    python import_lists.py --dry-run       # 只看会做什么
"""
import argparse
import os
import pathlib
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parent.parent
LISTS = ROOT / "lists"
DUP_SUFFIX = re.compile(r"\s*\(\d+\)$")     # 浏览器/资源管理器重名会存成 "X (1).txt"


def scan_dirs(explicit=""):
    """默认扫「下载」和「桌面」；--downloads 指定时只扫那一个。"""
    if explicit:
        return [pathlib.Path(explicit)]
    home = pathlib.Path(os.path.expanduser("~"))
    return [d for d in (home / "Downloads", home / "Desktop") if d.exists()]


def is_scraped(path):
    """认得出是抓取脚本导出的文件：内容里含 previewToken。"""
    try:
        head = path.read_text(encoding="utf-8-sig", errors="replace")[:4000]
    except Exception:
        return False
    return "previewToken=" in head


def urls_of(text):
    return [ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
            and ln.strip().lower().startswith("http")]


def merge_one(src, name, dry_run=False):
    """把 src 的地址合并进 lists\\<name>.txt。返回 True 表示有动作。"""
    dest = LISTS / f"{name}.txt"
    new_urls = urls_of(src.read_text(encoding="utf-8-sig", errors="replace"))
    if not new_urls:
        return False

    existing = []
    if dest.exists():
        existing = urls_of(dest.read_text(encoding="utf-8-sig", errors="replace"))
    merged = existing + [u for u in new_urls if u not in existing]

    same = src.name == dest.name
    print(f"[import] {src.name} -> {dest.name}"
          f"（新增 {len(merged) - len(existing)} 条，共 {len(merged)} 条）"
          + ("  [覆盖同名]" if same else ""))
    if dry_run:
        return True

    header = (f"# {name} · 由 import_lists.py 合并\n"
              f"# 每行一条地址；previewToken 地址会在下载时自动换成直链\n")
    dest.write_text(header + "\n".join(merged) + "\n", encoding="utf-8")
    if src.resolve() != dest.resolve():
        try:
            src.unlink()          # 搬走而不是留副本，避免下次重复导入
        except Exception:
            pass
    return True


def run(dirs, dry_run=False):
    LISTS.mkdir(exist_ok=True)
    moved = 0

    # 1) 下载文件夹 / 桌面
    for d in dirs:
        if not d.exists():
            continue
        for src in sorted(d.glob("*.txt")):
            if not is_scraped(src):
                continue
            name = DUP_SUFFIX.sub("", src.stem).strip() or "course"
            if merge_one(src, name, dry_run):
                moved += 1

    # 2) lists\ 里的 "X (1).txt" 副本（手动复制时选了保留两份）
    for src in sorted(LISTS.glob("*.txt")):
        if not DUP_SUFFIX.search(src.stem):
            continue
        name = DUP_SUFFIX.sub("", src.stem).strip() or "course"
        if merge_one(src, name, dry_run):
            moved += 1

    return moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--downloads", default="", help="只扫这个目录（测试/自定义用）")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    moved = run(scan_dirs(a.downloads), a.dry_run)
    if moved:
        print(f"[import] 共收编 {moved} 份清单")
    return 0


if __name__ == "__main__":
    sys.exit(main())
