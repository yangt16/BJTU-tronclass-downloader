#!/bin/sh
# tools/getlec.sh - download lectures listed in lists/*.txt (macOS / Linux)
#
# Same engine as getlec.cmd, just POSIX shell. Modes come from the same
# environment variables: GETLEC_DROPVIDEO / GETLEC_NOAUDIO / GETLEC_ONLY /
# GETLEC_EXCLUDE / GETLEC_JOBS / GETLEC_FORCE / GETLEC_KEEPLIST / GETLEC_DRYRUN.
#
# usage (run from the project root):
#   sh tools/getlec.sh                 everything in lists/
#   sh tools/getlec.sh lists/MYCOURSE.txt    only that list
#   sh tools/getlec.sh lists/X.txt INSTRUCTOR  another track
#   sh tools/getlec.sh --menu                  interactive menu
set -u

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT" || exit 1

# ---------- find python ----------
PY=""
for cand in "$ROOT/python/bin/python3" python3 python; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys" >/dev/null 2>&1; then
        PY="$cand"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "[getlec] ERROR: Python 3 not found."
    echo "         macOS: brew install python    (or python.org installer)"
    echo "         Linux: sudo apt install python3"
    if [ -z "${GETLEC_NOPAUSE:-}" ]; then printf "\nPress Enter to close..."; read -r _ || true; fi
    exit 9009
fi

if [ "${1:-}" = "--menu" ]; then
    "$PY" "$ROOT/tools/menu.py"
    exit $?
fi

# ---------- mode flags ----------
ARGS=""
[ "${GETLEC_DRYRUN:-}" = "1" ] && ARGS="$ARGS --dry-run"
[ "${GETLEC_DROPVIDEO:-}" = "1" ] && ARGS="$ARGS --drop-video"
[ "${GETLEC_NOAUDIO:-}" = "1" ] && ARGS="$ARGS --no-audio"
[ "${GETLEC_KEEPLIST:-}" = "1" ] && ARGS="$ARGS --keep-list"
[ "${GETLEC_FORCE:-}" = "1" ] && ARGS="$ARGS --force"
[ -n "${GETLEC_ONLY:-}" ] && ARGS="$ARGS --only $GETLEC_ONLY"
[ -n "${GETLEC_EXCLUDE:-}" ] && ARGS="$ARGS --exclude $GETLEC_EXCLUDE"
[ -n "${GETLEC_JOBS:-}" ] && ARGS="$ARGS --jobs $GETLEC_JOBS"

FIRST="${1:-}"
TRACK="${2:-ENCODER}"

if [ ! -f "$ROOT/tools/lectures.py" ]; then
    echo "[getlec] ERROR: tools/lectures.py not found"
    exit 1
fi

run_one() {
    LIST="$1"
    [ -f "$LIST" ] || LIST="$ROOT/$1"
    if [ ! -f "$LIST" ]; then
        echo "[getlec] SKIP missing: $1"
        return 0
    fi
    echo "============================================================"
    echo "[getlec] LIST $LIST"
    echo "[getlec] track=$TRACK"
    echo "============================================================"
    # shellcheck disable=SC2086
    "$PY" "$ROOT/tools/lectures.py" --urls "$LIST" --track "$TRACK" $ARGS
    return 0
}

if [ -z "$FIRST" ] || [ "$FIRST" = "--all" ]; then
    echo "[getlec] BATCH mode over $ROOT/lists"
    echo
    "$PY" "$ROOT/tools/lists.py"
    FOUND=0
    for f in "$ROOT"/lists/*.txt; do
        [ -e "$f" ] || continue
        FOUND=1
        run_one "$f"
    done
    if [ "$FOUND" -eq 0 ]; then
        echo "[getlec] nothing to do"
    fi
else
    run_one "$FIRST"
fi

echo
"$PY" "$ROOT/tools/make_index.py"

if [ -z "${GETLEC_NOPAUSE:-}" ]; then
    printf "\nPress Enter to close..."
    read -r _ || true
fi
exit 0
