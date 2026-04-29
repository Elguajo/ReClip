#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

usage() {
    cat <<'USAGE'
Usage: ./release-macos.sh vX.Y.Z [--dmg] [--publish]

Builds dist/ReClip.app and creates release assets in ./release:
  - ReClip-vX.Y.Z-macOS.zip
  - ReClip-vX.Y.Z-macOS.zip.sha256
  - ReClip-vX.Y.Z-macOS.dmg              with --dmg
  - ReClip-vX.Y.Z-macOS.dmg.sha256       with --dmg

Options:
  --dmg      Also create a compressed DMG.
  --publish  Create/push the git tag and publish assets with gh release create.
USAGE
}

fail() {
    echo "Error: $*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "$1 was not found."
}

VERSION="${1:-}"
CREATE_DMG=0
PUBLISH=0

if [ -z "$VERSION" ] || [ "$VERSION" = "-h" ] || [ "$VERSION" = "--help" ]; then
    usage
    exit 0
fi
shift

case "$VERSION" in
    v[0-9]*.[0-9]*.[0-9]*) ;;
    *) fail "version must look like v1.2.3" ;;
esac

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dmg) CREATE_DMG=1 ;;
        --publish) PUBLISH=1 ;;
        -h|--help)
            usage
            exit 0
            ;;
        *) fail "unknown option: $1" ;;
    esac
    shift
done

[ "$(uname -s)" = "Darwin" ] || fail "macOS is required to build the app bundle."

require_command python3
require_command ffmpeg
require_command shasum

if [ "$CREATE_DMG" -eq 1 ]; then
    require_command hdiutil
fi

if [ "$PUBLISH" -eq 1 ]; then
    require_command git
    require_command gh
    gh auth status >/dev/null || fail "GitHub CLI is not authenticated. Run: gh auth login"
    git diff --quiet || fail "commit or stash local changes before publishing a release."
    git diff --cached --quiet || fail "commit or unstage staged changes before publishing a release."
fi

./build-macos-app.sh

[ -d "dist/ReClip.app" ] || fail "dist/ReClip.app was not created."
find dist/ReClip.app -name .DS_Store -delete

mkdir -p release

ZIP_PATH="release/ReClip-${VERSION}-macOS.zip"
DMG_PATH="release/ReClip-${VERSION}-macOS.dmg"

rm -f "$ZIP_PATH" "$ZIP_PATH.sha256" "$DMG_PATH" "$DMG_PATH.sha256"

ditto -c -k --keepParent dist/ReClip.app "$ZIP_PATH"
shasum -a 256 "$ZIP_PATH" > "$ZIP_PATH.sha256"

ASSETS=("$ZIP_PATH" "$ZIP_PATH.sha256")

if [ "$CREATE_DMG" -eq 1 ]; then
    DMG_ROOT="release/dmg-root"
    rm -rf "$DMG_ROOT"
    mkdir -p "$DMG_ROOT"
    cp -R dist/ReClip.app "$DMG_ROOT/"
    ln -s /Applications "$DMG_ROOT/Applications"

    hdiutil create \
        -volname "ReClip" \
        -srcfolder "$DMG_ROOT" \
        -ov \
        -format UDZO \
        "$DMG_PATH"

    shasum -a 256 "$DMG_PATH" > "$DMG_PATH.sha256"
    ASSETS+=("$DMG_PATH" "$DMG_PATH.sha256")
fi

if [ "$PUBLISH" -eq 1 ]; then
    if ! git rev-parse "$VERSION" >/dev/null 2>&1; then
        git tag -a "$VERSION" -m "ReClip $VERSION"
        git push origin "$VERSION"
    fi

    gh release create "$VERSION" "${ASSETS[@]}" \
        --title "ReClip $VERSION" \
        --notes "Standalone macOS app build."
fi

echo ""
echo "Release assets:"
for asset in "${ASSETS[@]}"; do
    echo "  $asset"
done

if [ "$PUBLISH" -eq 0 ]; then
    echo ""
    echo "Publish with:"
    echo "  ./release-macos.sh $VERSION --dmg --publish"
fi
