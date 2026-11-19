#!/bin/sh
# Download video AND audio, keep both. This is the default mode.
cd "$(dirname "$0")" || exit 1
GETLEC_DROPVIDEO=; export GETLEC_DROPVIDEO
GETLEC_NOAUDIO=; export GETLEC_NOAUDIO
exec ./tools/getlec.sh "$@"
