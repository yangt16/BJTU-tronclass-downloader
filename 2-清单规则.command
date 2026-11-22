#!/bin/sh
# Configure per-course download rules (lists/<course>.rules).
# Double-click, pick a course, pick a rule. No rule = download all.
cd "$(dirname "$0")" || exit 1

PY=""
for cand in ./python/bin/python3 python3 python; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys" >/dev/null 2>&1; then
        PY="$cand"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "[rules] ERROR: Python 3 not found."
    echo "        macOS: brew install python    Linux: sudo apt install python3"
    printf "\nPress Enter to close..."
    read -r _ || true
    exit 9009
fi

"$PY" ./tools/rules.py "$@"
RC=$?
if [ -z "${GETLEC_NOPAUSE:-}" ]; then
    printf "\nPress Enter to close..."
    read -r _ || true
fi
exit $RC
