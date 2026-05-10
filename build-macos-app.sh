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

# --- bgutil POT provider bundle (Node + JS generate_once.js) -----------------
# Bundled into Resources/bin/node and Resources/bgutil-server/ so yt-dlp can
# bypass YouTube's bot check via Brainicism/bgutil-ytdlp-pot-provider in
# script mode. Cached under .build-cache/ to keep rebuilds fast.

NODE_VERSION="22.20.0"
BGUTIL_REF="1.3.1"
CACHE_DIR="$(pwd)/.build-cache"
NODE_DIR="${CACHE_DIR}/node-v${NODE_VERSION}-darwin-arm64"
NODE_BIN="${NODE_DIR}/bin/node"
BGUTIL_SRC="${CACHE_DIR}/bgutil-ytdlp-pot-provider"
BGUTIL_SERVER_BUILT="${BGUTIL_SRC}/server/build/generate_once.js"

mkdir -p "${CACHE_DIR}"

if [ ! -x "${NODE_BIN}" ]; then
    echo "Downloading Node.js v${NODE_VERSION} (arm64) ..."
    curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-darwin-arm64.tar.gz" \
        -o "${CACHE_DIR}/node.tar.gz"
    rm -rf "${NODE_DIR}"
    tar -xzf "${CACHE_DIR}/node.tar.gz" -C "${CACHE_DIR}"
    rm -f "${CACHE_DIR}/node.tar.gz"
fi

if [ ! -d "${BGUTIL_SRC}" ]; then
    echo "Cloning bgutil-ytdlp-pot-provider@${BGUTIL_REF} ..."
    git clone --depth 1 --branch "${BGUTIL_REF}" \
        https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git "${BGUTIL_SRC}"
fi

if [ ! -f "${BGUTIL_SERVER_BUILT}" ]; then
    echo "Building bgutil server with bundled node ..."
    pushd "${BGUTIL_SRC}/server" >/dev/null
    # First install with devDeps so typescript is available, compile, then
    # prune to production deps so the bundled node_modules stays slim.
    PATH="${NODE_DIR}/bin:${PATH}" "${NODE_DIR}/bin/npm" ci --no-audit --no-fund
    PATH="${NODE_DIR}/bin:${PATH}" "${NODE_DIR}/bin/npx" tsc
    PATH="${NODE_DIR}/bin:${PATH}" "${NODE_DIR}/bin/npm" prune --omit=dev --no-audit --no-fund
    popd >/dev/null
fi

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
    --collect-all yt_dlp_plugins
    --collect-all yt_dlp_ejs
    --collect-all bgutil_ytdlp_pot_provider
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

# --- Embed Node + bgutil-server into the bundle ------------------------------
APP_RESOURCES="dist/ReClip.app/Contents/Resources"

echo "Embedding Node ${NODE_VERSION} into app bundle ..."
mkdir -p "${APP_RESOURCES}/bin"
cp "${NODE_BIN}" "${APP_RESOURCES}/bin/node"
chmod +x "${APP_RESOURCES}/bin/node"

echo "Embedding bgutil-server into app bundle ..."
BGUTIL_DEST="${APP_RESOURCES}/bgutil-server"
remove_build_path "${BGUTIL_DEST}"
mkdir -p "${BGUTIL_DEST}"
cp -R "${BGUTIL_SRC}/server/build" "${BGUTIL_DEST}/build"
cp -R "${BGUTIL_SRC}/server/node_modules" "${BGUTIL_DEST}/node_modules"
cp "${BGUTIL_SRC}/server/package.json" "${BGUTIL_DEST}/package.json"

# Slim the bundle: strip Node debug symbols (~20MB) and prune dev-only
# artefacts from node_modules (~5–10MB). LICENSE files are intentionally
# kept for license compliance.
echo "Stripping debug symbols from Node binary ..."
strip -x "${APP_RESOURCES}/bin/node"

echo "Pruning bgutil node_modules of dev-only files ..."
find "${BGUTIL_DEST}/node_modules" -type f \
    \( -name "*.d.ts" -o -name "*.d.ts.map" -o -name "*.js.map" \) \
    -delete 2>/dev/null || true
find "${BGUTIL_DEST}/node_modules" -type d \
    \( -name "test" -o -name "tests" -o -name "__tests__" -o \
       -name "docs" -o -name "doc" -o -name "examples" -o \
       -name ".github" \) \
    -exec rm -rf {} + 2>/dev/null || true

# Re-sign the bundle (ad-hoc) — required after adding files post-PyInstaller,
# otherwise the code signature seal becomes invalid.
echo "Re-signing app bundle (ad-hoc) ..."
codesign --force --deep --sign - dist/ReClip.app

echo ""
echo "Standalone app built at: dist/ReClip.app"
echo "Run it with: open dist/ReClip.app"
