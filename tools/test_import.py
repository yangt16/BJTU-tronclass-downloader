"""校验 import_lists 的收编/合并逻辑（不联网、不碰真实 lists\\）。

覆盖：
  * 下载目录里的抓取清单 -> 合并进 lists\\<课程>.txt
  * 同名清单已存在 -> 按 URL 去重合并，老地址不丢
  * lists\\ 里的 "课程 (1).txt" 副本 -> 并入 "课程.txt" 并删除副本
  * 非抓取文件（普通 txt）-> 忽略
  * --dry-run -> 不写盘

用法: python tools/test_import.py
"""
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import import_lists  # noqa: E402

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


U1 = "https://incast.example/api/videos/1/preview?previewToken=aaa"
U2 = "https://incast.example/api/videos/2/preview?previewToken=bbb"
U3 = "https://incast.example/api/videos/3/preview?previewToken=ccc"


def scraped(*urls):
    return "# 自动抓取\n" + "\n".join(urls) + "\n"


BASE = ROOT / "tmp" / f"testimport_{__import__('os').getpid()}"
DL = BASE / "dl"
LISTS = BASE / "lists"
shutil.rmtree(BASE, ignore_errors=True)
DL.mkdir(parents=True)
LISTS.mkdir(parents=True)

# 让脚本把 LISTS 指向临时目录（模块级变量，main/run 都用它）
import_lists.LISTS = LISTS

try:
    # 1) 下载目录 -> lists
    (DL / "XX课程.txt").write_text(scraped(U1, U2), encoding="utf-8")
    moved = import_lists.run([DL])
    dest = LISTS / "XX课程.txt"
    text = dest.read_text(encoding="utf-8") if dest.exists() else ""
    check("从下载目录收编", moved == 1 and U1 in text and U2 in text)
    check("源文件已移走", not (DL / "XX课程.txt").exists())

    # 2) 再来一份（含旧地址 + 新地址）-> 去重合并
    (DL / "XX课程.txt").write_text(scraped(U2, U3), encoding="utf-8")
    import_lists.run([DL])
    text = (LISTS / "XX课程.txt").read_text(encoding="utf-8")
    check("合并去重", text.count(U2) == 1 and U3 in text and U1 in text,
          [n for n in (U1, U2, U3) if n in text])

    # 3) lists 里出现 "XX课程 (1).txt" -> 并入主清单并删除副本
    (LISTS / "XX课程 (1).txt").write_text(scraped(U3, U1), encoding="utf-8")
    moved = import_lists.run([])
    text = (LISTS / "XX课程.txt").read_text(encoding="utf-8")
    check("合并 (1) 副本", moved == 1 and not (LISTS / "XX课程 (1).txt").exists())
    check("副本内容已并入", text.count(U1) == 1 and text.count(U3) == 1)

    # 4) 普通 txt（不含 previewToken）被忽略
    (DL / "笔记.txt").write_text("随便写点东西\n", encoding="utf-8")
    moved = import_lists.run([DL])
    check("忽略非抓取文件", moved == 0 and (DL / "笔记.txt").exists())

    # 5) dry-run 不写盘
    (DL / "YY课程.txt").write_text(scraped(U1), encoding="utf-8")
    moved = import_lists.run([DL], dry_run=True)
    check("dry-run 报告会处理", moved == 1)
    check("dry-run 不落盘", not (LISTS / "YY课程.txt").exists())
    check("dry-run 不删源文件", (DL / "YY课程.txt").exists())
finally:
    shutil.rmtree(BASE, ignore_errors=True)

print()
print("全部通过" if bad == 0 else f"{bad} 项失败")
sys.exit(0 if bad == 0 else 1)
