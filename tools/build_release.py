"""
build_release.py - 打一个"下载解压就能用"的 Windows 发布包。

包含：
  * 仓库里所有跟踪文件（源码 + 文档 + 书签）
  * bin\\ffmpeg.exe + bin\\ffprobe.exe（约 340 MB 解压后，压缩后约 200 MB）
  * START-HERE.txt / LICENSE-ffmpeg.txt / COPYING.GPLv3.txt
  * 空的 lists\\

为什么不含 media\\ 和 har_archive\\：那是用户数据，且含签名地址。

用法:
    python tools\\build_release.py                 # 版本号取 git describe
    python tools\\build_release.py --version v3    # 指定版本
    python tools\\build_release.py --no-gpl-text   # 不发 GPL 全文（不推荐）

产物: release\\tronclass-downloader-<版本>-win64.zip
"""
import argparse
import pathlib
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
RELEASE = ROOT / "release"
ASSETS = RELEASE / "assets"
# GPL 全文：官方站偶尔 403，备一个镜像
GPL_URLS = [
    "https://www.gnu.org/licenses/gpl-3.0.txt",
    "https://raw.githubusercontent.com/gcc-mirror/gcc/master/COPYING3",
]

START_HERE = """\
课程回放下载器 · Windows 版
================================

这是一份已经装好 ffmpeg 的完整包，解压后即可使用。

第一步（一次性）
---------------
双击 setup.cmd
  它会检测 Python、确认 ffmpeg 就绪、建好 lists\\ 文件夹。
  本包已含 ffmpeg，所以这一步只需几秒。

第二步：拿到课程地址
-------------------
方式 A（推荐）：装书签
   1. 用 Edge 打开 dist\\install.html
   2. 把页面里的蓝色按钮拖到书签栏
   3. 打开课程的「直播」列表页，点一下书签，会下载一个 <课程名>.txt

方式 B（手动）：自己复制播放地址
   见 docs\\使用说明.md 的「手动版」一节。

第三步：下载
-----------
双击以下任一个：
   下视频和音频.cmd     视频 + 音轨都留（默认）
   只要音轨.cmd         只留音轨，省空间（只做转写用这个）
   只要视频.cmd         只留视频
   只下某一天.cmd       只下指定的某一天

产物在 media\\<课程名>\\<日期>\\ 下。

详细文档
--------
README.md              项目简介
docs\\使用说明.md       完整手册（含故障排查）
"""
START_HERE_MAC = """\
课程回放下载器 · macOS / Linux 版
================================

本包不含 ffmpeg（macOS 上用 Homebrew 装，别在包里带二进制）。

第一步（一次性）
---------------
在“终端”里进入本文件夹，然后：

    chmod +x *.command *.sh
    brew install ffmpeg python3      # Linux: sudo apt install ffmpeg python3
    ./setup.command

  setup.command 会检查 python3 与 ffmpeg、建好 lists/ 文件夹。

第二步：拿到课程地址
-------------------
方式 A（推荐）：装书签
   1. 用 Chrome / Edge 打开 dist/install.html
   2. 把页面里的蓝色按钮拖到书签栏
   3. 打开课程的「直播」列表页，点一下书签，会下载一个 <课程名>.txt

方式 B（手动）：自己复制播放地址
   见 docs/使用说明.md 的「手动版」一节。

第三步：下载
-----------
双击以下任一个（Finder 里就是中文名字的 .command 文件）：
   下视频和音频.command     视频 + 音轨都留（默认）
   只要音轨.command         只留音轨，省空间（只做转写用这个）
   只要视频.command         只留视频
   只下某一天.command       只下指定的某一天

若双击提示“无法验证开发者”：右键文件，选“打开”，再确认一次。
若提示权限不足：终端里执行 chmod +x *.command *.sh

产物在 media/<课程名>/<日期>/ 下。

详细文档
--------
README.md              项目简介
docs/使用说明.md       完整手册（含故障排查）
"""


def zip_write(z, path, arcname, executable=False):
    """写入 zip；脚本保留 755，其他 644（mac 上解压后可直接双击）。"""
    zi = zipfile.ZipInfo.from_file(str(path), arcname)
    mode = 0o755 if executable else 0o644
    zi.external_attr = (0o100000 | mode) << 16
    zi.compress_type = zipfile.ZIP_DEFLATED
    with open(path, "rb") as f:
        z.writestr(zi, f.read())


LICENSE_FFMPEG = """\
这个发布包内含 FFmpeg 可执行文件（ffmpeg.exe / ffprobe.exe）。

FFmpeg 来源与版本
-----------------
    项目：FFmpeg (https://ffmpeg.org/)
    版本：见 bin\\ffmpeg.exe -version 的输出
    构建：gyan.dev 的 release-essentials Windows 构建
          (https://www.gyan.dev/ffmpeg/builds/)
    许可证：GPL v3（该构建启用了 GPL 组件）

本发行包未修改 FFmpeg 二进制，仅原样打包分发。完整许可证文本见
COPYING.GPLv3.txt；FFmpeg 源码可从 https://ffmpeg.org/download.html
或其镜像获取。

FFmpeg 是独立的第三方程序，本项目的 MIT/学习用途声明不覆盖它。
"""


def git(*args, **kw):
    r = subprocess.run(["git", "-C", str(ROOT)] + list(args),
                       capture_output=True, **kw)
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} 失败: {r.stderr.decode('utf-8', 'replace')}")
    return r.stdout


def tracked_files():
    out = git("-c", "core.quotepath=false", "ls-files", "-z")
    return [p for p in out.decode("utf-8").split("\0") if p]


def version_of(arg):
    if arg:
        return arg
    try:
        return git("describe", "--tags", "--always", "--dirty").decode().strip()
    except SystemExit:
        return "dev"


def ensure_assets(no_gpl):
    ASSETS.mkdir(parents=True, exist_ok=True)
    sh = ASSETS / "START-HERE.txt"
    lf = ASSETS / "LICENSE-ffmpeg.txt"
    sh.write_text(START_HERE, encoding="utf-8")
    lf.write_text(LICENSE_FFMPEG, encoding="utf-8")

    gpl = ASSETS / "COPYING.GPLv3.txt"
    if no_gpl:
        return sh, lf, None
    if not gpl.exists() or gpl.stat().st_size < 1000:
        for url in GPL_URLS:
            print(f"[release] 下载 GPL 全文: {url}")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=40) as r:
                    data = r.read()
                if len(data) > 10000:
                    gpl.write_bytes(data)
                    break
            except Exception as e:
                print(f"[release]   失败（{type(e).__name__}），换下一个")
        if not (gpl.exists() and gpl.stat().st_size > 10000):
            print("[release] GPL 全文拿不到，包里不放；LICENSE-ffmpeg.txt 里已给出链接")
            return sh, lf, None
    if gpl.stat().st_size < 1000:
        return sh, lf, None
    return sh, lf, gpl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="")
    ap.add_argument("--platform", choices=["win", "mac"], default="win",
                    help="win = 内置 ffmpeg 的 Windows 包；mac = 不含 ffmpeg 的 macOS/Linux 包")
    ap.add_argument("--no-gpl-text", action="store_true")
    a = ap.parse_args()

    ver = version_of(a.version)
    win = (a.platform == "win")
    suffix = "win64" if win else "mac"
    name = f"tronclass-downloader-{ver}-{suffix}"
    out_zip = RELEASE / f"{name}.zip"
    RELEASE.mkdir(parents=True, exist_ok=True)

    ff = []
    if win:
        # Windows 包要自带 ffmpeg
        ff = [ROOT / "bin" / n for n in ("ffmpeg.exe", "ffprobe.exe")]
        missing = [p.name for p in ff if not p.exists()]
        if missing:
            raise SystemExit(f"缺少 {missing}；先跑一次 setup.cmd 再打包")
        sh, lf, gpl = ensure_assets(a.no_gpl_text)
        extras = [sh, lf, gpl]
    else:
        ASSETS.mkdir(parents=True, exist_ok=True)
        sh = ASSETS / "START-HERE-mac.txt"
        sh.write_text(START_HERE_MAC, encoding="utf-8")
        extras = [sh]

    if out_zip.exists():
        out_zip.unlink()

    files = tracked_files()
    # .cmd 必须 CRLF / .sh 必须 LF，否则解压出来的入口会坏
    for f in files:
        raw = (ROOT / f).read_bytes()
        if f.lower().endswith(".cmd") and b"\r\n" not in raw:
            raise SystemExit(f"{f} 不是 CRLF，先在仓库里修好再打包")
        if f.endswith((".sh", ".command")) and b"\r\n" in raw:
            raise SystemExit(f"{f} 含 CRLF（mac 会报 bad interpreter）")

    total = 0
    with zipfile.ZipFile(out_zip, "w") as z:
        for f in files:
            src = ROOT / f
            if not src.exists():
                print(f"[release] 跳过不存在的跟踪文件: {f}")
                continue
            exec_bit = f.endswith((".sh", ".command"))
            zip_write(z, src, f"{name}/{f}", executable=exec_bit)
            total += 1
        for p in ff:
            zip_write(z, p, f"{name}/bin/{p.name}")
            total += 1
        for extra in extras:
            if extra and extra.exists():
                arc = f"{name}/START-HERE.txt" if extra.name.startswith("START-HERE") else f"{name}/{extra.name}"
                zip_write(z, extra, arc)
                total += 1
        # 空中目录：解压后就有 lists/，省得用户自己建
        z.writestr(f"{name}/lists/", "")

    size = out_zip.stat().st_size / 1e6
    print(f"\n[release] {out_zip}")
    print(f"[release] {size:.1f} MB，{total} 个文件，版本 {ver}，平台 {a.platform}")
    if size > 1900:
        print("[release] 警告：超过 GitHub Releases 单文件 2 GB 上限")
    return 0


if __name__ == "__main__":
    sys.exit(main())
