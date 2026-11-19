"""menu.py - 交互菜单（由 1-开始下载.cmd / .command 调用）。

三项选择组合：
    产物：视频+音频 / 只要音频 / 只要视频
    范围：全部 / 只下某一天 / 只下星期几 / 排除星期几
    并发：1 / 2 / 3 / 4 路

问完把选择写进 GETLEC_* 环境变量，再启动 tools/getlec.cmd（Windows）
或 tools/getlec.sh（macOS / Linux），所以下载逻辑只有引擎一份。

直接回车 = 方括号里的默认值，连按两次回车等价于旧版"下视频和音频"入口。
"""
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEEK_CN = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}
MODE_CN = {"1": "视频 + 音频", "2": "只要音频", "3": "只要视频"}
JOBS_CN = {"1": "1 路", "2": "2 路", "3": "3 路", "4": "4 路"}
SEG_CN = {"1": "关闭", "4": "4 段", "8": "8 段"}
# 菜单上显示的序号 -> 实际段数（1 关闭 / 2 四段 / 3 八段）
SEG_MAP = {"1": "1", "2": "4", "3": "8"}
SCOPE_CN = {"1": "下载全部", "2": "只下某一天", "3": "只下星期几", "4": "排除星期几"}

# 菜单接管的变量：每次运行前清掉，避免上一次的残留影响本次
MANAGED = ("GETLEC_DROPVIDEO", "GETLEC_NOAUDIO", "GETLEC_ONLY",
           "GETLEC_EXCLUDE", "GETLEC_JOBS", "GETLEC_SEGMENTS")


def parse_dates(text):
    """'20261030, 20261104' -> '20261030,20261104'；非法返回 None。"""
    s = (text or "").replace("，", ",").replace(" ", "")
    return s if re.fullmatch(r"\d{8}(,\d{8})*", s) else None


def parse_weekdays(text):
    """'4,6' -> '4,6'；非法返回 None。"""
    s = (text or "").replace("，", ",").replace(" ", "")
    return s if re.fullmatch(r"[1-7](,[1-7])*", s) else None


def build_env(mode, scope, value="", jobs="2", seg="1", base=None):
    """菜单选择 -> 环境变量。mode 1/2/3；scope 1/2/3/4；jobs 1..4；seg 1/4。"""
    env = dict(os.environ if base is None else base)
    for k in MANAGED:
        env.pop(k, None)
    env["GETLEC_JOBS"] = jobs
    env["GETLEC_SEGMENTS"] = seg
    if mode == "2":
        env["GETLEC_DROPVIDEO"] = "1"
    elif mode == "3":
        env["GETLEC_NOAUDIO"] = "1"
    if scope in ("2", "3"):
        env["GETLEC_ONLY"] = value
    elif scope == "4":
        env["GETLEC_EXCLUDE"] = value
    return env


def describe(mode, scope, value=""):
    """返回 (产物中文, 范围中文)。"""
    if scope == "2":
        ranges = f"只下 {value}"
    elif scope in ("3", "4"):
        names = ",".join(WEEK_CN[int(d)] for d in value.split(","))
        ranges = ("只下 " if scope == "3" else "排除 ") + names
    else:
        ranges = "下载全部"
    return MODE_CN[mode], ranges


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def choose(prompt, default, labels):
    while True:
        s = ask(prompt) or default
        if s in labels:
            return s
        print(f"  !! 请输入 {' / '.join(sorted(labels))}")


def main():
    print("=" * 60)
    print("[menu] 下载设置（直接回车 = 方括号里的默认值）")
    print("=" * 60)

    print("\n产物：")
    print("  1) 视频 + 音频  [1]")
    print("  2) 只要音频")
    print("  3) 只要视频")
    mode = choose("> ", "1", MODE_CN)

    print("\n范围：")
    print("  1) 下载全部      [1]")
    print("  2) 只下某一天")
    print("  3) 只下星期几")
    print("  4) 排除星期几")
    scope = choose("> ", "1", SCOPE_CN)

    print("\n并发下载（越多越快，但对服务器压力也越大）：")
    print("  1) 1 路（最稳）")
    print("  2) 2 路  [2]")
    print("  3) 3 路")
    print("  4) 4 路")
    jobs = choose("> ", "2", JOBS_CN)

    print("\n单节加速（只补一两节时有用；多节并发时保持关闭）：")
    print("  1) 关闭  [1]")
    print("  2) 4 段")
    print("  3) 8 段（实测比 4 段快约 2 倍）")
    seg = SEG_MAP[choose("> ", "1", SEG_MAP)]

    value = ""
    if scope == "2":
        while not value:
            value = parse_dates(ask("\n日期（8 位，如 20261030；多个用逗号）：")) or ""
            if not value:
                print("  !! 需要 8 位日期，如 20261030")
    elif scope in ("3", "4"):
        while not value:
            value = parse_weekdays(ask("\n星期几（1=周一 … 7=周日；多个用逗号，如 2,4）：")) or ""
            if not value:
                print("  !! 只能输入 1-7，如 4 或 2,4")

    mode_cn, range_cn = describe(mode, scope, value)
    print("\n" + "=" * 60)
    print(f"  产物：{mode_cn}")
    print(f"  范围：{range_cn}")
    print(f"  并发：{JOBS_CN[jobs]}    单节加速：{SEG_CN[seg]}")
    print("=" * 60)
    print()

    sys.stdout.flush()          # 先把自己的输出吐完，再接引擎的

    env = build_env(mode, scope, value, jobs, seg)
    if os.name == "nt":
        cmd = [os.environ.get("COMSPEC", "cmd.exe"), "/c",
               str(ROOT / "tools" / "getlec.cmd")]
    else:
        cmd = ["sh", str(ROOT / "tools" / "getlec.sh")]
    rc = subprocess.call(cmd, env=env, cwd=str(ROOT))
    if rc != 0:
        print(f"\n[menu] 引擎返回 {rc}")
    return rc


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[menu] 已取消")
        sys.exit(130)
