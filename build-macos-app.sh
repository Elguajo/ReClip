#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

remove_build_path() {
    local path="$1"

    [ -e "$path" ] || return 0

    for _ in 1 2 3; do
        find "$path" -name .DS_Store -delete 2>/dev/null || true
        rm -rf "$path" 2>/dev/null && return 0
        sleep 0.2
    done

    rm -rf "$path"
}

if [ "$(uname -s)" != "Darwin" ]; then
    echo "This build script must be run on macOS."
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 was not found. Install it with: brew install python3"
    exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg was not found. Install it with: brew install ffmpeg"
    exit 1
fi

FFMPEG_BIN="$(command -v ffmpeg)"
FFPROBE_BIN="$(command -v ffprobe || true)"

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt -r requirements-build.txt

remove_build_path build
remove_build_path dist
rm -f ReClip.spec

pyinstaller_args=(
    --noconfirm
    --clean
    --windowed
    --name ReClip
    --osx-bundle-identifier com.local.reclip
    --icon ReClip.app/Contents/Resources/AppIcon.icns
    --add-data templates:templates
    --add-data static:static
    --add-binary "$FFMPEG_BIN:bin"
    --collect-all yt_dlp
    --collect-data certifi
    --hidden-import objc
    --hidden-import AppKit
    --hidden-import Foundation
    --hidden-import WebKit
)

if [ -n "$FFPROBE_BIN" ]; then
    pyinstaller_args+=(--add-binary "$FFPROBE_BIN:bin")
fi

python -m PyInstaller "${pyinstaller_args[@]}" native.py

echo ""
echo "Standalone app built at: dist/ReClip.app"
echo "Run it with: open dist/ReClip.app"
