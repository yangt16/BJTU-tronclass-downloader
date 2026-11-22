#!/bin/sh
# 0-首次安装.command - one-time setup for macOS / Linux.
# Double-click this file in Finder (macOS) or run ./0-首次安装.command.
set -u

ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT" || exit 1

echo "============================================================"
echo " course-notes setup (macOS / Linux)"
echo " root: $ROOT"
echo "============================================================"
echo

# ---------- 1. python ----------
PY=""
for cand in "$ROOT/python/bin/python3" python3 python; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys" >/dev/null 2>&1; then
        PY="$cand"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "[setup] ERROR: Python 3 not found."
    echo "        macOS: brew install python    (or python.org installer)"
    echo "        Linux: sudo apt install python3"
    printf "\nPress Enter to close..."
    read -r _ || true
    exit 1
fi
echo "[setup] step 1/3: python"
echo "  $PY  $("$PY" -V 2>&1)"
echo

# ---------- 2. ffmpeg ----------
echo "[setup] step 2/3: ffmpeg"
FF=""
if [ -x "$ROOT/bin/ffmpeg" ]; then
    FF="$ROOT/bin/ffmpeg"
elif command -v ffmpeg >/dev/null 2>&1; then
    FF=$(command -v ffmpeg)
fi
if [ -z "$FF" ]; then
    echo "  ffmpeg NOT found."
    echo
    echo "  macOS:  brew install ffmpeg"
    echo "  Linux:  sudo apt install ffmpeg"
    echo
    echo "  装好后重新双击本文件即可。"
    printf "\nPress Enter to close..."
    read -r _ || true
    exit 1
fi
echo "  $FF"
echo "  $("$FF" -hide_banner -version 2>/dev/null | head -1)"
if ! command -v ffprobe >/dev/null 2>&1 && [ ! -x "$ROOT/bin/ffprobe" ]; then
    echo "  WARNING: ffprobe not found (通常和 ffmpeg 一起装)"
fi
echo

# ---------- 3. lists folder ----------
echo "[setup] step 3/3: lists folder"
mkdir -p "$ROOT/lists"
echo "  ok: $ROOT/lists"
echo

echo "============================================================"
echo " setup done."
echo
echo " next:"
echo "   1. put a course list into lists/ (see docs/使用说明.md)"
echo "   2. double-click 1-开始下载.command in this folder"
echo "        a menu will ask: product, scope, jobs, segments"
echo "   3. per-course rules: double-click 2-清单规则.command"
echo "============================================================"
printf "\nPress Enter to close..."
read -r _ || true
exit 0
