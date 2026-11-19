"""
lists.py - 确保 lists\\ 目录存在，并报告有哪些待下载清单。

清单可以放进 lists\\，也可以直接把 txt 拖到入口图标上。
清单名就是课程名、文件夹名、文件名前缀；跑完会归档，lists\\ 只保留 .md 索引。
"""
import pathlib
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parent.parent
LISTS = ROOT / "lists"


def listed():
    """返回 [(路径, 地址数)]，按名字排序。"""
    out = []
    if not LISTS.exists():
        return out
    for p in sorted(LISTS.glob("*.txt")):
        try:
            n = sum(1 for line in p.read_text(encoding="utf-8-sig").splitlines()
                    if line.strip() and not line.strip().startswith("#")
                    and line.strip().lower().startswith("http"))
        except Exception:
            n = 0
        out.append((p, n))
    return out


def main():
    LISTS.mkdir(parents=True, exist_ok=True)
    items = listed()
    todo = [(p, n) for p, n in items if n]
    if not todo:
        print("=" * 56)
        print("  lists\\ 里还没有可下载的清单")
        print("=" * 56)
        print(f"  把抓取导出的 txt 放进 {LISTS}（或直接拖到入口图标上）。")
        print("  文件名就是课程名，例如：")
        print("    lists\\X.txt")
        print("  拿地址: 用书签抓取（推荐），或回放页 F12 -> 筛 ENCODER -> 右键复制 URL")
        print("")
        print("  跑完后 txt 会自动归档到 har_archive\\，lists\\ 只保留 <课程>.md 索引。")
        if items:
            print("")
            print("  当前已有但为空的清单:")
            for p, _ in items:
                print(f"    {p.name}")
        return 1
    print(f"[lists] 待下载清单 {len(todo)} 个:")
    for p, n in todo:
        print(f"    {p.name:24s} {n} 条地址 -> media\\{p.stem}\\")
    return 0


if __name__ == "__main__":
    sys.exit(main())
