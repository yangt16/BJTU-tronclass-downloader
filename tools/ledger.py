"""ledger.py - 下载台账（lists\\downloaded.jsonl）。

记录"哪一节确实下载并校验通过过"，与 media 里的文件是否存在无关。
用途：用户因空间不足删掉了旧文件后，再跑同一份清单不会从头重下。

每行一个 JSON（约 100 字节）:
    {"course":"XX课程","date":"20261029","span":"101000-120500",
     "video":true,"audio":true,"bytes":1420000000,"at":"2026-11-22 16:20:11"}

注意：video/audio 记录的是"当时保留下来的产物"：
  * 只要视频模式 / 视频+音频：video=true
  * 只要音频模式（下完删 mp4）：video=false, audio=true
这样以后切换模式时不会误跳过（缺的类型照样下）。
"""
import json
import pathlib
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDGER_PATH = ROOT / "lists" / "downloaded.jsonl"
_LOCK = threading.Lock()

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def key(course, date, span=""):
    return f"{course}|{date}|{span or '-'}"


def load(path=None):
    """返回 ({key: entry}, 坏行数)。坏行跳过，不影响其它记录。"""
    path = pathlib.Path(path) if path else LEDGER_PATH
    out = {}
    bad = 0
    if not path.exists():
        return out, bad
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return out, 1
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            bad += 1
            continue
        if not isinstance(e, dict) or not e.get("course") or not e.get("date"):
            bad += 1
            continue
        out[key(e["course"], e["date"], e.get("span", ""))] = e
    return out, bad


def record(course, date, span, video, audio, nbytes=0, path=None):
    """追加一条台账（线程安全；下载并发时会多线程调用）。"""
    path = pathlib.Path(path) if path else LEDGER_PATH
    entry = {
        "course": course,
        "date": date,
        "span": span or "",
        "video": bool(video),
        "audio": bool(audio),
        "bytes": int(nbytes),
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        with _LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        return None
    return entry


def satisfies(entry, mode):
    """台账记录是否满足本次产物模式（both/audio/video）。"""
    if not entry:
        return False
    if mode == "video":
        return bool(entry.get("video"))
    if mode == "audio":
        return bool(entry.get("audio"))
    return bool(entry.get("video")) and bool(entry.get("audio"))


def stats(path=None):
    """返回 (记录数, 坏行数, 覆盖课程数)。"""
    data, bad = load(path)
    return len(data), bad, len({e.get("course") for e in data.values()})


def _main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--stats" in argv:
        n, bad, courses = stats()
        print(f"[台账] {LEDGER_PATH}")
        print(f"  记录 {n} 节，覆盖 {courses} 门课" + (f"，坏行 {bad}" if bad else ""))
        return 0
    if "--clear" in argv:
        try:
            if LEDGER_PATH.exists():
                LEDGER_PATH.unlink()
            print(f"[台账] 已清空 {LEDGER_PATH}")
        except Exception as e:
            print(f"[台账] 清空失败: {e}")
            return 1
        return 0
    print(__doc__.strip())
    print("\n用法: python tools\\ledger.py --stats | --clear")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
