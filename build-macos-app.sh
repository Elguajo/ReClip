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
APP_ICON="assets/AppIcon.icns"

if [ ! -f "$APP_ICON" ]; then
    echo "App icon not found at ${APP_ICON}."
    echo "Restore the canonical icon before building."
    exit 1
fi

# --- bgutil POT provider bundle (Bun runtime + bundled JS) -------------------
# We ship Bun (the Node-compatible JS runtime) renamed as `node`, plus a single
# Bun-bundled generate_once.js. This replaces the previous setup that shipped a
# 85MB Node runtime alongside a 55MB node_modules tree (~140MB total) with a
# ~60MB Bun binary plus a ~6MB self-contained bundle — about a 70MB net saving.
#
# Bun-as-node is preferred over `bun build --compile` here because yt-dlp also
# invokes the JS runtime for n-signature/EJS challenges (not just bgutil), and
# a compiled bgutil-pot binary would mishandle those. Bun is Node-API
# compatible, so the bgutil plugin and yt-dlp's own runtime path both work.

BUN_VERSION="1.3.14"
BGUTIL_REF="1.3.1"
CACHE_DIR="$(pwd)/.build-cache"
case "$(uname -m)" in
    arm64) BUN_TARGET="darwin-aarch64" ;;
    x86_64) BUN_TARGET="darwin-x64" ;;
    *) echo "Unsupported macOS architecture: $(uname -m)"; exit 1 ;;
esac
BUN_DIR="${CACHE_DIR}/bun-v${BUN_VERSION}"
BUN_BIN="${BUN_DIR}/bun"
BGUTIL_SRC="${CACHE_DIR}/bgutil-ytdlp-pot-provider"
BGUTIL_BUNDLED_JS="${BGUTIL_SRC}/server/build-bundled/generate_once.js"

mkdir -p "${CACHE_DIR}"

if [ ! -x "${BUN_BIN}" ]; then
    echo "Downloading Bun v${BUN_VERSION} (${BUN_TARGET}) ..."
    curl -fsSL \
        "https://github.com/oven-sh/bun/releases/download/bun-v${BUN_VERSION}/bun-${BUN_TARGET}.zip" \
        -o "${CACHE_DIR}/bun.zip"
    rm -rf "${BUN_DIR}"
    mkdir -p "${BUN_DIR}"
    unzip -q "${CACHE_DIR}/bun.zip" -d "${BUN_DIR}"
    # Zip ships a `bun-${BUN_TARGET}/bun` entry; flatten it.
    mv "${BUN_DIR}/bun-${BUN_TARGET}/bun" "${BUN_BIN}"
    rmdir "${BUN_DIR}/bun-${BUN_TARGET}"
    chmod +x "${BUN_BIN}"
    rm -f "${CACHE_DIR}/bun.zip"
fi

if [ ! -d "${BGUTIL_SRC}" ]; then
    echo "Cloning bgutil-ytdlp-pot-provider@${BGUTIL_REF} ..."
    git clone --depth 1 --branch "${BGUTIL_REF}" \
        https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git "${BGUTIL_SRC}"
fi

if [ ! -f "${BGUTIL_BUNDLED_JS}" ]; then
    echo "Bundling bgutil generate_once.js with Bun v${BUN_VERSION} ..."
    pushd "${BGUTIL_SRC}/server" >/dev/null

    "${BUN_BIN}" install --silent

    # Drop canvas: it ships a 10MB+ native addon (libcairo/pango), but jsdom's
    # canvas integration is an optional peer dep — the POT flow only triggers
    # a `getContext()` warning, never an actual failure. Verified end-to-end
    # with --bypass-cache against live YouTube. `bun remove` alone leaves the
    # canvas directory in node_modules, so we also rm it on disk; otherwise
    # Bun's bundler resolves it and emits a 700KB canvas-*.node asset.
    "${BUN_BIN}" remove canvas --silent || true
    rm -rf node_modules/canvas

    # Drop the TypeScript-only commander shim in types/commander.d.ts that
    # remaps `commander` → `@commander-js/extra-typings`. Bun's bundler honors
    # tsconfig.json paths so the shim trips up `bun build`, even though it has
    # no runtime effect.
    rm -f types/commander.d.ts

    mkdir -p build-bundled
    "${BUN_BIN}" build src/generate_once.ts \
        --target=bun --minify \
        --outdir=build-bundled

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
    --icon "$APP_ICON"
    --add-data templates:templates
    --add-data static:static
    --add-binary "$FFMPEG_BIN:bin"
    --collect-all yt_dlp
    --collect-all yt_dlp_plugins
    --collect-all yt_dlp_ejs
    --collect-all bgutil_ytdlp_pot_provider
    --collect-all webview
    --collect-data certifi
    --hidden-import webview
    # Trim Python stdlib modules that PyInstaller pulls in by default but
    # ReClip never imports. Each saves a few hundred KB to a few MB.
    # NOTE: do not exclude `distutils` — PyInstaller's hook-distutils.py
    # aliases it as part of setuptools shim handling, and excluding it makes
    # the build crash before bundling. Same for `xml.dom`, which lxml-ish
    # hooks touch indirectly.
    --exclude-module tkinter
    --exclude-module _tkinter
    --exclude-module turtle
    --exclude-module turtledemo
    --exclude-module test
    --exclude-module unittest
    --exclude-module pydoc_data
    --exclude-module lib2to3
    --exclude-module xmlrpc
)

if [ -n "$FFPROBE_BIN" ]; then
    pyinstaller_args+=(--add-binary "$FFPROBE_BIN:bin")
fi

python -m PyInstaller "${pyinstaller_args[@]}" native.py

# --- Embed Bun (as `node`) + bundled generate_once.js into the bundle --------
APP_RESOURCES="dist/ReClip.app/Contents/Resources"
BGUTIL_DEST="${APP_RESOURCES}/bgutil-server"

echo "Embedding Bun runtime + bundled generate_once.js ..."
remove_build_path "${BGUTIL_DEST}"
mkdir -p "${BGUTIL_DEST}/build"

# Bun runs both the bgutil generate_once.js bundle and any other JS that
# yt-dlp's n-signature/EJS fallback wants to execute. Bun is Node-API
# compatible for both cases.
cp "${BUN_BIN}" "${BGUTIL_DEST}/bun"
chmod +x "${BGUTIL_DEST}/bun"

# Self-contained ~6MB ESM bundle with all of bgutil's JS deps inlined. Lives
# at the path the bgutil plugin expects (server_home/build/generate_once.js).
cp "${BGUTIL_BUNDLED_JS}" "${BGUTIL_DEST}/build/generate_once.js"

# Shell shim named `node` so the bgutil plugin's version gate
# (`node --version` parsed against `^v(\S+)`) passes — Bun renamed to `node`
# refuses a bare `--version` invocation and demands a script, which fails
# that gate. The shim emits a Node-shaped version string and otherwise
# forwards every other invocation to Bun verbatim.
cat > "${BGUTIL_DEST}/node" <<'SHIM'
#!/bin/sh
set -e
if [ "$#" -eq 1 ] && [ "$1" = "--version" ]; then
    echo "v22.0.0"
    exit 0
fi
exec "$(cd "$(dirname "$0")" && pwd)/bun" "$@"
SHIM
chmod +x "${BGUTIL_DEST}/node"

# Re-sign the bundle (ad-hoc) — required after adding files post-PyInstaller,
# otherwise the code signature seal becomes invalid.
echo "Re-signing app bundle (ad-hoc) ..."
codesign --force --deep --sign - dist/ReClip.app

echo ""
echo "Standalone app built at: dist/ReClip.app"
echo "Run it with: open dist/ReClip.app"
