"""
build_installer.py - 用 Inno Setup 6 打 Windows 安装包（内置 Python 3.11 + ffmpeg）。

产物: release\\课程回放下载器-安装包.exe  （文件名不带版本号，方便用固定链接）

流程:
  1. 确保有 <版本>-win64.zip（没有就调用 build_release.py 现打）
  2. 解压到 tmp\\installer-stage\\，再把 Python 嵌入版解压到 stage\\python\\
  3. 用 stage\\python\\python.exe 冒烟跑一遍 tools\\menu.py
     （嵌入式 Python 不会把脚本目录加进 sys.path，这里坏了安装后就是双击闪退）
  4. 生成只含 #define 的包装 .iss（#include installer\\app.iss），调用 ISCC 编译

用法:
    python tools\\build_installer.py                    # 版本号取 git describe
    python tools\\build_installer.py --version v4.4      # 指定版本
    python tools\\build_installer.py --python-zip D:\\python-3.11.9-embed-amd64.zip
    python tools\\build_installer.py --iscc "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe"

前置: Inno Setup 6（用户级安装即可）。Python 嵌入版缺失时会自动从 python.org 下载。
"""
import argparse
import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "installer"
RELEASE = ROOT / "release"
TMP = ROOT / "tmp"
STAGE = TMP / "installer-stage"
WRAPPER = TMP / "installer" / "build.iss"
PY_EMBED_CACHE = TMP / "python-embed.zip"
PY_EMBED_URL = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
EXE_NAME = "课程回放下载器-安装包.exe"


def version_of(arg):
    if arg:
        return arg.strip()
    r = subprocess.run(["git", "-C", str(ROOT), "describe", "--tags", "--always", "--dirty"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip() or "dev"


def normalize_version(ver):
    """4.4 -> v4.4（release 包名和 tag 都带 v，update.py 也是按 v 拼 URL 的）。"""
    return "v" + ver if re.fullmatch(r"\d+(?:\.\d+)*", ver) else ver


def full_version(ver):
    """Inno 要求 x.x.x.x 的数字版本。v4.3 -> 4.3.0.0"""
    parts = (re.findall(r"\d+", ver) + ["0", "0", "0"])[:3]
    return ".".join(parts + ["0"])


def win_zip(ver):
    path = RELEASE / f"tronclass-downloader-{ver}-win64.zip"
    if path.exists():
        print(f"[installer] 用现成的 win64 包: {path.name}")
        return path
    print(f"[installer] 没有 {path.name}，先调用 build_release.py 打一个")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "build_release.py"),
                        "--version", ver, "--platform", "win"])
    if r.returncode != 0 or not path.exists():
        raise SystemExit("[installer] 打 win64 包失败")
    return path


def embed_zip(arg):
    if arg:
        path = pathlib.Path(arg)
        if not path.exists():
            raise SystemExit(f"[installer] 找不到 Python 嵌入版: {path}")
        return path
    if PY_EMBED_CACHE.exists() and PY_EMBED_CACHE.stat().st_size > 5_000_000:
        print(f"[installer] 用缓存的 Python 嵌入版: {PY_EMBED_CACHE}")
        return PY_EMBED_CACHE
    PY_EMBED_CACHE.parent.mkdir(parents=True, exist_ok=True)
    print(f"[installer] 下载 Python 嵌入版: {PY_EMBED_URL}")
    req = urllib.request.Request(PY_EMBED_URL,
                                 headers={"User-Agent": "tronclass-downloader-build"})
    with urllib.request.urlopen(req, timeout=180) as r, open(PY_EMBED_CACHE, "wb") as fh:
        shutil.copyfileobj(r, fh)
    return PY_EMBED_CACHE


def prepare_stage(zip_path, py_zip):
    shutil.rmtree(STAGE, ignore_errors=True)
    STAGE.mkdir(parents=True, exist_ok=True)
    print(f"[installer] 解压程序文件到 {STAGE}")
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            parts = name.split("/", 1)
            if len(parts) < 2 or not parts[1]:
                continue                     # 顶层目录本身
            dest = STAGE / parts[1]
            if name.endswith("/"):
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(dest, "wb") as fh:
                shutil.copyfileobj(src, fh)
    print("[installer] 解压 Python 嵌入版到 stage\\python")
    with zipfile.ZipFile(py_zip) as z:
        z.extractall(STAGE / "python")


def smoke_stage():
    py = STAGE / "python" / "python.exe"
    if not py.exists():
        raise SystemExit("[installer] stage 里没有 python\\python.exe")
    env = dict(os.environ, GETLEC_DRYRUN="1", GETLEC_NOPAUSE="1")
    r = subprocess.run([str(py), str(STAGE / "tools" / "menu.py")],
                       cwd=str(STAGE), env=env, input="1\n1\n1\n1\n",
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=180)
    if r.returncode != 0 or "ModuleNotFoundError" in r.stderr:
        print(r.stdout[-800:])
        print(r.stderr[-800:])
        raise SystemExit("[installer] 嵌入式 Python 跑不动 menu.py（装完会闪退），先修再打")
    # 冒烟会在 stage 里留下 .menu.json 和 tools\__pycache__，别带进安装包
    junk = [STAGE / ".menu.json", *STAGE.rglob("__pycache__")]
    for p in junk:
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
    print("[installer] 冒烟通过: 嵌入式 Python 能启动 menu.py")


def write_wrapper(ver, full):
    WRAPPER.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "; 由 tools\\build_installer.py 生成，请勿手改",
        f'#define MyAppVersion "{ver.lstrip("v")}"',
        f'#define MyAppFullVersion "{full}"',
        f'#define StageDir "{STAGE}"',
        f'#define OutputDir "{RELEASE}"',
        f'#define SetupIcon "{INSTALLER / "app.ico"}"',
        f'#include "{INSTALLER / "app.iss"}"',
        "",
    ]
    WRAPPER.write_text("\n".join(lines), encoding="utf-8-sig")
    return WRAPPER


def find_iscc(arg):
    cands = []
    if arg:
        cands.append(arg)
    if os.environ.get("INNO_ISCC"):
        cands.append(os.environ["INNO_ISCC"])
    if os.environ.get("LOCALAPPDATA"):
        cands.append(os.path.join(os.environ["LOCALAPPDATA"],
                                  "Programs", "Inno Setup 6", "ISCC.exe"))
    for name in ("ProgramFiles(x86)", "ProgramFiles"):
        if os.environ.get(name):
            cands.append(os.path.join(os.environ[name], "Inno Setup 6", "ISCC.exe"))
    found = shutil.which("ISCC")
    if found:
        cands.append(found)
    for c in cands:
        if c and pathlib.Path(c).exists():
            return pathlib.Path(c)
    raise SystemExit("[installer] 找不到 ISCC.exe：装 Inno Setup 6，或用 --iscc 指定")


def report():
    exe = RELEASE / EXE_NAME
    if not exe.exists():
        raise SystemExit(f"[installer] 编译结束但没找到 {exe}")
    h = hashlib.sha256()
    with open(exe, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    print(f"\n[installer] {exe}")
    print(f"[installer] {exe.stat().st_size / 1048576:.2f} MiB")
    print(f"[installer] SHA256 {h.hexdigest().upper()}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="用 Inno Setup 6 打 Windows 安装包")
    ap.add_argument("--version", default="", help="版本号（默认 git describe）")
    ap.add_argument("--python-zip", default="", help="自备 Python 嵌入版 zip")
    ap.add_argument("--iscc", default="", help="ISCC.exe 路径")
    a = ap.parse_args(argv)

    ver = normalize_version(version_of(a.version))
    full = full_version(ver)
    print(f"[installer] 版本 {ver}（{full}）")

    zip_path = win_zip(ver)
    prepare_stage(zip_path, embed_zip(a.python_zip))
    smoke_stage()
    iss = write_wrapper(ver, full)
    iscc = find_iscc(a.iscc)
    print(f"[installer] 编译: {iscc}")
    r = subprocess.run([str(iscc), str(iss)])
    if r.returncode != 0:
        raise SystemExit(f"[installer] ISCC 失败（退出码 {r.returncode}）")
    report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
