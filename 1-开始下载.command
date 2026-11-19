#!/bin/sh
# Start downloading. Double-click this file (macOS).
#
# No arguments: shows the interactive menu
#     product : video + audio / audio only / video only
#     scope   : all / one day / weekdays / exclude weekdays
#
# Drop a list file onto this icon: runs that list directly,
# default settings (video + audio, everything), no menu.
cd "$(dirname "$0")" || exit 1

if [ "$#" -gt 0 ]; then
    exec ./tools/getlec.sh "$@"
fi
exec ./tools/getlec.sh --menu
