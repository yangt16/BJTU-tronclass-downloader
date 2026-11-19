"""clean_archive.py - 清理 har_archive\\（和可选的 logs\\）。

归档里存的是历史清单（含签名地址），只会越攒越多；日志同理。
默认**只预览**，加 --yes 才真的删。

用法:
    python tools\\clean_archive.py                  预览：60 天前的归档
    python tools\\clean_archive.py --days 30        预览：30 天前
    python tools\\clean_archive.py --keep 20        预览：只保留最近 20 个
    python tools\\clean_archive.py --days 30 --yes  真删
    python tools\\clean_archive.py --logs --days 30 --yes   连同 logs\\ 一起
"""
import argparse
import pathlib
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parent.parent


def collect(dirpath, days=None, keep=0, now=None):
    """返回该目录下待删文件（按修改时间从旧到新）。"""
    dirpath = pathlib.Path(dirpath)
    if not dirpath.exists():
        return []
    now = time.time() if now is None else now
    files = sorted((p for p in dirpath.glob("*") if p.is_file()),
                   key=lambda p: p.stat().st_mtime)
    if days is not None:
        cutoff = now - days * 86400
        files = [p for p in files if p.stat().st_mtime < cutoff]
    if keep and len(files) > keep:
        files = files[:-keep]
    return files


def fmt_size(n):
    if n >= 1024 ** 3:
        return f"{n / 1024**3:.2f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024**2:.1f} MB"
    return f"{n / 1024:.1f} KB"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60, help="删除早于 N 天的文件（默认 60）")
    ap.add_argument("--keep", type=int, default=0, help="无论多旧，保留最近 N 个（默认 0）")
    ap.add_argument("--logs", action="store_true", help="连 logs\\ 一起清理")
    ap.add_argument("--yes", action="store_true", help="真的删除（不加只预览）")
    ap.add_argument("--root", default="", help="覆盖归档目录（测试用）")
    a = ap.parse_args(argv)

    if a.root:
        roots = [pathlib.Path(a.root)]
    else:
        roots = [ROOT / "har_archive"]
        if a.logs:
            roots.append(ROOT / "logs")

    targets = []
    for d in roots:
        found = collect(d, a.days, a.keep)
        if not found:
            continue
        print(f"\n[{d.name}] 符合条件 {len(found)} 个：")
        for p in found:
            size = p.stat().st_size
            age = (time.time() - p.stat().st_mtime) / 86400
            print(f"  {p.name:52s} {fmt_size(size):>9s}  {age:5.0f} 天前")
        targets += found

    if not targets:
        print(f"[clean] 没有超过 {a.days} 天的文件（--keep {a.keep}）")
        return 0

    total = sum(p.stat().st_size for p in targets)
    print(f"\n[clean] 共 {len(targets)} 个文件 / {fmt_size(total)}")
    if not a.yes:
        print("[clean] 预览模式：确认无误后加 --yes 真删")
        return 0

    freed = 0
    for p in targets:
        try:
            freed += p.stat().st_size
            p.unlink()
        except Exception as e:
            print(f"  !! 删除失败 {p.name}: {e}")
    print(f"[clean] 已删除 {len(targets)} 个文件，释放 {fmt_size(freed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
