"""校验 batch.py 的离线节数估算、参数翻译与批次上下文（不联网）。

用法: python tools/test_batch.py
"""
import os
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import batch  # noqa: E402
from lectures import read_batch_ctx  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

bad = 0


def check(name, got, want):
    global bad
    ok = got == want
    print(f"[{'PASS' if ok else 'FAIL'}] {name:34s} got={got!r} want={want!r}")
    if not ok:
        bad += 1


BASE = ROOT / "tmp" / f"testbatch_{os.getpid()}"
LISTS = BASE / "lists"
LISTS.mkdir(parents=True)
try:
    # ---------- count_sections：previewToken 按 captures/<hash> 去重 ----------
    p1 = LISTS / "A.txt"
    p1.write_text(
        "# 注释\n"
        "https://incast.example/api/base/orgs/bjtu/captures/hash1/videos/c1/preview?previewToken=a\n"
        "https://incast.example/api/base/orgs/bjtu/captures/hash1/videos/c2/preview?previewToken=b\n"
        "https://incast.example/api/base/orgs/bjtu/captures/hash1/videos/c3/preview?previewToken=c\n"
        "https://incast.example/api/base/orgs/bjtu/captures/hash2/videos/c1/preview?previewToken=d\n"
        "https://incast.example/api/base/orgs/bjtu/captures/hash2/videos/c2/preview?previewToken=e\n"
        "https://incast.example/api/base/orgs/bjtu/captures/hash2/videos/c3/preview?previewToken=f\n",
        encoding="utf-8")
    check("preview 地址按 hash 去重 -> 2 节", batch.count_sections(p1), 2)

    # ---------- 直链：同标签 3 条轨算 1 节 ----------
    p2 = LISTS / "B.txt"
    p2.write_text(
        "https://h/videos/outbound1/bjtu/room1/20261030/101000-120500-1/ENCODER-a?ts=1\n"
        "https://h/videos/outbound1/bjtu/room1/20261030/101000-120500-1/STUDENTS-b?ts=1\n"
        "https://h/videos/outbound1/bjtu/room1/20261030/101000-120500-1/INSTRUCTOR-c?ts=1\n"
        "https://h/videos/outbound1/bjtu/room1/20261104/080000-095500-1/ENCODER-d?ts=1\n",
        encoding="utf-8")
    check("直链按标签去重 -> 2 节", batch.count_sections(p2), 2)

    p3 = LISTS / "C.txt"
    p3.write_text("# 只有注释\n\n", encoding="utf-8")
    check("空清单 -> 0", batch.count_sections(p3), 0)

    # ---------- build_args：环境变量 -> lectures 参数 ----------
    env = {"GETLEC_DRYRUN": "1", "GETLEC_NOAUDIO": "1", "GETLEC_ONLY": "4",
           "GETLEC_JOBS": "3", "GETLEC_SEGMENTS": "8"}
    check("参数翻译", batch.build_args(env),
          ["--dry-run", "--no-audio", "--only", "4", "--jobs", "3",
           "--segments", "8"])
    check("无变量 -> 空参数", batch.build_args({}), [])
    check("轨道参数", batch.build_args({"GETLEC_TRACK": "INSTRUCTOR"}),
          ["--track", "INSTRUCTOR"])
    check("默认轨道不传参", batch.build_args({"GETLEC_TRACK": "ENCODER"}), [])

    # ---------- read_batch_ctx ----------
    ctx = read_batch_ctx({"GETLEC_BATCH_TOTAL": "12", "GETLEC_BATCH_BEFORE": "4",
                          "GETLEC_BATCH_START": "100.0"})
    check("批次上下文", ctx, {"total": 12, "before": 4, "start": 100.0})
    check("缺变量 -> None", read_batch_ctx({}), None)
    check("非法值 -> None", read_batch_ctx({"GETLEC_BATCH_TOTAL": "x"}), None)

    # ---------- e2e：--dry-run-lists ----------
    r = subprocess.run([sys.executable, str(HERE / "batch.py"),
                        "--lists-dir", str(LISTS), "--dry-run-lists"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT))
    out = r.stdout
    check("清单汇总行", "共 2 份清单 / 约 4 节" in out, True)
    check("每个清单都列出", "A.txt" in out and "B.txt" in out, True)

    # ---------- B：批量开始前的规则汇总 + 确认 ----------
    import builtins
    import rules as rules_mod
    info = batch.menu_desc({"GETLEC_DROPVIDEO": "1", "GETLEC_JOBS": "4",
                            "GETLEC_SEGMENTS": "8", "GETLEC_ONLY": "4"})
    check("菜单描述-产物", info["产物"], "只要音频")
    check("菜单描述-并发", info["并发"], "4 路")
    check("菜单描述-单节加速", info["单节加速"], "8 段")
    check("菜单描述-筛选", info["筛选"], "只要 4")
    rules_mod.save(p1.with_suffix(".rules"),
                   {"only": ["4"], "exclude": [], "mode": "audio"})
    rows = batch.rules_summary([(p1, 2), (p2, 2)])
    check("规则汇总-A 含规则", "产物 只要音频" in rows[0][1] and rows[0][2], True)
    check("规则汇总-B 无规则", rows[1][2], False)
    check("非交互自动开始", batch.confirm_batch([(p1, 2)], {}, is_tty=False), True)
    check("--yes 直接开始",
          batch.confirm_batch([(p1, 2)], {}, yes=True, is_tty=True), True)
    old_input = builtins.input
    builtins.input = lambda prompt="": "n"
    try:
        got = batch.confirm_batch([(p1, 2)], {}, is_tty=True)
    finally:
        builtins.input = old_input
    check("输入 n 取消", got, False)
finally:
    shutil.rmtree(BASE, ignore_errors=True)

print()
print("全部通过" if bad == 0 else f"{bad} 项失败")
sys.exit(0 if bad == 0 else 1)
