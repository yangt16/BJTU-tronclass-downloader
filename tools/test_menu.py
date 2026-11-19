"""校验 menu.py 的输入解析与环境变量映射（不联网、不启动引擎）。

用法: python tools/test_menu.py
"""
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import menu  # noqa: E402

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


# ---------- 日期解析 ----------
check("日期单个", menu.parse_dates("20261030"), "20261030")
check("日期逗号+空格", menu.parse_dates("20261030, 20261104"), "20261030,20261104")
check("日期中文逗号", menu.parse_dates("20261030，20261104"), "20261030,20261104")
check("日期位数不对 -> None", menu.parse_dates("2026"), None)
check("日期空 -> None", menu.parse_dates(""), None)

# ---------- 星期几解析 ----------
check("星期几单个", menu.parse_weekdays("4"), "4")
check("星期几多个", menu.parse_weekdays("2,4"), "2,4")
check("星期几 0 -> None", menu.parse_weekdays("0"), None)
check("星期几 8 -> None", menu.parse_weekdays("8"), None)
check("星期几混入 9 -> None", menu.parse_weekdays("4,9"), None)

# ---------- 环境变量映射 ----------
base_with_leftover = {"GETLEC_ONLY": "20261030", "GETLEC_DROPVIDEO": "1",
                      "GETLEC_JOBS": "4", "PATH": "x"}

env = menu.build_env("1", "1")
check("默认不设模式变量", "GETLEC_DROPVIDEO" in env or "GETLEC_NOAUDIO" in env, False)
check("默认并发 2 路", env.get("GETLEC_JOBS"), "2")
check("默认不设筛选变量", "GETLEC_ONLY" in env or "GETLEC_EXCLUDE" in env, False)

env = menu.build_env("2", "1")
check("只要音频 -> DROPVIDEO", env.get("GETLEC_DROPVIDEO"), "1")

env = menu.build_env("3", "1")
check("只要视频 -> NOAUDIO", env.get("GETLEC_NOAUDIO"), "1")

env = menu.build_env("1", "2", "20261030")
check("只下某天 -> ONLY", env.get("GETLEC_ONLY"), "20261030")

env = menu.build_env("1", "3", "4,6")
check("只下星期 -> ONLY", env.get("GETLEC_ONLY"), "4,6")

env = menu.build_env("1", "4", "2")
check("排除星期 -> EXCLUDE", env.get("GETLEC_EXCLUDE"), "2")

env = menu.build_env("1", "1", jobs="4")
check("并发 4 路 -> GETLEC_JOBS", env.get("GETLEC_JOBS"), "4")

env = menu.build_env("1", "1", base=base_with_leftover)
check("清掉上次残留 ONLY", "GETLEC_ONLY" in env, False)
check("清掉上次残留 DROPVIDEO", "GETLEC_DROPVIDEO" in env, False)
check("残留 JOBS 被覆盖为默认", env.get("GETLEC_JOBS"), "2")
check("保留无关变量", env.get("PATH"), "x")

# ---------- 摘要文案 ----------
check("摘要 默认", menu.describe("1", "1"), ("视频 + 音频", "下载全部"))
check("摘要 周四", menu.describe("1", "3", "4"), ("视频 + 音频", "只下 周四"))
check("摘要 排除周二周四", menu.describe("2", "4", "2,4"), ("只要音频", "排除 周二,周四"))
check("摘要 某天", menu.describe("3", "2", "20261030"), ("只要视频", "只下 20261030"))
check("并发文案表", menu.JOBS_CN, {"1": "1 路", "2": "2 路", "3": "3 路", "4": "4 路"})

print()
print("全部通过" if bad == 0 else f"{bad} 项失败")
sys.exit(0 if bad == 0 else 1)
