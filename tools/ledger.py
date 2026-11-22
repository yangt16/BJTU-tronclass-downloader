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


SPAN_RE = __import__("re").compile(r"_(\d{6}-\d{6})$")


def _session_span(daydir):
    """从 .session 取时段（单场次日期用）。"""
    tag = daydir / ".session"
    if tag.exists():
        try:
            label = tag.read_text(encoding="utf-8-sig").strip()
            if "_" in label:
                return label.split("_", 1)[1]
        except Exception:
            pass
    return ""


def _media_groups(daydir):
    """把一天的媒体文件按"场次"分组：{span: [files]}。

    单场次日期文件名不带时段 -> span 用 .session 里的时段。
    多场次日期文件名带 `_HHMMSS-HHMMSS` -> 每个时段一组。
    """
    files = [f for f in daydir.iterdir()
             if f.is_file() and f.suffix in (".mp4", ".m4a")]
    if not files:
        return {}
    groups = {}
    for f in files:
        m = SPAN_RE.search(f.stem)
        span = m.group(1) if m else _session_span(daydir)
        groups.setdefault(span, []).append(f)
    return groups


def import_media(media_dir=None, path=None, dry_run=False):
    """扫描 media 目录，把已存在的下载补进台账。

    返回 (新增节数, 已有节数, 无媒体目录数)。
    """
    media_dir = pathlib.Path(media_dir) if media_dir else (ROOT / "media")
    path = pathlib.Path(path) if path else LEDGER_PATH
    existing, _ = load(path)
    added = existed = skipped = 0
    new_entries = []
    if not media_dir.exists():
        return 0, 0, 0
    for course_dir in sorted(d for d in media_dir.iterdir() if d.is_dir()):
        for daydir in sorted(d for d in course_dir.iterdir() if d.is_dir()):
            if len(daydir.name) != 8 or not daydir.name.isdigit():
                continue
            groups = _media_groups(daydir)
            if not groups:
                skipped += 1
                continue
            for span, files in groups.items():
                k = key(course_dir.name, daydir.name, span)
                if k in existing:
                    existed += 1
                    continue
                new_entries.append({
                    "course": course_dir.name,
                    "date": daydir.name,
                    "span": span,
                    "video": any(f.suffix == ".mp4" for f in files),
                    "audio": any(f.suffix == ".m4a" for f in files),
                    "bytes": sum(f.stat().st_size for f in files),
                    "at": time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime(max(f.stat().st_mtime for f in files))),
                })
                added += 1
    if not dry_run and new_entries:
        with _LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                for e in new_entries:
                    fh.write(__import__("json").dumps(e, ensure_ascii=False) + "\n")
    return added, existed, skipped


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
    if "--import-media" in argv:
        added, existed, skipped = import_media(dry_run="--dry-run" in argv)
        tag = "预览" if "--dry-run" in argv else "已写入"
        print(f"[台账] 扫描 media 完成（{tag}）：新增 {added} 节，"
              f"已有 {existed} 节，无媒体目录 {skipped} 个")
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
