"""校验清单归档行为：跑完归档到 har_archive，lists 里不再留 txt。

不联网、不碰真实 media/ 与 lists/：
  * 把 lectures.ROOT 指到临时目录（har_archive 也落在那里）
  * 把 make_index.rebuild 换成空函数（避免写真实 lists/）
"""
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


def check(name, ok, detail=""):
    global bad
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        bad += 1


BASE = ROOT / "tmp" / f"testarchive_{os.getpid()}"
FAKE_ROOT = BASE / "root"
LISTS = FAKE_ROOT / "lists"
OUT = FAKE_ROOT / "media" / "XX课程"
shutil.rmtree(BASE, ignore_errors=True)
LISTS.mkdir(parents=True)
(OUT / "20261111").mkdir(parents=True)
(OUT / "20261111" / "XX课程_20261111.mp4").write_bytes(b"x" * 1024)

# 打桩：ROOT 指到临时目录；make_index 不写真实目录
real_root = lectures.ROOT
import make_index  # noqa: E402
real_rebuild = make_index.rebuild
lectures.ROOT = FAKE_ROOT
make_index.rebuild = lambda outdir: None

try:
    src = LISTS / "XX课程.txt"
    src.write_text("# 清单\nhttps://x/20261111/080000-095500-1/ENCODER-a?ts=1\n",
                   encoding="utf-8")
    lectures.archive_list(str(src), ["20261111"], OUT)

    arc = FAKE_ROOT / "har_archive"
    files = sorted(arc.glob("urls_*.txt")) if arc.exists() else []
    check("归档文件已生成", len(files) == 1, [f.name for f in files])
    check("归档内容是原清单", "ENCODER-a" in files[0].read_text(encoding="utf-8") if files else False)
    check("lists 里的 txt 已移走", not src.exists())
    check("没有重建空模板", not (LISTS / "XX课程.txt").exists())

    # 同日期再归档一次：不能覆盖已有归档
    src2 = LISTS / "XX课程.txt"
    src2.write_text("# 清单2\nhttps://x/20261112/080000-095500-1/ENCODER-b?ts=1\n",
                    encoding="utf-8")
    lectures.archive_list(str(src2), ["20261111"], OUT)
    files2 = sorted(arc.glob("urls_*.txt"))
    check("重复日期不覆盖旧归档", len(files2) == 2, [f.name for f in files2])

    # 拖拽场景：清单来自 lists 之外（例如下载文件夹）
    outside = BASE / "download"
    outside.mkdir()
    src3 = outside / "YY课程.txt"
    src3.write_text("# 清单3\nhttps://x/20261113/080000-095500-1/ENCODER-c?ts=1\n",
                    encoding="utf-8")
    out2 = FAKE_ROOT / "media" / "YY课程"
    (out2 / "20261113").mkdir(parents=True)
    (out2 / "20261113" / "YY课程_20261113.mp4").write_bytes(b"x" * 1024)
    lectures.archive_list(str(src3), ["20261113"], out2)
    check("外部清单也被归档移走", not src3.exists())
    check("外部清单归档成功", any("20261113" in f.name for f in arc.glob("urls_*.txt")))
finally:
    lectures.ROOT = real_root
    make_index.rebuild = real_rebuild
    shutil.rmtree(BASE, ignore_errors=True)

print()
print("全部通过" if bad == 0 else f"{bad} 项失败")
sys.exit(0 if bad == 0 else 1)
