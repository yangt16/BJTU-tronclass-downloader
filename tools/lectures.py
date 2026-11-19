"""
lectures.py - 主编排：清单 → 下载 → 抽音轨 → 命名 → 归档 → 刷新索引。

唯一入口是 lists\\<科目>.txt（每行一个播放地址）。
清单名就是课程名：lists\\X.txt -> media\\X\\X_<日期>.mp4 + .m4a

媒体地址不含登录信息，只靠请求头就能下（见 get_media.BASE_HEADERS）。

用法:
    python lectures.py --urls lists\\X.txt
    python lectures.py --urls lists\\X.txt --track INSTRUCTOR
    python lectures.py --urls lists\\X.txt --dest D:\\courses\\db
    python lectures.py --urls lists\\X.txt --dry-run      # 只打印路径，不写盘
"""
import argparse
import pathlib
import re
import datetime
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from get_media import SEG_CONN_MAX, SEG_MAX, download, resolve  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ROOT = tools/ 的父目录。整套东西可搬到任意位置而不用改代码。
ROOT = pathlib.Path(__file__).resolve().parent.parent


class _Tee:
    """把输出同时写到控制台和日志文件。"""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            try:
                st.write(s)
                st.flush()
            except Exception:
                pass
        return len(s)

    def flush(self):
        for st in self.streams:
            try:
                st.flush()
            except Exception:
                pass

    def isatty(self):
        return False


def fmt_dur(sec):
    """秒数 -> 1h02m / 3m05s / 42s。"""
    sec = int(max(0, sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def pick_log_dir(arg):
    """--log 参数 / GETLEC_LOG=1 环境变量 -> 日志目录（None = 不写日志）。"""
    if arg:
        return pathlib.Path(arg)
    if os.environ.get("GETLEC_LOG") == "1":
        return ROOT / "logs"
    return None


def _exe(name):
    """优先用 ROOT\\bin 下的，找不到再退回 PATH。"""
    local = ROOT / "bin" / f"{name}.exe"
    if local.exists():
        return local
    found = shutil.which(name)
    return pathlib.Path(found) if found else local


FFMPEG = _exe("ffmpeg")
FFPROBE = _exe("ffprobe")


# ---------------- 落点 ---------------- #

DUP_SUFFIX = re.compile(r"\s*\(\d+\)$")


def clean_course_name(stem):
    """去掉浏览器/资源管理器重名后缀：'X (1)' -> 'X'。"""
    return DUP_SUFFIX.sub("", stem).strip() or stem


def resolve_outdir(args, urls_file=""):
    """落点完全由清单文件名决定：lists\\X.txt -> media\\X\\

    --dest 可以覆盖（相对本程序或绝对路径）；直接调用本脚本且没给 --dest 时，
    也按清单文件名推。
    """
    if getattr(args, "dest", ""):
        return ROOT / args.dest
    if urls_file:
        return ROOT / "media" / clean_course_name(pathlib.Path(urls_file).stem)
    return ROOT / "media"


def course_name(outdir):
    """课程名 = 落点目录的末级名。落点退化到 media 本身时用通用名。"""
    name = getattr(outdir, "name", "") or ""
    return name if name and name.lower() != "media" else "课程"


# ---------------- 地址与命名 ---------------- #


def label_of(url):
    """从 .../<日期>/<HHMMSS-HHMMSS-id>/<file> 取出 'YYYYMMDD_HHMMSS-HHMMSS'。"""
    parts = url.split("?")[0].split("/")
    try:
        date = parts[-3]
        span = parts[-2].split("-")
        return f"{date}_{span[0]}-{span[1]}"
    except Exception:
        return "lecture"


def group_by_label(urls):
    """按「日期+时段」分组，而不是按完整目录。

    为什么不能用目录分组：同一节课的三条轨可能被存在**不同目录**里
    （实测：20261111 / 20261023 / 20261106 的 INSTRUCTOR/STUDENTS 就在
    另一个目录下），按目录分会把一节课裂成两组，白白多跑一轮。
    日期+时段是这一节课的稳定标识。
    """
    groups = {}
    for u in urls:
        groups.setdefault(label_of(u), []).append(u)
    return groups


WEEKDAY_CN = {"1": "周一", "2": "周二", "3": "周三", "4": "周四",
              "5": "周五", "6": "周六", "7": "周日"}


def weekday_of(date):
    """'20261030' -> 5（1=周一 … 7=周日）；日期非法返回 0。"""
    try:
        d = datetime.date(int(date[0:4]), int(date[4:6]), int(date[6:8]))
    except Exception:
        return 0
    return d.isoweekday()


def spec_label(spec):
    """把 1-7 显示成"周四"，其余原样。"""
    return WEEKDAY_CN.get(spec, spec)


def parse_specs(values):
    """把 --only / --exclude 的值拆成列表。

    支持重复传参（--only A --only B）和逗号分隔（--only A,B），
    中文逗号也认。空值忽略。
    """
    out = []
    for v in values or []:
        for part in str(v).replace("，", ",").split(","):
            part = part.strip()
            if part and part not in out:
                out.append(part)
    return out


def match_label(label, specs):
    """label 是否命中任一 spec。

    spec 可以是：
      * 日期       20261030         -> 命中这一天的所有节
      * 星期几     4                -> 命中所有周四的节（1=周一 … 7=周日）
      * 完整标签   20261030_101000-120500
      * 前缀       20261030_10      -> 命中当天 10 点档
    """
    date = label.split("_")[0]
    wd = weekday_of(date)
    for s in specs:
        if len(s) == 1 and s in WEEKDAY_CN:
            if wd == int(s):
                return True
            continue
        if label.startswith(s) or date == s:
            return True
    return False


def filter_groups(groups, only, exclude):
    """按日期/标签筛选。返回 (新 groups, 说明文字)。"""
    before = len(groups)
    if only:
        groups = {k: v for k, v in groups.items() if match_label(k, only)}
    if exclude:
        groups = {k: v for k, v in groups.items() if not match_label(k, exclude)}
    note = ""
    if only or exclude:
        bits = []
        if only:
            bits.append("只要 " + ",".join(spec_label(s) for s in only))
        if exclude:
            bits.append("排除 " + ",".join(spec_label(s) for s in exclude))
        note = f"{'；'.join(bits)}：{before} 节 -> {len(groups)} 节"
    return groups, note


def track_of(url):
    """从 <TRACK>-<b64>?ts=... 认出是哪条轨。"""
    name = url.split("?")[0].rsplit("/", 1)[-1]
    return name.split("-")[0].upper() or "MEDIA"


def labels_parts(label):
    """'20261014_150100-160500' -> ('20261014', '150100-160500')"""
    date, _, span = label.partition("_")
    return date, span


def target_paths(outdir, label):
    """命名规则。

    一天一节:  <课程>_<YYYYMMDD>.mp4 / .m4a
    一天多节:  <课程>_<YYYYMMDD>_<时段>.mp4 / .m4a   （有 .multi 标记时）

    落点:  [dest]\\<YYYYMMDD>\\
    文件名带课程名，因为上传工具只显示文件名、不显示路径。
    """
    date, span = labels_parts(label)
    d = outdir / date
    base = f"{course_name(outdir)}_{date}"
    if (d / ".multi").exists() and span:
        base += f"_{span}"
    return d / f"{base}.mp4", d / f"{base}.m4a"


def guard_previous(daydir, label, course, date):
    """处理"同一天第二节课"，返回当天是否已有多节。

    - .session 记录的场次和本次不同 -> 判定为多节
    - 把旧的、还不带时段的名字改写成带时段
    - 打 .multi 标记，之后 target_paths() 会给新文件也带时段
    - 已带时段的文件不动，避免二次改名
    """
    tag = daydir / ".session"
    # utf-8-sig 容忍 BOM：PowerShell 写过的文件可能带 BOM
    old = tag.read_text(encoding="utf-8-sig").strip() if tag.exists() else ""
    collided = bool(old) and old != label
    multi = (daydir / ".multi").exists() or collided

    if collided:
        _, oldspan = labels_parts(old)
        oldspan = oldspan or "old"
        for p in sorted(daydir.glob("*.mp4")) + sorted(daydir.glob("*.m4a")):
            if re.search(r"_\d{6}-\d{6}$", p.stem):     # 已带时段，跳过
                continue
            dst = daydir / f"{course}_{date}_{oldspan}{p.suffix}"
            if p != dst and not dst.exists():
                p.replace(dst)
                print(f"  ! 同一天有第二节课，旧文件改名为 {dst.name}")

    daydir.mkdir(parents=True, exist_ok=True)
    if multi:
        (daydir / ".multi").write_text("1", encoding="utf-8")
    tag.write_text(label, encoding="utf-8")
    return multi


def load_urls(path):
    """读清单：一行一个地址，忽略空行和 # 注释。"""
    out = []
    for line in pathlib.Path(path).read_text(encoding="utf-8-sig").splitlines():
        u = line.strip()
        if not u or u.startswith("#"):
            continue
        if not u.lower().startswith("http"):
            print(f"  ! 跳过非 URL 行: {u[:60]}")
            continue
        out.append(u)
    print(f"[urls] {path} 里读到 {len(out)} 条地址")
    return out


# ---------------- 媒体处理 ---------------- #

def extract_audio(mp4, m4a):
    """音频流直接复制，不重编码。"""
    r = subprocess.run(
        [str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(mp4), "-vn", "-c:a", "copy", "-movflags", "+faststart", str(m4a)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"  !! ffmpeg 失败: {(r.stderr or '')[:300]}")
        return False
    return True


def info_of(path):
    r = subprocess.run(
        [str(FFPROBE), "-v", "error",
         "-show_entries", "format=duration,size:stream=codec_type,codec_name",
         "-of", "default=noprint_wrappers=1", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip()


# ---------------- 主流程 ---------------- #

def archive_list(urls_file, dates, outdir):
    """归档已跑完的清单，并从 lists\\ 移走（lists 里只保留 .md 索引）。"""
    src = pathlib.Path(urls_file)
    arc = ROOT / "har_archive"
    arc.mkdir(exist_ok=True)
    name = "urls_" + "_".join(sorted(set(dates))) + ".txt"
    dest = arc / name
    if dest.exists():
        dest = arc / f"urls_{'_'.join(sorted(set(dates)))}_{int(time.time())}.txt"
    src.replace(dest)
    print(f"\n[archive] 清单已归档 -> {dest.name}（lists 里不再保留 txt）")
    try:
        import make_index
        idx = make_index.rebuild(outdir)     # 必须传本次落点，不能用默认
        if idx:
            print(f"[archive] 已刷新下载清单 {idx}")
    except Exception as e:
        print(f"[archive] 刷新清单失败: {e}")


def already_done(mp4, m4a, mode="both"):
    """本地已有完整产物 —— 只查文件系统，不联网。

    mode 决定"完成"的标准：
      both  : mp4 + m4a 都在（默认）
      audio : 只有 m4a（音轨模式跑完会删掉 mp4）
      video : 只有 mp4（只要视频模式不抽音轨）
      any   : 任一个在（给预检用，判断"这节碰过没"）
    """
    def ok(p):
        try:
            return p.exists() and p.stat().st_size > 0
        except Exception:
            return False

    if mode == "audio":
        return ok(m4a)
    if mode == "video":
        return ok(mp4)
    if mode == "any":
        return ok(m4a) or ok(mp4)
    return ok(mp4) and ok(m4a)


DEFAULT_JOBS = 2
MAX_JOBS = 4
PRINT_LOCK = threading.Lock()


def resolve_jobs(arg, env=None):
    """--jobs / GETLEC_JOBS -> 1..MAX_JOBS，默认 DEFAULT_JOBS。"""
    raw = arg if arg not in (None, "") else (env or os.environ).get("GETLEC_JOBS", "")
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = DEFAULT_JOBS
    return max(1, min(MAX_JOBS, n))


def resolve_segments(arg, env=None):
    """--segments / GETLEC_SEGMENTS -> 1..SEG_MAX，默认 1（关闭）。"""
    raw = arg if arg not in (None, "") else (env or os.environ).get("GETLEC_SEGMENTS", "")
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = 1
    return max(1, min(n, SEG_MAX))


def effective_segments(arg, jobs, env=None):
    """分段数与节级并发组合后，总连接数不超过 SEG_CONN_MAX。"""
    seg = resolve_segments(arg, env)
    return min(seg, max(1, SEG_CONN_MAX // max(1, jobs)))


def plan_sections(groups, outdir, mode, track, force=False, dry_run=False):
    """串行确定每节的落点、处理同一天多节改名、判断是否已下载。

    命名和改名都在这里一次做完，下载阶段只管传数据 —— 这样多节并发时
    才不会互相改文件名。
    返回 (todo, skipped_dates)；dry_run 时 todo 只用于打印。
    """
    todo, skipped = [], []
    for label, us in groups.items():
        want = [u for u in us if track_of(u) == track.upper()]
        pick = want[0] if want else us[0]
        date = labels_parts(label)[0]

        if dry_run:
            mp4, m4a = target_paths(outdir, label)
            print(f"\n=== 第 {len(todo) + 1}/{len(groups)} 节: {label}"
                  f"  轨: {[track_of(u) for u in us]} ===")
            print(f"  将写入: {mp4}")
            if mode != "video":
                print(f"          {m4a}")
            todo.append({"label": label, "date": date, "pick": pick, "urls": us,
                         "mp4": mp4, "m4a": m4a})
            continue

        outdir.mkdir(parents=True, exist_ok=True)
        guard_previous(outdir / date, label, course_name(outdir), date)
        mp4, m4a = target_paths(outdir, label)
        if not force and already_done(mp4, m4a, mode):
            skipped.append(date)
            continue
        todo.append({"label": label, "date": date, "pick": pick, "urls": us,
                     "mp4": mp4, "m4a": m4a})
    return todo, skipped


def notify_done():
    """跑完提示：终端响铃 + Windows 提示音 / macOS beep。"""
    try:
        print("\a", end="", flush=True)
    except Exception:
        pass
    if os.name == "nt":
        try:
            import winsound
            winsound.MessageBeep()
        except Exception:
            pass
    elif sys.platform == "darwin":
        try:
            subprocess.run(["osascript", "-e", "beep"], capture_output=True, timeout=5)
        except Exception:
            pass


def write_failed_log(jobs, outdir):
    """把本次失败的节写进 logs\\，方便回看。返回路径或 None。"""
    if not jobs:
        return None
    try:
        d = ROOT / "logs"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"failed_{outdir.name}_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        lines = ["# 下载失败的节（重跑同一份清单会自动跳过已完成的）"]
        for j in jobs:
            lines.append(f"# {j['label']}")
            lines.append(j["pick"])
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", required=True, help="每行一个媒体地址的 txt")
    ap.add_argument("--track", default="ENCODER", help="ENCODER / INSTRUCTOR / STUDENTS")
    ap.add_argument("--dest", default="", help="落点，相对本程序或绝对路径")
    ap.add_argument("--drop-video", action="store_true", help="抽完音轨就删 mp4")
    ap.add_argument("--no-audio", action="store_true", help="只要视频，不抽音轨")
    ap.add_argument("--dry-run", action="store_true", help="只打印路径，不写盘")
    ap.add_argument("--force", action="store_true", help="已下载的也重做")
    ap.add_argument("--keep-list", action="store_true",
                    help="跑完不动清单（不归档、不重建），适合长期维护的增量清单")
    ap.add_argument("--only", action="append", default=[], metavar="日期/1-7",
                    help="只下指定日期、星期几(1=周一..7=周日)或标签，可重复或用逗号分隔，"
                         "如 20261030 或 4")
    ap.add_argument("--exclude", action="append", default=[], metavar="日期/1-7",
                    help="跳过指定的日期/标签，写法同 --only")
    ap.add_argument("--log", default="", metavar="DIR",
                    help="把输出同时写进 DIR 下的日志文件（也可设 GETLEC_LOG=1 用默认 logs/）")
    ap.add_argument("--jobs", default="", metavar="N",
                    help=f"并发下载的节数，1-{MAX_JOBS}（默认 {DEFAULT_JOBS}；也可设 GETLEC_JOBS）")
    ap.add_argument("--segments", default="", metavar="N",
                    help=f"只下一两节时，单个文件再拆 N 段下载，1-{SEG_MAX}"
                         "（默认 1 = 关闭；也可设 GETLEC_SEGMENTS）")
    a = ap.parse_args()

    # 缺 ffmpeg 时直接给一句人话，而不是等抽音轨阶段抛 FileNotFoundError
    if not (FFMPEG.exists() or shutil.which("ffmpeg")):
        print("[error] 没找到 ffmpeg，抽音轨需要它：")
        print("        macOS : brew install ffmpeg")
        print("        Windows: 双击 0-首次安装.cmd 自动下载")
        return 1

    # 落点由清单文件名决定：lists\X.txt -> media\X\
    outdir = resolve_outdir(a, a.urls)

    # 可选：输出同时写进日志文件（长任务跑完还能回看）。
    # 要在第一条输出之前装好，否则日志会漏掉开头几行。
    log_fh = None
    log_dir = pick_log_dir(a.log)
    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{outdir.name}_{time.strftime('%Y%m%d_%H%M%S')}.log"
            log_fh = open(log_file, "w", encoding="utf-8", newline="\n", buffering=1)
            sys.stdout = _Tee(sys.stdout, log_fh)
            sys.stderr = _Tee(sys.stderr, log_fh)
        except Exception as e:
            print(f"[log] 无法写日志: {e}")

    print(f"[dest] 落点: {outdir}")
    if log_fh:
        print(f"[log] 同时写入 {log_fh.name}")

    urls = load_urls(a.urls)
    if not urls:
        # 空清单是正常状态（比如先建好文件、之后再粘地址），不算失败
        print(f"  {a.urls} 里没有可用地址，跳过")
        return 0

    # 清单里可能是「间接地址」（incast 的 preview?previewToken=...）。
    # 它 302 到真正的签名直链，这个跳转不需要登录态，本地就能换。
    # 换过之后 URL 里才带日期/时段/轨道，才能命名和分组。
    if any("previewToken=" in u for u in urls):
        print(f"[resolve] 发现间接地址，换成直链（{len(urls)} 条）...")
        fixed = []
        for u in urls:
            r = resolve(u)
            if r != u:
                print(f"  {u[-42:]}  ->  {r[-46:]}")
            else:
                print(f"  {u[-42:]}  ->  (未变化，可能已过期)")
            fixed.append(r)
        urls = fixed

    groups = group_by_label(urls)

    # 按日期/标签筛选（--only / --exclude）
    only_specs = parse_specs(a.only)
    excl_specs = parse_specs(a.exclude)
    if only_specs or excl_specs:
        groups, note = filter_groups(groups, only_specs, excl_specs)
        print(f"[filter] {note}")
        if not groups:
            print("[filter] 没有符合条件的节。检查日期（20261030）或星期几（1-7）是否写对")
            return 0
        # 筛选模式下绝不归档清单：否则会把没处理的那些地址一起搬走
        if not a.keep_list:
            a.keep_list = True
            print("[filter] 已自动开启 --keep-list（筛选时不归档清单）")

    # 三种模式：都要 / 只要音轨 / 只要视频
    mode = "video" if a.no_audio else ("audio" if a.drop_video else "both")
    mode_cn = {"both": "视频 + 音轨", "audio": "只要音轨", "video": "只要视频"}[mode]
    print(f"[mode] {mode_cn}")

    jobs = resolve_jobs(a.jobs)
    segments = effective_segments(a.segments, jobs)
    extra = f"   单节 {segments} 段" if segments > 1 else ""
    print(f"[jobs] 并发 {jobs} 路{extra}")

    todo, skipped_dates = plan_sections(groups, outdir, mode, a.track,
                                        force=a.force, dry_run=a.dry_run)
    if a.dry_run:
        return 0

    done_dates = list(skipped_dates)
    n_skip = len(skipped_dates)
    if n_skip:
        print(f"[skip] 已下载 {n_skip} 节，本次实际需下载 {len(todo)} 节")

    counters = {"new": 0}
    failed_jobs = []
    t_start = time.time()

    def process_job(job, idx, total, retry=False):
        """下载并处理一节；返回 True 表示成功。"""
        prefix = "重试 " if retry else ""
        with PRINT_LOCK:
            print(f"\n=== {prefix}第 {idx}/{total} 节: {job['label']}"
                  f"  轨: {[track_of(u) for u in job['urls']]} ===")
            print(f"  [下载] -> {job['mp4'].name}")
        try:
            download(job["pick"], job["mp4"], quiet=jobs > 1, segments=segments)
        except Exception as e:
            with PRINT_LOCK:
                print(f"  下载失败: {e}")
            return False

        if mode == "video":
            with PRINT_LOCK:
                print(f"      视频 {job['mp4'].name}  {job['mp4'].stat().st_size/1e6:.1f} MB")
                print("  [信息]")
                print("      " + info_of(job["mp4"]).replace("\n", "\n      "))
                print(f"\n  视频用这个: {job['mp4']}")
            return True

        with PRINT_LOCK:
            print(f"  [抽音频] -> {job['m4a'].name}")
        if not extract_audio(job["mp4"], job["m4a"]):
            return False
        with PRINT_LOCK:
            print(f"      {job['m4a'].name}  {job['m4a'].stat().st_size/1e6:.1f} MB")
            if a.drop_video:
                freed = job["mp4"].stat().st_size
                job["mp4"].unlink()
                print(f"      已删除录像 {job['mp4'].name}，省回 {freed/1e6:.1f} MB")
            print("  [信息]")
            print("      " + info_of(job["m4a"]).replace("\n", "\n      "))
            print(f"\n  上传用这个: {job['m4a']}")
        return True

    def record(job, ok):
        """收尾统计 + 进度（加锁，线程安全）。"""
        with PRINT_LOCK:
            if ok:
                counters["new"] += 1
                done_dates.append(job["date"])
            else:
                failed_jobs.append(job)
            done = counters["new"] + len(failed_jobs)
            if done < len(todo):
                elapsed = time.time() - t_start
                eta = elapsed / done * (len(todo) - done)
                print(f"[进度] {done}/{len(todo)} 节  已用 {fmt_dur(elapsed)}"
                      f"  预计剩余 {fmt_dur(eta)}")

    def run_one(idx, job):
        record(job, process_job(job, idx, len(todo)))

    if jobs == 1:
        for idx, job in enumerate(todo, 1):
            run_one(idx, job)
    else:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            list(pool.map(lambda p: run_one(p[0], p[1]), enumerate(todo, 1)))

    # 失败节自动重试一轮（网络抖动很常见，一次就放弃太亏）
    retried = 0
    if failed_jobs:
        retried = len(failed_jobs)
        print(f"\n[retry] 有 {retried} 节失败，自动重试一轮 ...")
        again = list(failed_jobs)
        failed_jobs.clear()
        for idx, job in enumerate(again, 1):
            ok = process_job(job, idx, len(again), retry=True)
            if ok:
                with PRINT_LOCK:
                    counters["new"] += 1
                    done_dates.append(job["date"])
            else:
                with PRINT_LOCK:
                    failed_jobs.append(job)

    failed = len(failed_jobs)
    print(f"\n[小结] 新下载 {counters['new']} 节 / 跳过 {n_skip} 节 /"
          f" 失败 {failed} 节  用时 {fmt_dur(time.time() - t_start)}")
    if retried:
        print(f"[retry] {retried} 节重试，其中 {retried - failed} 节成功")
    if failed:
        fp = write_failed_log(failed_jobs, outdir)
        if fp:
            print(f"[failed] 失败清单已写入 {fp}")
    elif counters["new"]:
        notify_done()

    if log_fh:
        log_fh.flush()

    if failed or not done_dates:
        return 1 if failed else 0

    if a.keep_list:
        # 增量清单模式：清单原地保留，方便下周把新地址追加进来
        print(f"[list] 保留清单不动: {a.urls}")
        try:
            import make_index
            idx = make_index.rebuild(outdir)
            if idx:
                print(f"[list] 已刷新下载清单 {idx}")
        except Exception:
            pass
        return 0

    archive_list(a.urls, done_dates, outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
