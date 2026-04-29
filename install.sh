#!/bin/bash
set -e

REPO="https://github.com/Elguajo/ReClip.git"
INSTALL_DIR="$HOME/.reclip"
APP_NAME="ReClip.app"

echo ""
echo "  ReClip installer"
echo "  ----------------"
echo ""

if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew was not found."
    echo "Install it first:"
    echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 1
fi

echo "[1/5] Checking dependencies..."
missing=""
command -v python3 >/dev/null 2>&1 || missing="$missing python3"
command -v git >/dev/null 2>&1 || missing="$missing git"
command -v ffmpeg >/dev/null 2>&1 || missing="$missing ffmpeg"
command -v yt-dlp >/dev/null 2>&1 || missing="$missing yt-dlp"

if [ -n "$missing" ]; then
    brew install $missing
fi
echo "Dependencies are ready."

echo "[2/5] Downloading ReClip..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git remote set-url origin "$REPO"
    git fetch --quiet origin main
    git reset --quiet --hard origin/main
elif [ -d "$INSTALL_DIR" ]; then
    TMP_DIR="$(mktemp -d)"
    git clone --quiet "$REPO" "$TMP_DIR"
    cp -R "$TMP_DIR"/. "$INSTALL_DIR"/
    rm -rf "$TMP_DIR"
else
    git clone --quiet "$REPO" "$INSTALL_DIR"
fi
echo "Code is installed at $INSTALL_DIR."

echo "[3/5] Setting up Python..."
cd "$INSTALL_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "Python environment is ready."

echo "[4/5] Installing macOS app..."
rm -rf "/Applications/$APP_NAME"
cp -R "$INSTALL_DIR/$APP_NAME" "/Applications/$APP_NAME"

LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister"
if [ -x "$LSREGISTER" ]; then
    "$LSREGISTER" -f "/Applications/$APP_NAME" >/dev/null 2>&1 || true
fi
echo "$APP_NAME is installed in /Applications."

echo "[5/5] Done."
echo ""
echo "Launch with: Cmd+Space -> ReClip"
echo "Or run: open /Applications/ReClip.app"
echo ""

read -r -p "Launch ReClip now? [Y/n] " reply
case "$reply" in
    [Nn]*) ;;
    *) open "/Applications/$APP_NAME" ;;
esac
