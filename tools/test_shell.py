"""校验 shell 入口脚本的硬性规则（macOS / Linux）。

Windows 上跑不了 sh，所以这里只做静态检查，覆盖真正会坏的三件事：
  1. 没有 shebang            -> 双击没反应
  2. CRLF 换行               -> macOS 报 bad interpreter: /bin/sh^M
  3. 可执行位丢失（POSIX）   -> 双击提示权限不足

用法: python tools/test_shell.py
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

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


scripts = sorted(set(list(ROOT.glob("*.sh")) + list(ROOT.glob("*.command"))
                     + list((ROOT / "tools").glob("*.sh"))))
check("找到 shell 入口脚本", len(scripts) >= 6, f"实际 {len(scripts)} 个")

for p in scripts:
    raw = p.read_bytes()
    check(f"{p.name}: shebang", raw.startswith(b"#!/bin/sh"), raw[:20])
    check(f"{p.name}: 无 CRLF", b"\r\n" not in raw)
    if os.name != "nt":
        check(f"{p.name}: 可执行位", os.access(p, os.X_OK))

# 入口必须都转发到 tools/getlec.sh（避免逻辑重复）
for p in scripts:
    if p.name in ("getlec.sh", "0-首次安装.command"):
        continue
    text = p.read_text(encoding="utf-8", errors="replace")
    check(f"{p.name}: 调用 tools/getlec.sh", "./tools/getlec.sh" in text)

# 主脚本必须真的存在
check("tools/getlec.sh 存在", (ROOT / "tools" / "getlec.sh").exists())
check("tools/getlec.sh 调用 lectures.py",
      "tools/lectures.py" in (ROOT / "tools" / "getlec.sh").read_text(encoding="utf-8"))

print()
print("全部通过" if bad == 0 else f"{bad} 项失败")
sys.exit(0 if bad == 0 else 1)
