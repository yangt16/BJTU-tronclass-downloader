"""batch.py - 批量下载驱动（替代入口脚本里的逐清单循环）。

职责：
  * 枚举 lists\\*.txt，离线估算每份清单有多少节（不联网）
  * 逐份调用 lectures.py，并把"全局进度上下文"通过环境变量传下去：
        GETLEC_BATCH_TOTAL / GETLEC_BATCH_BEFORE / GETLEC_BATCH_START
    lectures.py 用它打印跨清单的"全局进度 + 预计剩余时间"
  * 结束后汇总；失败清单不影响其它清单继续跑

Windows 和 macOS 共用这一份批次逻辑。
"""
import argparse
import os
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
LISTS = ROOT / "lists"
HASH_RE = re.compile(r"/captures/([^/]+)/videos/")


def count_sections(path):
    """离线估算一份清单有几节（不联网）。

    previewToken 地址：同一节课的 3 条轨共享 captures/<hash>，按 hash 去重。
    直链：按 lectures.label_of 的标签去重。
    """
    urls = []
    for line in pathlib.Path(path).read_text(encoding="utf-8-sig").splitlines():
        u = line.strip()
        if u and not u.startswith("#") and u.lower().startswith("http"):
            urls.append(u)
    if not urls:
        return 0

    sys.path.insert(0, str(ROOT / "tools"))
    from lectures import label_of  # noqa: E402

    keys = set()
    for u in urls:
        m = HASH_RE.search(u)
        if "previewToken=" in u and m:
            keys.add("cap:" + m.group(1))
            continue
        lab = label_of(u)
        keys.add(("lab:" + lab) if lab and lab != "lecture" else ("url:" + u))
    return len(keys)


def build_args(env=None):
    """把 GETLEC_* 环境变量翻译成 lectures.py 的参数。"""
    env = os.environ if env is None else env
    args = []
    if env.get("GETLEC_DRYRUN") == "1":
        args.append("--dry-run")
    if env.get("GETLEC_DROPVIDEO") == "1":
        args.append("--drop-video")
    if env.get("GETLEC_NOAUDIO") == "1":
        args.append("--no-audio")
    if env.get("GETLEC_KEEPLIST") == "1":
        args.append("--keep-list")
    if env.get("GETLEC_FORCE") == "1":
        args.append("--force")
    for key, arg in (("GETLEC_ONLY", "--only"), ("GETLEC_EXCLUDE", "--exclude"),
                     ("GETLEC_JOBS", "--jobs"), ("GETLEC_SEGMENTS", "--segments")):
        if env.get(key):
            args += [arg, env[key]]
    track = (env.get("GETLEC_TRACK") or "").upper()
    if track and track != "ENCODER":
        args += ["--track", track]
    return args


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--lists-dir", default="", help="覆盖清单目录（测试用）")
    ap.add_argument("--dry-run-lists", action="store_true", help="只列清单和节数")
    a = ap.parse_args(argv)

    lists_dir = pathlib.Path(a.lists_dir) if a.lists_dir else LISTS
    items = []
    for p in sorted(lists_dir.glob("*.txt")):
        n = count_sections(p)
        if n:
            items.append((p, n))

    if not items:
        print("[batch] 没有可下载的清单")
        return 0

    total = sum(n for _, n in items)
    print(f"[batch] 共 {len(items)} 份清单 / 约 {total} 节")
    if a.dry_run_lists:
        for p, n in items:
            print(f"  {p.name}: 约 {n} 节")
        return 0

    env = dict(os.environ)
    env["GETLEC_BATCH_TOTAL"] = str(total)
    start = time.time()
    env["GETLEC_BATCH_START"] = f"{start:.3f}"

    before = 0
    failed = []
    for i, (p, n) in enumerate(items, 1):
        sys.stdout.flush()
        print(f"\n[batch] === 清单 {i}/{len(items)}: {p.name}（约 {n} 节）===")
        sys.stdout.flush()
        env["GETLEC_BATCH_BEFORE"] = str(before)
        rc = subprocess.call(
            [sys.executable, str(ROOT / "tools" / "lectures.py"),
             "--urls", str(p)] + build_args(),
            env=env, cwd=str(ROOT))
        if rc != 0:
            failed.append(p.name)
        before += n

    sys.stdout.flush()
    print()
    if failed:
        print(f"[batch] 完成 {len(items) - len(failed)}/{len(items)} 份清单；"
              f"失败: {', '.join(failed)}（重跑同一批会自动跳过已完成的）")
    else:
        print(f"[batch] 全部完成：{len(items)} 份清单 / 约 {total} 节，"
              f"用时 {int((time.time() - start) // 60)} 分钟")
        sys.path.insert(0, str(ROOT / "tools"))
        from lectures import notify_done  # noqa: E402
        notify_done()
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
