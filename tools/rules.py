"""rules.py - 按课程配置下载规则（lists\\<课程>.rules）。

不写规则文件 = 全部下载（与旧版行为一致）。规则由 lectures.py 在下载时自动读取，
优先级高于命令行/环境变量里的 --only / --exclude。

用法:
    python tools\\rules.py                     交互式配置
    python tools\\rules.py list                查看所有清单及规则
    python tools\\rules.py set 软件设计 --only 4
    python tools\\rules.py set 软件设计 --only 20261030,20261104
    python tools\\rules.py set 软件设计 --exclude 2
    python tools\\rules.py clear 软件设计      取消规则（恢复全下）

规则文件格式（# 开头是注释）:
    only: 4
    exclude: 2
"""
import argparse
import pathlib
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not sys.stdin.isatty():          # 管道/脚本输入时按 UTF-8 解码
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parent.parent
LISTS = ROOT / "lists"
MEDIA = ROOT / "media"
WEEK_CN = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五",
           6: "周六", 7: "周日"}
KEYS = ("only", "exclude")


def rules_path_for(txt_path):
    """lists\\X.txt -> lists\\X.rules（拖拽外部 txt 时找它旁边的 .rules）。"""
    return pathlib.Path(txt_path).with_suffix(".rules")


def normalize_tokens(text):
    """'20261030, 4' -> ['20261030', '4']；返回 (tokens, errors)。"""
    s = (text or "").replace("，", ",")
    out, errors = [], []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if re.fullmatch(r"\d{8}", part):
            out.append(part)
        elif re.fullmatch(r"[1-7]", part):
            out.append(part)
        elif re.fullmatch(r"\d{8}_[\d\-]+", part):
            out.append(part)
        else:
            errors.append(part)
    return out, errors


def load(path):
    """读规则文件。返回 ({'only': [...], 'exclude': [...]}, errors)。"""
    path = pathlib.Path(path)
    rule = {"only": [], "exclude": []}
    errors = []
    if not path.exists():
        return rule, errors
    try:
        text = path.read_text(encoding="utf-8-sig")
    except Exception as e:
        return rule, [f"读取失败: {e}"]
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            errors.append(line)
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key not in KEYS:
            errors.append(line)
            continue
        tokens, bad = normalize_tokens(value)
        rule[key] = tokens
        errors += [f"{key}: {b}" for b in bad]
    return rule, errors


def save(path, rule):
    """写规则文件（两个 key 都为空则删除文件）。返回是否还有规则。"""
    path = pathlib.Path(path)
    only = rule.get("only") or []
    exclude = rule.get("exclude") or []
    if not only and not exclude:
        if path.exists():
            path.unlink()
        return False
    lines = [f"# {path.stem} 的下载规则（由 tools\\rules.py 生成；删掉本文件 = 全部下载）"]
    if only:
        lines.append("only: " + ",".join(only))
    if exclude:
        lines.append("exclude: " + ",".join(exclude))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def describe(rule):
    """[..] -> '排除 周二'；为空 -> '无（全部下载）'。"""
    bits = []
    for key, name in (("only", "只要"), ("exclude", "排除")):
        values = rule.get(key) or []
        if not values:
            continue
        shown = [WEEK_CN[int(v)] if re.fullmatch(r"[1-7]", v) else v for v in values]
        bits.append(name + " " + ", ".join(shown))
    return "；".join(bits) if bits else "无（全部下载）"


def resolve_filters(cli_only, cli_exclude, rule):
    """确定最终筛选：清单规则优先；没有规则才用命令行/环境变量。

    返回 (only, exclude, source)，source 为 '清单规则' 或 '命令行'。
    """
    if rule and ((rule.get("only") or []) or (rule.get("exclude") or [])):
        return list(rule.get("only") or []), list(rule.get("exclude") or []), "清单规则"
    return list(cli_only or []), list(cli_exclude or []), "命令行"


def media_courses(media_dir=None):
    """media 目录下已下载过的课程名（用于给清单已归档的课程配规则）。"""
    media_dir = pathlib.Path(media_dir) if media_dir else MEDIA
    if not media_dir.exists():
        return []
    return sorted(d.name for d in media_dir.iterdir() if d.is_dir())


def discover(lists_dir, media_dir=None):
    """返回课程候选列表，每项:

    {"name": 课程名, "txt": Path 或 None, "rule": dict, "errors": list}

    来源 = lists 下的 txt（有清单）+ media 下的课程（清单可能已归档）。
    """
    lists_dir = pathlib.Path(lists_dir)
    out, seen = [], set()
    for txt in sorted(lists_dir.glob("*.txt")):
        rule, errors = load(rules_path_for(txt))
        out.append({"name": txt.stem, "txt": txt, "rule": rule, "errors": errors})
        seen.add(txt.stem)
    for name in media_courses(media_dir):
        if name in seen:
            continue
        rule, errors = load(lists_dir / f"{name}.rules")
        out.append({"name": name, "txt": None, "rule": rule, "errors": errors})
    return out


def cmd_list(lists_dir, media_dir=None):
    items = discover(lists_dir, media_dir)
    if not items:
        print(f"[规则] {lists_dir} 里没有清单，media 里也没有课程")
        return 0
    print(f"[规则] 可配置的课程（{len(items)} 个）:")
    for it in items:
        mark = "" if it["txt"] else "  [无清单]"
        print(f"  {it['name']:24s} {describe(it['rule'])}{mark}")
        for e in it["errors"]:
            print(f"    !! 规则有误: {e}")
    return 0


def find_txt(lists_dir, name):
    """按 名字 / 名字.txt 找清单。"""
    p = pathlib.Path(lists_dir) / name
    if p.suffix == ".txt":
        return p
    return pathlib.Path(lists_dir) / f"{name}.txt"


def cmd_set(lists_dir, name, only_text, exclude_text):
    name = pathlib.Path(name).stem
    txt = find_txt(lists_dir, name)
    only, err1 = normalize_tokens(only_text)
    exclude, err2 = normalize_tokens(exclude_text)
    bad = err1 + err2
    if bad:
        print(f"[规则] 看不懂: {', '.join(bad)}（要 8 位日期或 1-7）")
        return 1
    path = rules_path_for(txt)
    kept = save(path, {"only": only, "exclude": exclude})
    if kept:
        print(f"[规则] 已写入 {path.name}: {describe({'only': only, 'exclude': exclude})}")
        if txt.exists():
            print("       下次双击 1-开始下载.cmd 就会按这个规则跑（跑完保留清单）")
        else:
            print(f"       注意：清单 {txt.name} 还不在 lists\\，规则先存着，")
            print("       等清单放进来后自动生效")
    else:
        print(f"[规则] 规则已清空（{path.name} 已删除），恢复全部下载")
    return 0


def cmd_clear(lists_dir, name):
    txt = find_txt(lists_dir, name)
    path = rules_path_for(txt)
    if path.exists():
        path.unlink()
        print(f"[规则] 已删除 {path.name}，{txt.name} 恢复全部下载")
    else:
        print(f"[规则] {txt.name} 本来就没有规则")
    return 0


def _read(prompt=""):
    """读一行；EOF 返回 None（按退出处理）。"""
    try:
        return input(prompt)
    except EOFError:
        return None


def interactive(lists_dir, media_dir=None):
    """交互式配置：配完后回到课程列表，输入 q 退出。"""
    while True:
        items = discover(lists_dir, media_dir)
        print("=" * 60)
        print("[规则] 按课程配置下载规则（输入 q 退出）")
        print("=" * 60)
        print("\n请选择课程:")
        for i, it in enumerate(items, 1):
            mark = "" if it["txt"] else "  [无清单]"
            print(f"  {i}) {it['name']:20s} 当前: {describe(it['rule'])}{mark}")
        manual = len(items) + 1
        print(f"  {manual}) 手动输入课程名（新课/清单还没放进来）")
        print("  q) 退出")

        txt = None
        while txt is None:
            raw = _read("> ")
            if raw is None:
                print("\n[规则] 已退出")
                return 0
            s = raw.strip()
            if s.lower() in ("q", "quit", "exit"):
                print("\n[规则] 已退出")
                return 0
            if not (s.isdigit() and 1 <= int(s) <= manual):
                print(f"  !! 请输入 1-{manual}，或 q 退出")
                continue
            if int(s) == manual:
                name = _read("课程名（= 清单文件名，不带 .txt）: ")
                if name is None:
                    print("\n[规则] 已退出")
                    return 0
                name = pathlib.Path(name.strip()).stem
                if not name:
                    print("  !! 课程名不能为空")
                    continue
                txt = pathlib.Path(lists_dir) / f"{name}.txt"
            else:
                it = items[int(s) - 1]
                txt = it["txt"] if it["txt"] else pathlib.Path(lists_dir) / f"{it['name']}.txt"

        print(f"\n给 {txt.stem} 设置规则:")
        print("  1) 全部下载（删除规则）")
        print("  2) 只下星期几")
        print("  3) 排除星期几")
        print("  4) 只下某几天（输入日期）")
        choice = None
        while choice not in ("1", "2", "3", "4"):
            raw = _read("> ")
            if raw is None:
                print("\n[规则] 已退出")
                return 0
            choice = raw.strip()
            if choice.lower() in ("q", "quit", "exit"):
                print("\n[规则] 已退出")
                return 0
            if choice not in ("1", "2", "3", "4"):
                print("  !! 请输入 1-4，或 q 退出")

        only, exclude = [], []
        if choice == "1":
            pass
        elif choice in ("2", "3"):
            print("\n星期几（1=周一 … 7=周日；多个用逗号，如 2,4）:")
            tokens = []
            while not tokens:
                raw = _read("> ")
                if raw is None:
                    print("\n[规则] 已退出")
                    return 0
                if raw.strip().lower() in ("q", "quit", "exit"):
                    print("\n[规则] 已退出")
                    return 0
                tokens, bad = normalize_tokens(raw)
                if bad or not tokens:
                    print("  !! 只能输入 1-7，或 q 退出")
                    tokens = []
            if choice == "2":
                only = tokens
            else:
                exclude = tokens
        else:
            print("\n日期（8 位，如 20261030；多个用逗号）:")
            tokens = []
            while not tokens:
                raw = _read("> ")
                if raw is None:
                    print("\n[规则] 已退出")
                    return 0
                if raw.strip().lower() in ("q", "quit", "exit"):
                    print("\n[规则] 已退出")
                    return 0
                tokens, bad = normalize_tokens(raw)
                if bad or not tokens:
                    print("  !! 要 8 位日期，如 20261030，或 q 退出")
                    tokens = []
            only = tokens

        path = rules_path_for(txt)
        kept = save(path, {"only": only, "exclude": exclude})
        print()
        if kept:
            print(f"已写入 {path.name}: {describe({'only': only, 'exclude': exclude})}")
            print("下次双击 1-开始下载.cmd 就会按这个规则跑（跑完保留清单，不归档）。")
        else:
            print("规则已清空（规则文件已删除），该课程恢复全部下载。")
        print("\n继续配置其它课程，或输入 q 退出。")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--lists-dir", default="", help="覆盖清单目录（测试用）")
    ap.add_argument("--media-dir", default="", help="覆盖媒体库目录（测试用）")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("list", help="列出清单与规则")

    p_set = sub.add_parser("set", help="设置规则")
    p_set.add_argument("name", help="课程名（清单文件名，可不带 .txt）")
    p_set.add_argument("--only", default="", help="只下这些日期/星期几")
    p_set.add_argument("--exclude", default="", help="跳过这些日期/星期几")

    p_clear = sub.add_parser("clear", help="取消规则")
    p_clear.add_argument("name")

    a = ap.parse_args(argv)
    lists_dir = pathlib.Path(a.lists_dir) if a.lists_dir else LISTS
    media_dir = pathlib.Path(a.media_dir) if a.media_dir else None

    if a.cmd == "list":
        return cmd_list(lists_dir, media_dir)
    if a.cmd == "set":
        if not a.only and not a.exclude:
            print("[规则] 用 --only / --exclude 指定规则；要清空请用 clear")
            return 1
        return cmd_set(lists_dir, a.name, a.only, a.exclude)
    if a.cmd == "clear":
        return cmd_clear(lists_dir, a.name)
    return interactive(lists_dir, media_dir)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\n[规则] 已取消")
        sys.exit(130)
