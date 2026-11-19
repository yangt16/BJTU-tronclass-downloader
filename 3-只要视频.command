#!/bin/sh
# Video only: no audio extraction, keep the mp4 as-is.
cd "$(dirname "$0")" || exit 1
GETLEC_DROPVIDEO=; export GETLEC_DROPVIDEO
GETLEC_NOAUDIO=1; export GETLEC_NOAUDIO
exec ./tools/getlec.sh "$@"
