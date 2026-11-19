"""校验日志 tee、时长格式化、日志目录选择，以及 --log 的端到端行为。

不联网：用 example.invalid 的假地址 + --dry-run。
CI 上 runner 没有 ffmpeg，所以测试里临时造一个假的放进 PATH，
让 lectures.py 的启动检查通过。

用法: python tools/test_log.py
"""
import io
import os
import pathlib
import shutil
import subprocess
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


def check(name, ok, detail=""):
    global bad
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        bad += 1


# ---------- fmt_dur ----------
check("fmt_dur 0 秒", lectures.fmt_dur(0) == "0s", lectures.fmt_dur(0))
check("fmt_dur 59 秒", lectures.fmt_dur(59) == "59s", lectures.fmt_dur(59))
check("fmt_dur 65 秒", lectures.fmt_dur(65) == "1m05s", lectures.fmt_dur(65))
check("fmt_dur 3725 秒", lectures.fmt_dur(3725) == "1h02m", lectures.fmt_dur(3725))
check("fmt_dur 负数", lectures.fmt_dur(-5) == "0s", lectures.fmt_dur(-5))

# ---------- _Tee ----------
a, b = io.StringIO(), io.StringIO()
tee = lectures._Tee(a, b)
tee.write("hello")
tee.flush()
check("_Tee 同时写两路", a.getvalue() == "hello" and b.getvalue() == "hello",
      f"{a.getvalue()!r} {b.getvalue()!r}")
check("_Tee isatty 为假", tee.isatty() is False)

# ---------- pick_log_dir ----------
os.environ.pop("GETLEC_LOG", None)
check("无参数无环境变量 -> None", lectures.pick_log_dir("") is None)
os.environ["GETLEC_LOG"] = "1"
check("GETLEC_LOG=1 -> logs/", lectures.pick_log_dir("") == ROOT / "logs",
      str(lectures.pick_log_dir("")))
os.environ.pop("GETLEC_LOG", None)
check("显式 --log 优先", lectures.pick_log_dir("tmp/x") == pathlib.Path("tmp/x"),
      str(lectures.pick_log_dir("tmp/x")))

# ---------- 端到端：--log 是否真的落盘 ----------
BASE = ROOT / "tmp" / f"testlog_{os.getpid()}"
shutil.rmtree(BASE, ignore_errors=True)
BASE.mkdir(parents=True, exist_ok=True)
fake = BASE / "fakebin"
fake.mkdir()
if os.name == "nt":
    (fake / "ffmpeg.cmd").write_text("@exit /b 0\r\n", encoding="ascii")
else:
    p = fake / "ffmpeg"
    p.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    p.chmod(0o755)

urls = BASE / "list.txt"
urls.write_text(
    "https://example.invalid/videos/o/site/20261111/080000-095500-1/ENCODER-x?ts=1\n",
    encoding="utf-8")
logs = BASE / "mylogs"

env = dict(os.environ)
env["PATH"] = str(fake) + os.pathsep + env.get("PATH", "")
env.pop("GETLEC_LOG", None)
r = subprocess.run(
    [sys.executable, str(HERE / "lectures.py"), "--urls", str(urls),
     "--dry-run", "--log", str(logs)],
    capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)

check("--log 运行成功", r.returncode == 0, (r.stderr or r.stdout)[-200:])
log_files = sorted(logs.glob("*.log")) if logs.exists() else []
check("生成日志文件", len(log_files) == 1, str(logs))
if log_files:
    text = log_files[0].read_text(encoding="utf-8", errors="replace")
    check("日志包含 [mode]", "[mode]" in text)
    check("日志包含落点", "[dest]" in text)
    check("日志文件名含课程名", log_files[0].name.startswith("list_"), log_files[0].name)

shutil.rmtree(BASE, ignore_errors=True)

print()
print("全部通过" if bad == 0 else f"{bad} 项失败")
sys.exit(0 if bad == 0 else 1)
