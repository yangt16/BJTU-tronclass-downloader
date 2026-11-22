"""校验下载台账（lists\\downloaded.jsonl）与预扫描的"曾下载但已删除"分类。

用法: python tools/test_ledger.py
"""
import contextlib
import io
import os
import pathlib
import shutil
import sys
import threading

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import ledger  # noqa: E402
import lectures  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

bad = 0


def check(name, got, want):
    global bad
    ok = got == want
    print(f"[{'PASS' if ok else 'FAIL'}] {name:38s} got={got!r} want={want!r}")
    if not ok:
        bad += 1


BASE = ROOT / "tmp" / f"testledger_{os.getpid()}"
shutil.rmtree(BASE, ignore_errors=True)
BASE.mkdir(parents=True)
LP = BASE / "downloaded.jsonl"


def url(date, span):
    return f"https://h/videos/outbound1/bjtu/room1/{date}/{span}/ENCODER-a?ts=1"


try:
    # ---------- 台账读写 ----------
    check("空台账", ledger.load(LP), ({}, 0))
    ledger.record("A课", "20261030", "101000-120500", True, True, 100, path=LP)
    ledger.record("A课", "20261104", "080000-095500", False, True, 50, path=LP)
    data, bad_lines = ledger.load(LP)
    check("记录数", len(data), 2)
    check("坏行数", bad_lines, 0)
    k1 = ledger.key("A课", "20261030", "101000-120500")
    check("key 含 span", k1, "A课|20261030|101000-120500")
    check("取到记录", data[k1]["video"], True)

    # 坏行忽略
    with open(LP, "a", encoding="utf-8") as fh:
        fh.write("not json\n")
    data, bad_lines = ledger.load(LP)
    check("坏行被忽略", (len(data), bad_lines), (2, 1))

    # ---------- 产物类型判断 ----------
    entry_both = {"video": True, "audio": True}
    entry_audio = {"video": False, "audio": True}
    entry_video = {"video": True, "audio": False}
    check("both 需要音视频", ledger.satisfies(entry_both, "both"), True)
    check("audio 记录不满足 both", ledger.satisfies(entry_audio, "both"), False)
    check("audio 模式满足 audio", ledger.satisfies(entry_audio, "audio"), True)
    check("video 记录满足 video", ledger.satisfies(entry_video, "video"), True)
    check("audio 记录不满足 video", ledger.satisfies(entry_audio, "video"), False)
    check("空记录不满足", ledger.satisfies(None, "both"), False)

    # ---------- 并发写台账 ----------
    LP2 = BASE / "conc.jsonl"
    threads = [threading.Thread(target=ledger.record,
                                args=("B课", f"2026110{i}", "", True, False, 1),
                                kwargs={"path": LP2})
               for i in range(1, 6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    data2, bad2 = ledger.load(LP2)
    check("多线程写入无丢行", (len(data2), bad2), (5, 0))

    # ---------- plan_sections：台账分类 ----------
    out = BASE / "media" / "C课"
    groups = {
        "20261030_101000-120500": [url("20261030", "101000-120500-1")],
        "20261104_080000-095500": [url("20261104", "080000-095500-1")],
    }
    lmap = {
        ledger.key("C课", "20261030", "101000-120500"):
            {"video": True, "audio": True},
    }
    todo, skipped, archived = lectures.plan_sections(
        groups, out, "both", "ENCODER", ledger_map=lmap, course="C课")
    check("台账命中 -> archived", len(archived), 1)
    check("另一节仍待下载", len(todo), 1)
    check("文件在时仍优先 skip",
          len(lectures.plan_sections(groups, out, "both", "ENCODER",
                                     ledger_map=lmap, course="C课")[1]), 0)

    # 模式不匹配：台账只有 audio，当前要 both -> 应下载
    lmap_audio = {ledger.key("C课", "20261030", "101000-120500"):
                  {"video": False, "audio": True}}
    todo2, _, archived2 = lectures.plan_sections(
        groups, out, "both", "ENCODER", ledger_map=lmap_audio, course="C课")
    check("产物类型不满足 -> 下载", (len(todo2), len(archived2)), (2, 0))

    # --redownload：不走台账
    todo3, _, archived3 = lectures.plan_sections(
        groups, out, "both", "ENCODER", ledger_map=lmap,
        redownload=True, course="C课")
    check("redownload 忽略台账", (len(todo3), len(archived3)), (2, 0))

    # ---------- 从 media 回填台账 ----------
    media_root = BASE / "backfill_media"
    d1 = media_root / "C1课" / "20261014"
    d1.mkdir(parents=True)
    (d1 / "X_20261014.mp4").write_bytes(b"v" * 100)
    (d1 / "X_20261014.m4a").write_bytes(b"a" * 50)
    (d1 / ".session").write_text("20261014_101000-120500", encoding="utf-8")

    d2 = media_root / "C1课" / "20261021"
    d2.mkdir(parents=True)
    (d2 / "X_20261021.m4a").write_bytes(b"a" * 60)
    (d2 / ".session").write_text("20261021_080000-095500", encoding="utf-8")

    d3 = media_root / "C2课" / "20261104"
    d3.mkdir(parents=True)
    (d3 / "Y_20261104_150100-160500.mp4").write_bytes(b"v" * 10)
    (d3 / "Y_20261104_162000-181500.mp4").write_bytes(b"v" * 20)

    (media_root / "C2课" / "20261105").mkdir(parents=True)   # 空目录

    BP = BASE / "backfill.jsonl"
    added, existed, skipped = ledger.import_media(
        media_dir=media_root, path=BP)
    check("回填新增节数", added, 4)
    check("回填跳过空目录", skipped, 1)
    data_b, bad_b = ledger.load(BP)
    check("回填记录数", len(data_b), 4)
    k1 = ledger.key("C1课", "20261014", "101000-120500")
    check("单场次时段来自 .session",
          (data_b[k1]["video"], data_b[k1]["audio"]), (True, True))
    k2 = ledger.key("C1课", "20261021", "080000-095500")
    check("纯音频日", (data_b[k2]["video"], data_b[k2]["audio"]), (False, True))
    k3 = ledger.key("C2课", "20261104", "150100-160500")
    k4 = ledger.key("C2课", "20261104", "162000-181500")
    check("多场次日拆两条", (k3 in data_b, k4 in data_b), (True, True))
    added2, existed2, _ = ledger.import_media(media_dir=media_root, path=BP)
    check("回填幂等", (added2, existed2), (0, 4))

    # ---------- main：菜单式询问（跳过分支）----------
    ledger.LEDGER_PATH = BASE / "main_ledger.jsonl"
    for d, sp in (("20261030", "101000-120500"), ("20261104", "080000-095500")):
        ledger.record("TC", d, sp, True, True, 10)

    class TTY(io.StringIO):
        def isatty(self):
            return True

    lst = BASE / "TC.txt"
    lst.write_text(url("20261030", "101000-120500-1") + "\n"
                   + url("20261104", "080000-095500-1") + "\n", encoding="utf-8")
    old_stdin = sys.stdin
    sys.stdin = TTY("1\n")          # 1 = 跳过
    lectures.FFMPEG = pathlib.Path(sys.executable)
    lectures.FFPROBE = pathlib.Path(sys.executable)
    old_argv = sys.argv
    sys.argv = ["lectures.py", "--urls", str(lst), "--dest",
                str(BASE / "media" / "TC"), "--jobs", "1"]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = lectures.main()
    finally:
        sys.argv = old_argv
        sys.stdin = old_stdin
    out_text = buf.getvalue()
    check("询问后跳过 -> 成功", rc, 0)
    check("提示曾下载", "[archived] 2 节" in out_text, True)
    check("小结含已删除记录", "已删除记录 2 节" in out_text, True)
finally:
    shutil.rmtree(BASE, ignore_errors=True)

print()
print("全部通过" if bad == 0 else f"{bad} 项失败")
sys.exit(0 if bad == 0 else 1)
