"""校验 rules.py 的解析、优先级、CLI 与交互式配置（不联网）。

用法: python tools/test_rules.py
"""
import os
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import rules  # noqa: E402
import lectures  # noqa: E402
import ledger  # noqa: E402

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


BASE = ROOT / "tmp" / f"testrules_{os.getpid()}"
LISTS = BASE / "lists"
shutil.rmtree(BASE, ignore_errors=True)
LISTS.mkdir(parents=True)

try:
    # ---------- 路径映射 ----------
    check("规则文件路径", rules.rules_path_for(LISTS / "AA.txt").name, "AA.rules")

    # ---------- 解析 ----------
    tokens, errors = rules.normalize_tokens("4, 20261030，2")
    check("混合 token", tokens, ["4", "20261030", "2"])
    check("非法 token 报错", rules.normalize_tokens("8, x")[1], ["8", "x"])

    rule, errors = rules.load(LISTS / "none.rules")
    check("无规则文件 -> 空", (rule["only"], rule["exclude"], errors), ([], [], []))

    # ---------- 保存/读取 ----------
    path = LISTS / "AA.rules"
    rules.save(path, {"only": ["4"], "exclude": []})
    rule, errors = rules.load(path)
    check("保存后读回", (rule["only"], rule["exclude"]), (["4"], []))
    check("可读描述", rules.describe(rule), "只要 周四")
    check("文件含注释", "#" in path.read_text(encoding="utf-8"), True)

    rules.save(path, {"only": [], "exclude": ["2", "6"]})
    rule, _ = rules.load(path)
    check("排除多值", rules.describe(rule), "排除 周二, 周六")

    toks, errs = rules.normalize_tokens("20261030_101000-120500")
    check("完整标签也认", toks, ["20261030_101000-120500"])

    # ---------- 优先级 ----------
    got = rules.resolve_filters(["20261030"], [], {"only": ["4"], "exclude": []})
    check("规则优先于命令行", got, (["4"], [], "清单规则"))
    got = rules.resolve_filters(["20261030"], ["2"], {"only": [], "exclude": []})
    check("无规则用命令行", got, (["20261030"], ["2"], "命令行"))

    # ---------- 空规则=删除文件 ----------
    kept = rules.save(path, {"only": [], "exclude": []})
    check("清空后删文件", (kept, path.exists()), (False, False))

    # ---------- CLI：set / list / clear ----------
    (LISTS / "AA.txt").write_text(
        "https://h/videos/outbound1/bjtu/room1/20261030/080000-095500-1/ENCODER-a?ts=1\n",
        encoding="utf-8")
    (LISTS / "BB.txt").write_text(
        "# 注释\nhttps://h/videos/outbound1/bjtu/room1/20261104/080000-095500-1/ENCODER-b?ts=1\n",
        encoding="utf-8")

    EMPTY_MEDIA = BASE / "empty_media"
    EMPTY_MEDIA.mkdir(exist_ok=True)

    def run(*args, stdin=None, media=EMPTY_MEDIA):
        base = [sys.executable, str(HERE / "rules.py"),
                "--lists-dir", str(LISTS)]
        if media is not None:
            base += ["--media-dir", str(media)]
        return subprocess.run(base + list(args),
                              input=stdin, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", cwd=str(ROOT))

    r = run("set", "AA", "--exclude", "2")
    check("CLI set 成功", r.returncode, 0)
    check("CLI set 写文件", (LISTS / "AA.rules").exists(), True)

    r = run("list")
    check("CLI list 列出规则", "排除 周二" in r.stdout, True)

    r = run("set", "新课", "--only", "4")
    check("CLI set 无清单也允许", r.returncode, 0)
    check("无清单时规则已存", (LISTS / "新课.rules").exists(), True)

    r = run("clear", "AA")
    check("CLI clear 删除规则", (r.returncode, (LISTS / "AA.rules").exists()), (0, False))

    # ---------- 已下载但无清单的课程也能配 ----------
    media = BASE / "media"
    (media / "CC课程").mkdir(parents=True)
    found = rules.discover(LISTS, media_dir=media)
    names = {it["name"]: it for it in found}
    check("discover 含 media 课程", "CC课程" in names, True)
    check("media 课程无清单", names["CC课程"]["txt"], None)
    r = run("set", "CC课程", "--only", "4")
    check("无清单课程可 set", (r.returncode, (LISTS / "CC课程.rules").exists()),
          (0, True))

    # ---------- 交互式：手动输入课程名 ----------
    r = run(media=media, stdin="4\nDD课程\n2\n4\n")
    check("交互式手动建规则退出码", r.returncode, 0)
    rule, _ = rules.load(LISTS / "DD课程.rules")
    check("手动课程规则写入", rule["only"], ["4"])

    # ---------- 交互式（原有路径，EOF 当退出）----------
    r = run(stdin="1\n2\n4\n")   # 选第 1 门课 -> 只下星期几 -> 周四
    check("交互式退出码", r.returncode, 0)
    rule, _ = rules.load(LISTS / "AA.rules")
    check("交互式写规则", rule["only"], ["4"])

    # ---------- 修改规则：5 返回不改 / 回车沿用 / 覆盖 ----------
    rules.save(LISTS / "AA.rules", {"only": ["4"], "exclude": []})
    run(stdin="1\n6\nq\n")           # 选 AA -> 6 返回 -> q
    rule, _ = rules.load(LISTS / "AA.rules")
    check("6 返回不修改规则", rule["only"], ["4"])

    run(stdin="1\n2\n\nq\n")         # 选 AA -> 只下星期几 -> 空回车沿用 4
    rule, _ = rules.load(LISTS / "AA.rules")
    check("空回车沿用当前值", rule["only"], ["4"])

    run(stdin="1\n3\n2\nq\n")        # 改成排除周二
    rule, _ = rules.load(LISTS / "AA.rules")
    check("重新选择即覆盖", (rule["only"], rule["exclude"]), ([], ["2"]))
    rules.save(LISTS / "AA.rules", {"only": ["4"], "exclude": []})

    # ---------- 产物规则（mode）----------
    rules.save(LISTS / "AA.rules", {"only": [], "exclude": [], "mode": "audio"})
    rule, _ = rules.load(LISTS / "AA.rules")
    check("mode 读回", rule["mode"], "audio")
    check("mode 可读描述", rules.describe(rule), "产物 只要音频")
    check("resolve_mode 规则优先", rules.resolve_mode("both", rule),
          ("audio", "清单规则"))
    check("resolve_mode 无规则用命令行",
          rules.resolve_mode("both", {"only": [], "exclude": [], "mode": ""}),
          ("both", "命令行"))
    r = run("set", "AA", "--mode", "video")
    rule, _ = rules.load(LISTS / "AA.rules")
    check("CLI --mode 生效", (r.returncode, rule["mode"]), (0, "video"))
    rules.save(LISTS / "AA.rules", {"only": ["4"], "exclude": []})
    run(stdin="1\n5\n2\nq\n")       # 选 AA -> 设置产物 -> 只要音频
    rule, _ = rules.load(LISTS / "AA.rules")
    check("交互式设置产物", (rule["only"], rule["mode"]), (["4"], "audio"))

    # ---------- 一次会话配两门，然后按 q 退出 ----------
    r = run(stdin="1\n2\n4\n2\n3\n2\nq\n")
    check("多课程会话退出码", r.returncode, 0)
    rule_b, _ = rules.load(LISTS / "BB.rules")
    check("第二门规则写入", rule_b["exclude"], ["2"])
    check("退出提示", "[规则] 已退出" in r.stdout, True)
    # ---------- lectures 接入：清单规则优先 ----------
    import contextlib
    import io

    T = BASE / "conv"
    T.mkdir()
    LST = T / "XX课程.txt"
    LST.write_text(
        "https://h/videos/outbound1/bjtu/room1/20261029/080000-095500-1/ENCODER-a?ts=1\n"
        "https://h/videos/outbound1/bjtu/room1/20261030/080000-095500-1/ENCODER-b?ts=1\n",
        encoding="utf-8")
    rules.save(T / "XX课程.rules",
               {"only": ["4"], "exclude": [], "mode": "audio"})  # 只下周四 + 只要音频

    # 没有 ffmpeg/ffprobe 的机器（CI）也能跑 dry-run：把启动检查指到 python
    ledger.LEDGER_PATH = BASE / "rules_ledger.jsonl"
    lectures.FFMPEG = pathlib.Path(sys.executable)
    lectures.FFPROBE = pathlib.Path(sys.executable)
    old_argv = sys.argv
    sys.argv = ["lectures.py", "--urls", str(LST), "--dry-run",
                "--dest", str(T / "out")]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = lectures.main()
    finally:
        sys.argv = old_argv
    out = buf.getvalue()
    check("接入后运行成功", rc, 0)
    check("打印了清单规则", "[rule] 使用清单规则" in out, True)
    check("只保留周四那一节", "20261029" in out and "20261030" not in out, True)
    check("规则产物覆盖命令行", "[mode] 只要音轨（清单规则）" in out, True)
finally:
    shutil.rmtree(BASE, ignore_errors=True)

print()
print("全部通过" if bad == 0 else f"{bad} 项失败")
sys.exit(0 if bad == 0 else 1)
