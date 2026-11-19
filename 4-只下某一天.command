#!/bin/sh
# Download only ONE DAY (or several days) of lectures.
# Ask for a date, then run the normal batch with a filter.
#
#   20261030              one day
#   20261030,20261104     several days
#   (empty)               no filter, download everything
cd "$(dirname "$0")" || exit 1

echo "============================================================"
echo " Download only selected day(s)"
echo "============================================================"
printf "Date(s) to download - YYYYMMDD, comma for several, empty=all: "
IFS= read -r DAY || DAY=""

if [ -n "$DAY" ]; then
    case "$DAY" in
        *[!0-9,]*)
            echo
            echo "[day] ERROR: bad input: \"$DAY\""
            echo "      Use 8 digits, e.g. 20261030 or 20261030,20261104"
            printf "\nPress Enter to close..."
            read -r _ || true
            exit 1
            ;;
    esac
    echo "[day] only: $DAY"
    GETLEC_ONLY="$DAY"; export GETLEC_ONLY
else
    echo "[day] no filter, downloading everything"
fi

exec ./tools/getlec.sh "$@"
