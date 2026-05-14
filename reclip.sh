#!/bin/bash
set -e
cd "$(dirname "$0")"

# Check prerequisites
missing=""

if ! command -v python3 &> /dev/null; then
    missing="$missing python3"
fi

if ! command -v ffmpeg &> /dev/null; then
    missing="$missing ffmpeg"
fi

if [ -n "$missing" ]; then
    echo "Missing required tools:$missing"
    echo ""
    if command -v brew &> /dev/null; then
        echo "Install with:  brew install$missing"
    elif command -v apt &> /dev/null; then
        echo "Install with:  sudo apt install$missing"
    else
        echo "Please install:$missing"
    fi
    exit 1
fi

# Set up venv and install Python deps
if [ ! -d "venv" ]; then
    echo "Setting up virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -r requirements.txt
else
    source venv/bin/activate
    # Ensure all required packages are installed even if venv exists
    pip install -q -r requirements.txt
fi

export PATH="$PWD/venv/bin:$PATH"

echo ""
if [ -n "${RECLIP_SERVER_ONLY:-}" ]; then
    PORT="${PORT:-8899}"
    export PORT
    echo "  ReClip is running at http://localhost:$PORT"
else
    echo "  ReClip desktop window is opening"
    echo "  Preferred local URL: http://localhost:${PORT:-8899}"
fi
echo "  Downloads: ${RECLIP_DOWNLOAD_DIR:-saved app setting}"
echo ""
python3 app.py
