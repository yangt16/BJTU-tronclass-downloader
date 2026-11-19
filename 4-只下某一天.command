#!/bin/sh
# Download only selected day(s) or weekday(s).
# Ask for a date or a weekday number, then run the normal batch with a filter.
#
#   20261030              one day
#   20261030,20261104     several days
#   4                     every Thursday (1=Mon .. 7=Sun)
#   2,4                   Monday and Thursday
#   (empty)               no filter, download everything
cd "$(dirname "$0")" || exit 1

echo "============================================================"
echo " Download only selected day(s) / weekday(s)"
echo "============================================================"
printf "Date 20261030 or weekday 1-7 (1=Mon..7=Sun), comma ok, empty=all: "
IFS= read -r DAY || DAY=""

if [ -n "$DAY" ]; then
    case "$DAY" in
        *[!0-9,]*)
            echo
            echo "[day] ERROR: bad input: \"$DAY\""
            echo "      Use 8-digit date (20261030) or weekday 1-7 (1=Mon..7=Sun), comma for several"
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
