#!/bin/sh
# Audio only: extract m4a, then delete the mp4 to save space.
cd "$(dirname "$0")" || exit 1
GETLEC_DROPVIDEO=1; export GETLEC_DROPVIDEO
GETLEC_NOAUDIO=; export GETLEC_NOAUDIO
exec ./getlec.sh "$@"
