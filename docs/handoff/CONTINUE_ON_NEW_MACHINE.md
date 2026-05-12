# Continue ReClip on a New Machine

This is the minimal handoff checklist for continuing ReClip from GitHub without copying local build artifacts.

## Source of truth

- GitHub repository: `https://github.com/Elguajo/ReClip.git`
- Default branch: `main`
- Current release tag seen during handoff audit: `v1.2.0`
- Current roadmap: `docs/ROADMAP.md`
- Agent instructions: `AGENTS.md`

The repository should contain source code, docs, tests, scripts, and small assets only. Do not copy local virtual environments, `.app` bundles, release zips, build caches, downloaded media, or user config into Git.

## Fresh checkout

```bash
git clone https://github.com/Elguajo/ReClip.git
cd ReClip
git status --short --branch
```

Expected result on a clean clone:

```text
## main...origin/main
```

## Local development setup

macOS:

```bash
brew install python3 ffmpeg
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
./reclip.sh
```

Open `http://localhost:8899` if the launcher does not open it automatically.

Windows development for the current cross-platform work:

```powershell
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
python app.py
```

Install `ffmpeg` separately and ensure it is on `PATH` until the Windows packaging phase bundles it.

## Verification

Run the test suite before starting new work:

```bash
python -m pytest -q
```

For frontend changes, also launch the app and smoke-test:

- Fetch metadata for a URL
- Select quality
- Start and cancel a download
- Toggle theme
- Change save folder
- Use Show in Finder on macOS after a completed download

## What stays local

These are intentionally ignored and should not be added to GitHub:

- `venv/`
- `.build-cache/`
- `build/`
- `dist/`
- `ReClip.app/`
- `release/`
- `downloads/`
- `.pytest_cache/`
- `.DS_Store`
- `~/.reclip/config.json`

## Current project state

Completed implementation work in `docs/ROADMAP.md`:

- Phase A1 implementation tasks and tests are checked off.
- Phase A2 implementation tasks and tests are checked off.
- Phase A3 has a `native_pywebview.py` spike checked off, but the main `native.py` migration and Windows verification remain open.

Before starting new work, read:

1. `AGENTS.md`
2. `docs/ROADMAP.md`
3. `README.md`
4. The files directly involved in the next roadmap phase

## Git workflow

Use a branch per phase or fix:

```bash
git checkout -b codex/phase-a3-pywebview
```

Before pushing:

```bash
git status --short
git diff --stat
python -m pytest -q
```

Do not use `git add -A` blindly. Stage only the files that belong to the current change.
