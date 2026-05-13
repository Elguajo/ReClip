# AGENTS.md

Instructions for AI coding agents (Claude Code, Cursor, Aider, etc.) working in this repository. Read this in full **before** making any changes. The standard is documented at [agents.md](https://agents.md/).

---

## 1. Project Overview

**ReClip** — self-hosted media downloader. Pastes one or more URLs, fetches them via yt-dlp, optionally converts via ffmpeg, saves to a chosen folder.

This fork extends the upstream `averygan/reclip` with:
- Configurable save location, persisted to `~/.reclip/config.json`
- Show-in-Finder action after download
- Light/dark theme toggle (saved to `localStorage`)
- Safer download pipeline (temp folder → final destination)
- Duplicate-safe filenames
- Centralized `JobManager` for state, progress, cancel, errors
- Regression tests under `tests/`

**Active development direction (this fork):**
- **Phase A1:** Dynamic quality detection up to 8K and beyond, populated from actual formats reported by yt-dlp per video
- **Phase A2:** Post-download conversion presets for AV workflows (H.264, HEVC, ProRes 422, ProRes 422 HQ)
- **Phase A3:** Cross-platform support — native wrapper now uses `pywebview` so the same codebase can run on Windows
- **Phase A4:** Windows build pipeline + GitHub Actions release automation

See `docs/ROADMAP.md` for the phased plan with concrete tasks and acceptance criteria.

**Target users:** AV integration engineers (RedMouse and similar shops). Not developers — UX must remain simple and the app must just work after install. Defaults matter more than configurability.

---

## 2. Tech Stack — and what NOT to introduce

| Layer | Technology |
|---|---|
| Backend | Python 3.8+, Flask |
| Frontend | Vanilla HTML / CSS / JS in `templates/` and `static/` |
| Native wrapper | `pywebview` (WKWebView on macOS, Edge WebView2 on Windows) |
| Download engine | `yt-dlp` |
| Media processing | `ffmpeg` + `ffprobe` |
| Job lifecycle | `JobManager` class in `job_manager.py` |
| Tests | `pytest` |
| Packaging | `build-macos-app.sh` (PyInstaller-based for the .app bundle) |

**Do NOT introduce without explicit user approval:**

- ❌ React, Vue, Svelte, or any frontend framework
- ❌ Tailwind, styled-components, CSS-in-JS, or any CSS preprocessor
- ❌ TypeScript, Webpack, Vite, or any build step for the frontend
- ❌ Async/await refactor of existing sync Flask routes
- ❌ FastAPI or any backend framework swap
- ❌ Database layer (SQLite, etc.) — stick to `~/.reclip/config.json` and in-memory state
- ❌ Heavy new dependencies (each one bloats the macOS bundle)
- ❌ Tauri, Electron, or any other shell rewrite — those were considered and rejected for this fork

**The "no build step" frontend is a feature, not a limitation.** Keep it.

---

## 3. Repository Layout

```
.
├── app.py                  # Flask app, HTTP routes, entry point
├── job_manager.py          # JobManager class, job lifecycle, state machine
├── native.py               # pywebview desktop wrapper for the local Flask app
├── reclip.sh               # Local dev launcher (Mac/Linux)
├── build-macos-app.sh      # macOS .app bundling script
├── release-macos.sh        # macOS release packaging
├── Dockerfile              # Optional self-hosted Docker run
│
├── templates/              # Flask Jinja2 HTML templates
│   └── index.html          # Single-page UI
├── static/                 # CSS, JS, images served as-is
│
├── tests/                  # pytest suite
│
├── assets/                 # Screenshots, preview images
├── ReClip.app/             # Generated local macOS bundle, ignored by git
│
├── requirements.txt        # Runtime deps
├── requirements-dev.txt    # Test/dev deps
├── requirements-build.txt  # PyInstaller / build deps
│
├── README.md
├── docs/
│   ├── ROADMAP.md          # ⭐ Phased development plan — read before any work
│   ├── CLAUDE_CODE_GUIDE.md
│   └── handoff/
└── AGENTS.md               # This file
```

**Adding files:** keep additions minimal. New presets/configuration → constants in an existing module if it fits, or a new `presets.py`-style file if not. Don't create directories for one file.

---

## 4. Commands Reference

```bash
# Local dev (Mac/Linux) — opens http://localhost:8899
./reclip.sh

# Tests
python -m pytest -q
python -m pytest tests/test_specific.py -v   # one file, verbose

# Build the macOS .app
./build-macos-app.sh
open dist/ReClip.app

# Release a versioned macOS zip
./release-macos.sh

# Docker (self-hosted)
docker build -t reclip . && docker run -p 8899:8899 reclip
```

### Release notes style

Release notes must be written for ReClip users first, not as raw commit summaries.

- Start with one plain sentence describing the build, e.g. "Standalone macOS app build."
- Use clear user-facing sections such as `Features`, `Fixes`, `What changed`, `Cross-platform groundwork`, `Developer / project hygiene`, and `Install`.
- Keep technical commit details in a final `Changelog` section only.
- Always include install steps and the unsigned macOS Gatekeeper note for app releases.
- Avoid leading with internal file moves, tests, or refactors unless they directly affect users.

Use this shape by default:

```markdown
Standalone macOS app build.

## Features / What changed
- User-facing change in plain language.

## Fixes
- User-visible bug fix or reliability improvement.

## Install
1. Download `ReClip-vX.Y.Z-macOS.zip` or `.dmg`.
2. Verify with the matching `.sha256` if you want.
3. Move `ReClip.app` to `/Applications`.

First launch: right-click `ReClip.app` → Open (macOS Gatekeeper, build is unsigned).

## Changelog
- `abc1234` Commit subject
```

**After every code change:**
1. Run the relevant test file(s); add new tests for new behavior
2. If `app.py` or `job_manager.py` changed: run the full suite (`pytest -q`)
3. If frontend changed: launch `./reclip.sh` and smoke-test the affected flow
4. Don't commit if any test fails — fix or revert

---

## 5. Coding Conventions

### Python

- **Python 3.8+ compatible.** No walrus-only patterns, no `match` statements.
- **Style:** PEP 8, 4-space indent, snake_case for functions and variables, PascalCase for classes.
- **Docstrings** for public functions and classes. One-liner is fine for obvious helpers; full triple-quoted block for anything non-trivial.
- **Type hints** where they clarify intent — not religiously, but for new public functions and JobManager methods, yes.
- **No bare `except:`.** Catch specific exceptions; if catching `Exception`, log it.
- **Logging via the existing logger** (look for `logging.getLogger(__name__)` patterns in app.py). Don't add `print()` calls in committed code.
- **Imports:** standard library, then third-party, then local. One import per line is fine.

### Frontend (HTML / CSS / JS)

- **Vanilla everything.** No JSX, no JS frameworks, no CSS preprocessors.
- **CSS in `static/`.** Use existing class names where possible — extend, don't redefine.
- **JS in `static/`.** Keep modules small. Use `addEventListener` not inline `onclick=`. Use `fetch()` for API calls.
- **Match the existing visual style.** Light/dark theme tokens are CSS custom properties (variables). Use them — don't hardcode colors.
- **Don't break existing behavior** — Quality picker, save location, theme toggle, Show-in-Finder all work today. Verify they still work after any UI change.

### Tests

- **Every new feature gets a test.** Bug fixes get a regression test.
- **Test files mirror source files:** `app.py` → `tests/test_app.py`, `job_manager.py` → `tests/test_job_manager.py`.
- **Use fixtures** (already defined in `tests/conftest.py` if it exists; create one if needed) instead of repeating setup code.
- **Mock yt-dlp and ffmpeg.** Tests must not actually hit YouTube or run ffmpeg — those are slow, flaky, and depend on network.

### Configuration & Persistence

- **User config goes to `~/.reclip/config.json`.** That's the existing convention — don't introduce alternatives.
- **Frontend prefs (theme, etc.) go to `localStorage`.** Already established.
- **Never persist secrets.** No tokens, no cookies, no credentials in config.

---

## 6. JobManager Conventions

The `JobManager` class is the heart of state. New work threading through it must follow existing patterns.

- **State transitions are explicit.** A job moves: `pending → downloading → [converting] → completed`, or any state → `error`/`cancelled`. Don't skip states; don't silently retry.
- **Progress is a float 0.0–1.0** plus an optional message string. Don't invent new progress shapes.
- **Cancellation is cooperative.** A long-running step (yt-dlp, ffmpeg) checks `job.is_cancelled` between chunks/lines and exits cleanly — no kill -9 unless absolutely necessary.
- **Errors are user-facing strings.** Don't dump tracebacks to the UI. Log the traceback server-side; show the user "Failed to fetch metadata" or similar.

When adding a new job phase (e.g. conversion in Phase A2):
1. Add the new state to the state machine
2. Update the lifecycle method to call the new phase between download and completion
3. Add progress reporting from the new phase
4. Add tests covering the new state transitions, cancellation during the new phase, and error paths

---

## 7. Phase Discipline (read this before coding)

**Before any non-trivial change**, check `docs/ROADMAP.md` and confirm the change belongs to the current phase.

- **Stay in the current phase.** Don't fix or improve unrelated things "while you're there." Leave a `# TODO:` with phase reference if you spot something — don't act on it.
- **Don't skip phases.** If a Phase A3 task seems blocked by a Phase A1 issue, fix the A1 issue first or ask the user.
- **A phase is done** when its acceptance criteria pass and the user has confirmed. Then mark items complete in `docs/ROADMAP.md` and ask before starting the next phase.

---

## 8. What NOT to do

❌ **Don't commit `~/.reclip/config.json` or any user-specific data.**

❌ **Don't reach into yt-dlp internals.** Use the public Python API (`YoutubeDL`, `extract_info`) or subprocess. Don't import private modules.

❌ **Don't write to disk in `/tmp` without cleanup.** Use the existing temp pattern — temp folder per job, cleaned on completion or error.

❌ **Don't change `requirements.txt` casually.** Each dep is auditable. New dep = explicit user approval.

❌ **Don't break the macOS .app build.** If something works in `./reclip.sh` but not in the bundled .app, that's a regression. Test both.

❌ **Don't reformat unrelated code.** Whitespace and import-order changes in files you didn't otherwise touch make diffs unreviewable.

❌ **Don't run `git push` or `git commit -A` autonomously.** Stage changes, show the diff, let the user commit.

❌ **Don't fetch real videos from YouTube in tests.** Mock yt-dlp's `extract_info` with fixture data.

---

## 9. Working with yt-dlp

The download engine. Critical for Phase A1 (quality detection) and ongoing.

- **Use the Python API for metadata** (`YoutubeDL.extract_info(url, download=False)`), subprocess for actual downloads is fine if that's the existing pattern.
- **`info['formats']` is a list of dicts** — each format has `format_id`, `height`, `width`, `vcodec`, `acodec`, `filesize`/`filesize_approx`, `tbr`, `ext`, `protocol`. Heights are the source of truth for quality detection.
- **Format selection string** for downloads: `bv*[height<=N]+ba/b[height<=N]` to cap at height N; `bv*+ba/b` for "best available." Build these dynamically based on user choice.
- **Heights are not always standard.** Some videos have non-standard heights (e.g. 3072 instead of 2160). Don't hardcode an enum — derive from `info['formats']`.
- **Update yt-dlp regularly.** YouTube changes its formats; old yt-dlp versions break. The pinned version in `requirements.txt` should be reviewed each release.

---

## 10. Working with ffmpeg

Used for the conversion presets in Phase A2.

- **Bundled, not system.** The macOS .app embeds an `ffmpeg` binary; resolve its path via the existing helper, not `shutil.which("ffmpeg")`.
- **Run via subprocess with explicit args.** Never compose shell strings — pass the args list. Avoids quoting bugs and shell injection.
- **Parse progress from stderr.** ffmpeg writes `time=HH:MM:SS.MS` to stderr; pair with total duration from `ffprobe` to compute progress.
- **Handle non-zero exit codes.** A failed convert leaves the source file intact; don't delete the input until convert succeeds.

---

## 11. pywebview Notes — Phase A3

The native wrapper has been promoted to pywebview:

- `pywebview` works on macOS (uses WKWebView under the hood), Windows (uses Edge WebView2), Linux (uses GTK/QT)
- The existing Flask app keeps running unchanged — pywebview just opens a window pointing at `localhost:8899`
- Keep `native.py` as the public wrapper entry point so callers don't change
- The `build-macos-app.sh` flow collects pywebview for PyInstaller
- Add a `build-windows.ps1` (or similar) for Windows packaging
- Test on a real Windows 10/11 machine before declaring Phase A3 done — VM is fine, but it must be a real test, not "it should work"

---

## 12. When Uncertain

1. Re-read `docs/ROADMAP.md` for the current phase's tasks and acceptance criteria
2. Search the existing codebase for similar patterns — match what's already there
3. Ask the user a single concrete question rather than guessing
4. Show the smallest possible change first; expand only after user approves

---

_This file is the contract between human and AI agents in this repo. If a rule here is wrong or missing, update the file in the same PR as the work that revealed it._
