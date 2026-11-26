#!/bin/sh
# Update to the latest GitHub release. Keeps data folders (media/lists/...).
cd "$(dirname "$0")" || exit 1

PY=""
for cand in ./python/bin/python3 python3 python; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys" >/dev/null 2>&1; then
        PY="$cand"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "[update] ERROR: Python 3 not found."
    echo "        macOS: brew install python    Linux: sudo apt install python3"
    printf "\nPress Enter to close..."
    read -r _ || true
    exit 1
fi

"$PY" ./tools/update.py "$@"
RC=$?
if [ -z "${GETLEC_NOPAUSE:-}" ]; then
    printf "\nPress Enter to close..."
    read -r _ || true
fi
exit $RC
