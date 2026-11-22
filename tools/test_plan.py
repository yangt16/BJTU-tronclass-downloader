"""校验预扫描（plan_sections）与并发解析（resolve_jobs），不联网。

用法: python tools/test_plan.py
"""
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from lectures import (confirm_start, effective_segments, plan_sections,  # noqa: E402
                     resolve_jobs, resolve_segments, target_paths)

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


def url(date, span, track=""):
    t = f"{track}-x" if track else "ENCODER-abc"
    return f"https://h/videos/outbound1/bjtu/room1/{date}/{span}/{t}?ts=1&token=x"


L1 = "20261030_101000-120500"
L2 = "20261104_080000-095500"
groups = {
    L1: [url("20261030", "101000-120500-1", "STUDENTS"),
         url("20261030", "101000-120500-1")],
    L2: [url("20261104", "080000-095500-1")],
}

BASE = ROOT / "tmp" / f"testplan_{__import__('os').getpid()}"
shutil.rmtree(BASE, ignore_errors=True)

try:
    # ---------- 全未下载 ----------
    out1 = BASE / "out1"
    todo, skipped, archived = plan_sections(groups, out1, "both", "ENCODER")
    check("全未下载 -> todo 2", len(todo), 2)
    check("全未下载 -> archived 0", len(archived), 0)
    check("全未下载 -> skipped 0", len(skipped), 0)
    check("优先选 ENCODER 轨", todo[0]["pick"], groups[L1][1])
    check("落点文件名正确", todo[0]["mp4"].name, "out1_20261030.mp4")
    check("已建目录", (out1 / "20261030").exists(), True)

    # ---------- 标记第一节完成（both 需要 mp4 + m4a） ----------
    mp4, m4a = target_paths(out1, L1)
    mp4.write_bytes(b"v")
    m4a.write_bytes(b"a")
    todo, skipped, archived = plan_sections(groups, out1, "both", "ENCODER")
    check("已下载 -> skipped 1", len(skipped), 1)
    check("已下载 -> todo 剩 1", len(todo), 1)
    check("剩下的是第二节", todo[0]["label"], L2)

    # ---------- --force 不跳过 ----------
    todo, skipped, archived = plan_sections(groups, out1, "both", "ENCODER", force=True)
    check("force -> todo 2", len(todo), 2)
    check("force -> skipped 0", len(skipped), 0)

    # ---------- 只要音频模式：只有 m4a 也算完成 ----------
    out2 = BASE / "out2"
    out2.mkdir(parents=True)
    mp4b, m4ab = target_paths(out2, L1)
    (out2 / "20261030").mkdir(exist_ok=True)
    m4ab.write_bytes(b"a")
    todo, skipped, archived = plan_sections(groups, out2, "audio", "ENCODER")
    check("audio 模式 m4a 存在 -> skip", len(skipped), 1)

    # ---------- dry-run 不建目录 ----------
    out3 = BASE / "out3"
    todo, skipped, archived = plan_sections(groups, out3, "both", "ENCODER", dry_run=True)
    check("dry-run -> todo 2", len(todo), 2)
    check("dry-run 不建落点", out3.exists(), False)

    # ---------- 并发数解析 ----------
    check("默认 2 路", resolve_jobs(""), 2)
    check("显式 1 路", resolve_jobs("1"), 1)
    check("显式 4 路", resolve_jobs("4"), 4)
    check("超过上限收敛到 4", resolve_jobs("9"), 4)
    check("0 收敛到 1", resolve_jobs("0"), 1)
    check("非法值回落默认", resolve_jobs("x"), 2)
    check("环境变量生效", resolve_jobs("", {"GETLEC_JOBS": "3"}), 3)
    check("参数优先于环境", resolve_jobs("1", {"GETLEC_JOBS": "3"}), 1)

    # ---------- 单文件分段数 ----------
    check("分段默认关闭", resolve_segments(""), 1)
    check("分段 4 段", resolve_segments("4"), 4)
    check("分段超过上限收敛到 8", resolve_segments("99"), 8)
    check("分段环境变量", resolve_segments("", {"GETLEC_SEGMENTS": "4"}), 4)
    check("分段非法值回落 1", resolve_segments("x"), 1)
    check("节级 1 路 + 4 段 -> 4", effective_segments("4", 1), 4)
    check("节级 2 路 + 4 段 -> 4", effective_segments("4", 2), 4)
    check("节级 4 路 + 4 段 -> 2", effective_segments("4", 4), 2)
    check("节级 3 路 + 8 段 -> 2", effective_segments("8", 3), 2)

    # ---------- C：本清单下载前确认 ----------
    import builtins
    check("确认：--yes 直接开始", confirm_start(3, 0, 0, yes=True), True)
    check("确认：无需下载直接开始", confirm_start(0, 0, 0), True)
    check("确认：非交互自动开始", confirm_start(3, 0, 0, is_tty=False), True)
    old_input = builtins.input
    builtins.input = lambda prompt="": "y"
    try:
        y = confirm_start(3, 1, 0, is_tty=True)
    finally:
        builtins.input = old_input
    check("确认：输入 y 开始", y, True)
    builtins.input = lambda prompt="": "n"
    try:
        n = confirm_start(3, 1, 2, is_tty=True)
    finally:
        builtins.input = old_input
    check("确认：输入 n 取消", n, False)
finally:
    shutil.rmtree(BASE, ignore_errors=True)

print()
print("全部通过" if bad == 0 else f"{bad} 项失败")
sys.exit(0 if bad == 0 else 1)
