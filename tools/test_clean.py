"""校验 clean_archive 的筛选与预览/删除行为（不碰真实归档）。

用法: python tools/test_clean.py
"""
import os
import pathlib
import shutil
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import clean_archive  # noqa: E402

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


BASE = ROOT / "tmp" / f"testclean_{os.getpid()}"
shutil.rmtree(BASE, ignore_errors=True)
BASE.mkdir(parents=True)
now = time.time()


def make(name, age_days):
    p = BASE / name
    p.write_text("x" * 100, encoding="utf-8")
    t = now - age_days * 86400
    os.utime(p, (t, t))
    return p


try:
    make("old100.txt", 100)
    make("old50.txt", 50)
    make("new1.txt", 1)

    got = [p.name for p in clean_archive.collect(BASE, days=60, now=now)]
    check("60 天前 -> 只剩最旧的", got, ["old100.txt"])

    got = [p.name for p in clean_archive.collect(BASE, days=40, now=now)]
    check("40 天前 -> 两个", got, ["old100.txt", "old50.txt"])

    got = [p.name for p in clean_archive.collect(BASE, days=None, keep=2, now=now)]
    check("keep 2 -> 最旧的", got, ["old100.txt"])

    got = [p.name for p in clean_archive.collect(BASE, days=None, keep=0, now=now)]
    check("不筛选 -> 全部", len(got), 3)

    check("目录不存在 -> 空", clean_archive.collect(BASE / "nope"), [])

    # 预览：不删
    rc = clean_archive.main(["--root", str(BASE), "--days", "40"])
    check("预览返回 0", rc, 0)
    check("预览不删文件", len(list(BASE.glob("*"))), 3)

    # 真删：只删 40 天前的两个
    rc = clean_archive.main(["--root", str(BASE), "--days", "40", "--yes"])
    left = sorted(p.name for p in BASE.glob("*"))
    check("真删返回 0", rc, 0)
    check("只留新文件", left, ["new1.txt"])
finally:
    shutil.rmtree(BASE, ignore_errors=True)

print()
print("全部通过" if bad == 0 else f"{bad} 项失败")
sys.exit(0 if bad == 0 else 1)
