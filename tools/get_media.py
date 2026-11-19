"""
get_media.py - 分块下载 + 请求头基线。

媒体接口 ilesson.wh.bjtu.edu.cn 不校验 Cookie，只校验请求头：
    User-Agent, Referer, sec-ch-ua, sec-ch-ua-platform, sec-ch-ua-mobile
缺 sec-ch-ua 三项会 403。所以地址本身即可下载，无需登录态。

分块用 HTTP Range：
  * 断点续传（中断后从已有字节继续）
  * 失败只重下那一块（指数退避，最多 6 次）
  * 进度可见
"""
import json
import os
import re
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36 Edg/157.0.4341.42"),
    "Referer": "https://tronclass.wh.bjtu.edu.cn/",
    "Accept": "*/*",
    "sec-ch-ua": '"Not-A.Brand";v="99", "Microsoft Edge";v="157", "Chromium";v="157"',
    "sec-ch-ua-platform": '"Windows"',
    "sec-ch-ua-mobile": "?0",
}
CTX = ssl._create_unverified_context()
CHUNK = 8 * 1024 * 1024


def probe(url, timeout=60):
    """取 1 字节探活。返回 (是否可用, 总字节数, 错误说明)。"""
    h = dict(BASE_HEADERS, Range="bytes=0-0")
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=h),
                                   timeout=timeout, context=CTX)
        cr = r.headers.get("Content-Range") or ""
        r.close()
        m = re.search(r"/(\d+)", cr)
        total = int(m.group(1)) if m else 0
        if not total:
            return False, 0, "服务器未返回文件长度"
        return True, total, ""
    except urllib.error.HTTPError as e:
        return False, 0, f"HTTP {e.code}" + ("（链接可能已过期）" if e.code == 403 else "")
    except Exception as e:
        return False, 0, f"{type(e).__name__} {str(e)[:60]}"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


# 手动构造 opener：既要禁止自动跟随 302（我们要读 Location），
# 又要带上不校验证书的 HTTPSHandler（校园证书链不被系统信任）。
# 注意 OpenerDirector.open() 不接受 context 参数，只能这样注入。
_OPENER_NOREDIR = urllib.request.build_opener(
    _NoRedirect, urllib.request.HTTPSHandler(context=CTX))


def resolve(url, timeout=40):
    """把「间接地址」换成真正的媒体直链。

    incast 的 .../videos/<cameraId>/preview?previewToken=xxx 会 302 跳到
    ilesson 的签名地址（?ts=&token=）。这个 302 端点不需要登录态，
    所以本地程序可以自己换。已经是直链的地址原样返回。
    """
    if "previewToken=" not in url:
        return url
    req = urllib.request.Request(url, headers=BASE_HEADERS)
    try:
        r = _OPENER_NOREDIR.open(req, timeout=timeout)
        loc = r.headers.get("Location")
        r.close()
        if loc:
            return loc
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location")
        if loc:
            return loc
    except Exception:
        pass
    return url


SEG_MAX = 8          # 单文件最多拆几段
SEG_CONN_MAX = 8     # 节级并发 × 分段数 的连接总数上限


def seg_state_path(out):
    """分段进度旁路文件：X.mp4.segstate（下完会删掉）。"""
    return out.parent / (out.name + ".segstate")


def _save_state(path, state):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    os.replace(tmp, path)


def download_segmented(url, out_path, segments=4, quiet=False):
    """同一个文件用多个连接分段下载；各段写各自的字节区间，下完就是完整文件。

    进度存在 X.mp4.segstate 里：中途中断后重跑会从各段的断点继续。
    """
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    state_path = seg_state_path(out)

    ok, total, err = probe(url)
    if not ok:
        raise RuntimeError(f"无法访问媒体地址: {err}")
    if out.exists() and out.stat().st_size == total and not state_path.exists():
        if not quiet:
            print("已经下完，跳过")
        return out

    n = max(1, min(int(segments), SEG_MAX))
    per = (total + n - 1) // n
    state = {"total": total, "n": n, "done": [0] * n}
    if state_path.exists():
        try:
            old = json.loads(state_path.read_text(encoding="utf-8"))
            if (old.get("total") == total and old.get("n") == n
                    and len(old.get("done", [])) == n):
                state = old
                if not quiet:
                    print(f"[seg] 接着上次的分段进度（已下 {sum(state['done'])/1e6:.1f} MB）")
        except Exception:
            pass

    with open(out, "ab") as fh:
        fh.truncate(total)      # 预占位，避免各段互相扩文件

    lock = threading.Lock()
    progress = {"bytes": sum(state["done"])}
    t0 = time.time()

    def report():
        if quiet:
            return
        done = progress["bytes"]
        el = time.time() - t0
        print(f"  {done/1e6:8.1f}/{total/1e6:.1f} MB  {done/total*100:5.1f}%"
              f"  {done/el/1e6 if el else 0:5.1f} MB/s", end="\r", flush=True)

    def worker(i):
        start = i * per
        end = min(total, start + per)
        fh = open(out, "r+b", buffering=0)
        try:
            pos = start + state["done"][i]
            fh.seek(pos)
            while pos < end:
                chunk_end = min(pos + CHUNK - 1, end - 1)
                h = dict(BASE_HEADERS, Range=f"bytes={pos}-{chunk_end}")
                data = b""
                for attempt in range(6):
                    try:
                        r = urllib.request.urlopen(
                            urllib.request.Request(url, headers=h),
                            timeout=120, context=CTX)
                        data = r.read()
                        break
                    except Exception as ex:
                        if attempt == 5:
                            raise RuntimeError(f"第 {i+1} 段 {pos} 字节处连续失败: {ex}")
                        if not quiet:
                            with lock:
                                print(f"\n  第 {i+1} 段重试 {attempt+1}/5: {type(ex).__name__}")
                        time.sleep(2 * (attempt + 1))
                if not data:
                    raise RuntimeError(f"第 {i+1} 段读到 0 字节（{pos}）")
                fh.write(data)
                pos += len(data)
                with lock:
                    state["done"][i] = pos - start
                    progress["bytes"] += len(data)
                    _save_state(state_path, state)
                    report()
        finally:
            fh.close()

    if not quiet:
        print(f"总长 {total/1e6:.1f} MB  分 {n} 段并发下载")
    with ThreadPoolExecutor(max_workers=n) as pool:
        list(pool.map(worker, range(n)))

    size = out.stat().st_size
    if size != total:
        raise RuntimeError(f"下载后大小不对: {size} != {total}")
    try:
        state_path.unlink()
    except Exception:
        pass
    if not quiet:
        print()
        print(f"完成 {out}  {size/1e6:.1f} MB  用时 {time.time()-t0:.0f}s（{n} 段）")
    return out


def download(url, out_path, quiet=False, segments=1):
    """按块下载到 out_path，已存在的部分会续传。

    quiet=True 时不打印进度（多节并发下载时用，避免输出互相踩）。
    segments>1 时走单文件多连接分段下载。
    """
    if segments and int(segments) > 1:
        return download_segmented(url, out_path, int(segments), quiet=quiet)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    ok, total, err = probe(url)
    if not ok:
        raise RuntimeError(f"无法访问媒体地址: {err}")
    have = out.stat().st_size if out.exists() else 0
    if have > total:
        out.unlink()
        have = 0
    if not quiet:
        print(f"总长 {total/1e6:.1f} MB  已有 {have/1e6:.1f} MB")
    if have == total:
        if not quiet:
            print("已经下完，跳过")
        return out

    t0 = time.time()
    with open(out, "ab" if have else "wb") as fh:
        while have < total:
            end = min(have + CHUNK - 1, total - 1)
            h = dict(BASE_HEADERS, Range=f"bytes={have}-{end}")
            for attempt in range(6):
                try:
                    r = urllib.request.urlopen(urllib.request.Request(url, headers=h),
                                               timeout=120, context=CTX)
                    fh.write(r.read())
                    fh.flush()
                    break
                except Exception as ex:
                    if attempt == 5:
                        raise RuntimeError(f"第 {have} 字节处连续失败: {ex}")
                    if not quiet:
                        print(f"  重试 {attempt+1}/5: {type(ex).__name__} {str(ex)[:60]}")
                    time.sleep(2 * (attempt + 1))
            have = out.stat().st_size
            if not quiet:
                el = time.time() - t0
                print(f"  {have/1e6:8.1f}/{total/1e6:.1f} MB  {have/total*100:5.1f}%"
                      f"  {have/el/1e6 if el else 0:5.1f} MB/s", end="\r", flush=True)
    if not quiet:
        print()
        print(f"完成 {out}  {out.stat().st_size/1e6:.1f} MB  用时 {time.time()-t0:.0f}s")
    return out
