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
SEG_INV = {v: k for k, v in SEG_MAP.items()}

MEMORY_PATH = ROOT / ".menu.json"
MEMORY_KEYS = ("mode", "scope", "value", "jobs", "seg")
MEMORY_DEFAULT = {"mode": "1", "scope": "1", "value": "", "jobs": "2", "seg": "1"}


def load_memory(path=None):
    """读上次的选择（文件不存在/损坏时用默认值）。"""
    path = pathlib.Path(path) if path else MEMORY_PATH
    data = dict(MEMORY_DEFAULT)
    try:
        raw = __import__("json").loads(path.read_text(encoding="utf-8"))
    except Exception:
        return data
    if isinstance(raw, dict):
        for k in MEMORY_KEYS:
            v = raw.get(k)
            if isinstance(v, str):
                data[k] = v
    if data["mode"] not in MODE_CN:
        data["mode"] = "1"
    if data["scope"] not in SCOPE_CN:
        data["scope"] = "1"
    if data["jobs"] not in JOBS_CN:
        data["jobs"] = "2"
    if data["seg"] not in SEG_CN:
        data["seg"] = "1"
    return data


def save_memory(choice, path=None):
    """把本次选择写进记忆文件，下次作为默认值。"""
    path = pathlib.Path(path) if path else MEMORY_PATH
    try:
        path.write_text(__import__("json").dumps(choice, ensure_ascii=False),
                        encoding="utf-8")
        return True
    except Exception:
        return False


def forget_memory(path=None):
    """清除记忆（恢复默认）。"""
    path = pathlib.Path(path) if path else MEMORY_PATH
    try:
        if path.exists():
            path.unlink()
        return True
    except Exception:
        return False


def show_options(items, default):
    """打印选项，并标出"上次"。"""
    for key, label in items:
        mark = "  [上次]" if key == default else ""
        print(f"  {key}) {label}{mark}")

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
    print("[menu] 下载设置（直接回车 = 沿用记忆/默认值）")
    print("=" * 60)

    mem = load_memory()
    if mem != MEMORY_DEFAULT:
        print(f"\n[记忆] 上次：{MODE_CN[mem['mode']]} / {SCOPE_CN[mem['scope']]}"
              f" / {JOBS_CN[mem['jobs']]} / 单节加速 {SEG_CN[mem['seg']]}")

    print("\n产物：")
    show_options([(k, v) for k, v in MODE_CN.items()], mem["mode"])
    mode = choose("> ", mem["mode"], MODE_CN)

    print("\n范围：")
    show_options([(k, v) for k, v in SCOPE_CN.items()], mem["scope"])
    scope = choose("> ", mem["scope"], SCOPE_CN)

    print("\n并发下载（越多越快，但对服务器压力也越大）：")
    show_options([("1", JOBS_CN["1"]), ("2", JOBS_CN["2"]), ("3", JOBS_CN["3"])],
                 mem["jobs"])
    print("  4) 4 路" + ("  [上次]" if mem["jobs"] == "4" else ""))
    jobs = choose("> ", mem["jobs"], JOBS_CN)

    print("\n单节加速（只补一两节时有用；多节并发时保持关闭）：")
    show_options([("1", "关闭"), ("2", "4 段")], SEG_INV[mem["seg"]])
    print("  3) 8 段（实测比 4 段快约 2 倍）"
          + ("  [上次]" if mem["seg"] == "8" else ""))
    seg = SEG_MAP[choose("> ", SEG_INV[mem["seg"]], SEG_MAP)]

    value = ""
    mem_value = mem["value"] if scope == mem["scope"] else ""
    if scope == "2":
        while not value:
            hint = f"，回车沿用 {mem_value}" if mem_value else ""
            value = parse_dates(
                ask(f"\n日期（8 位，如 20261030；多个用逗号{hint}）：")) or mem_value
            if not value:
                print("  !! 需要 8 位日期，如 20261030")
    elif scope in ("3", "4"):
        while not value:
            hint = f"，回车沿用 {mem_value}" if mem_value else ""
            value = parse_weekdays(
                ask(f"\n星期几（1=周一 … 7=周日；多个用逗号，如 2,4{hint}）：")) or mem_value
            if not value:
                print("  !! 只能输入 1-7，如 4 或 2,4")

    save_memory({"mode": mode, "scope": scope, "value": value,
                 "jobs": jobs, "seg": seg})

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
    if "--forget" in sys.argv[1:]:
        if forget_memory():
            print("[记忆] 已清除，下次回到默认（视频+音频 / 全部 / 2 路 / 关闭）")
        else:
            print("[记忆] 清除失败")
        sys.exit(0)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if not sys.stdin.isatty():
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[menu] 已取消")
        sys.exit(130)
