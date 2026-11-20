"""校验完整性检查、并发每节进度节流、以及 ffprobe 校验分支（不联网）。"""
import os
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import lectures  # noqa: E402

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


BASE = ROOT / "tmp" / f"testintegrity_{os.getpid()}"
shutil.rmtree(BASE, ignore_errors=True)
BASE.mkdir(parents=True)
probe = BASE / "fake_probe.py"
probe.write_text(
    "import os, sys\n"
    "mode = os.environ.get('FFPROBE_TEST_MODE', 'ok')\n"
    "if mode == 'err':\n"
    "    print('boom', file=sys.stderr)\n"
    "    sys.exit(1)\n"
    "print({'ok': '120.0', 'garbage': 'oops', 'short': '0.5'}[mode])\n",
    encoding="utf-8")
cmd = [sys.executable, str(probe)]

try:
    fake = BASE / "a.mp4"
    fake.write_bytes(b"x" * 1024)

    os.environ["FFPROBE_TEST_MODE"] = "ok"
    ok, why = lectures.check_media(fake, probe=cmd)
    check("正常时长 -> 通过", ok, True)
    check("说明含分钟", "分钟" in why, True)

    os.environ["FFPROBE_TEST_MODE"] = "short"
    ok, _ = lectures.check_media(fake, probe=cmd)
    check("时长过短 -> 失败", ok, False)

    os.environ["FFPROBE_TEST_MODE"] = "garbage"
    ok, _ = lectures.check_media(fake, probe=cmd)
    check("读不到时长 -> 失败", ok, False)

    os.environ["FFPROBE_TEST_MODE"] = "err"
    ok, _ = lectures.check_media(fake, probe=cmd)
    check("ffprobe 报错 -> 失败", ok, False)
    os.environ.pop("FFPROBE_TEST_MODE", None)

    ok, _ = lectures.check_media(fake, probe=[str(BASE / "no-such-probe")])
    check("ffprobe 不存在 -> 失败", ok, False)
finally:
    shutil.rmtree(BASE, ignore_errors=True)

# ---------- 并发每节进度的节流规则 ----------
check("首次进度要打印", lectures.progress_due(-1, 0, 0, 100), True)
check("1% 且 1 秒内 -> 不打印", lectures.progress_due(0, 100, 1, 100.5), False)
check("涨 5% -> 打印", lectures.progress_due(0, 100, 5, 100.5), True)
check("满 3 秒 -> 打印", lectures.progress_due(0, 100, 1, 104), True)
check("100% 必打", lectures.progress_due(96, 100, 100, 100.2), True)

print()
print("全部通过" if bad == 0 else f"{bad} 项失败")
sys.exit(0 if bad == 0 else 1)
