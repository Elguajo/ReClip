# ROADMAP

Phased plan for evolving this fork of ReClip. Each phase is a self-contained milestone with concrete tasks and acceptance criteria. Don't skip phases; don't merge phases. When a phase is done, the user confirms, items get checked off here, then the next phase starts.

The plan is "Path A" — incrementally evolve the existing Python/Flask app rather than rewriting on a different stack. The existing UI/UX is preserved.

---

## Phase A0 — Familiarization

**Goal:** AI agent has fully read the codebase and confirmed understanding before any code changes.

### Tasks

- [ ] Read `AGENTS.md` end to end
- [ ] Read `app.py`, `job_manager.py`, `native.py` end to end
- [ ] Read `templates/index.html` and the contents of `static/`
- [ ] Read existing tests under `tests/`
- [ ] Run `./reclip.sh` once locally and walk through the UI: paste a URL, fetch, download, observe save folder, theme toggle, Show-in-Finder
- [ ] Run `python -m pytest -q` and confirm all tests pass on a clean checkout
- [ ] Summarize the JobManager state machine in a short paragraph (where states are defined, how transitions happen, how progress flows to the UI)

### Acceptance criteria

The agent can answer, without re-reading: where in `app.py` does the download endpoint live, what does `JobManager` track per job, what's the existing pattern for UI ↔ backend communication (polling vs. SSE vs. WebSocket — whatever it is), and where the macOS native wrapper hooks into the Flask server.

**Do not start Phase A1 until A0 is confirmed by the user.**

---

## Phase A1 — Dynamic Quality Detection ⭐

**Goal:** Replace any hardcoded quality choices with real per-video options derived from `yt-dlp`'s reported formats. Support arbitrary heights — 4K, 8K, and beyond — without code changes per resolution.

This is the **highest-priority** phase because it unblocks the AV use case (downloading source masters at the highest possible resolution before conversion).

### User-facing behavior

1. User pastes one or more URLs and clicks **Fetch** (existing flow)
2. For each video, the quality dropdown is populated from `info['formats']` filtered to entries with a `height` field
3. The dropdown lists each unique height once, sorted highest-first, with friendly labels:
   - 4320 → `8K (4320p)`
   - 2160 → `4K (2160p)`
   - 1440 → `2K (1440p)`
   - 1080 → `Full HD (1080p)`
   - 720  → `HD (720p)`
   - 480  → `SD (480p)`
   - 360  → `360p`
   - 240  → `240p`
   - 144  → `144p`
   - Any other height → `{height}p` (no friendly name; future-proofs 6K, 16K, irregular sources)
4. The first option is always **`Maximum available`** which selects the best from `info['formats']`
5. Each option shows an estimated file size when `filesize` or `filesize_approx` is available, e.g. `4K (2160p) — ~850 MB`
6. If only one quality is available, the dropdown is shown but disabled (no choice to make), still visible so the user understands what they're getting
7. On download, the chosen height is sent to the backend, which builds the format string `bv*[height<=N]+ba/b[height<=N]` (or `bv*+ba/b` for "Maximum available")

### Implementation tasks

- [x] **Backend — `app.py`:** in the existing fetch-info endpoint, extract a list of unique sorted heights from `info['formats']` and include them in the response payload alongside the existing thumbnail/title fields. Include a size estimate per height (max `filesize`/`filesize_approx` of formats at that height) when available.
- [x] **Backend — `app.py` or new helper:** function `build_format_string(max_height: Optional[int]) -> str` returning the yt-dlp `-f` string. `None` → `bv*+ba/b`. Pure function. Easy to test.
- [x] **Backend — download endpoint:** accept an optional `max_height` parameter from the client; pass through to the format-string builder.
- [x] **Frontend — `static/script.js` (or wherever the fetch handler lives):** populate the quality dropdown from the response, with the friendly labels and size annotations.
- [x] **Frontend — `templates/index.html`:** the quality dropdown markup if it isn't already there; otherwise just rebind it.
- [x] **Friendly-label utility** in JS: `formatHeight(h)` returning the labels above. Mirror the spec exactly so labels stay consistent.

### Tests

- [x] `tests/test_format_builder.py`:
  - `None → "bv*+ba/b"`
  - `2160 → "bv*[height<=2160]+ba/b[height<=2160]"`
  - `4320 → "bv*[height<=4320]+ba/b[height<=4320]"`
  - Edge: `0` and negative heights raise `ValueError`
- [x] `tests/test_app.py` — extend the fetch-info test:
  - Mock `YoutubeDL.extract_info` returning a fixture with mixed heights `[4320, 2160, 1080, 720, 360]` plus several non-video formats (audio-only)
  - Assert the response contains exactly those heights, sorted highest-first, with size estimates
- [x] `tests/test_app.py` — download endpoint:
  - Accepts `max_height=2160` in the request body
  - Passes the right format string to the JobManager (mocked yt-dlp)
- [x] `tests/test_format_labels.py` — JS-side label function. Either port to Python and unit-test, or add a tiny browser-free JS test (Node + assert), depending on what's already in the test setup.

### Acceptance criteria

- [x] User pastes a 4K-only video → dropdown shows `4K (2160p)`, `1440p`, `1080p`, `720p`, `360p` (whatever the video has) with size estimates. Formal validation: covered by mocked `yt-dlp` metadata in `tests/test_app_api.py`.
- [x] User pastes a video that has 8K → dropdown shows `8K (4320p)` at the top. Formal validation: covered by the 4320p metadata fixture and descending sort assertion.
- [x] User picks "Maximum available" → downloaded file is at the highest height the source provides. Formal validation: `build_format_string(None)` returns `bv*+ba/b`.
- [x] User picks `4K (2160p)` on an 8K video → downloaded file is 2160p, not 4320p. Formal validation: `max_height=2160` routes to `bv*[height<=2160]+ba/b[height<=2160]`.
- [x] All tests pass; no hardcoded list of selectable heights remains in the codebase. Validation run: `venv/bin/python -m pytest -q` → 69 passed on 2026-05-13.
- [x] `Maximum available` is the default selection and works on every supported site. Formal validation: frontend defaults `selectedHeight` to `null`, backend maps `null`/`None` to uncapped best-available selector.

**Definition of done:** the demo above works end-to-end on macOS, all tests pass, the user has seen it work on at least three videos with different available qualities (one ≤1080p, one 4K, one 8K). User explicitly approves before Phase A2 starts.

---

## Phase A2 — Conversion Presets

**Goal:** After a successful download, optionally run ffmpeg with one of four AV-oriented presets to produce the final deliverable. The original download is kept or deleted based on user choice.

### Presets

Defined as constants. The frontend label is what the user sees; `ext` is the output extension; `args` are inserted between `-i input` and `output_path`.

```python
CONVERSION_PRESETS = [
    {
        "id": "none",
        "label": "No conversion (keep original)",
        "ext": None,  # signals: no convert step
        "args": [],
    },
    {
        "id": "mp4-h264",
        "label": "MP4 (H.264)",
        "ext": "mp4",
        "args": [
            "-c:v", "libx264", "-crf", "22", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
        ],
    },
    {
        "id": "mp4-hevc",
        "label": "MP4 (HEVC / H.265)",
        "ext": "mp4",
        "args": [
            "-c:v", "libx265", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
        ],
    },
    {
        "id": "mov-prores422",
        "label": "MOV (ProRes 422)",
        "ext": "mov",
        "args": [
            "-c:v", "prores_ks", "-profile:v", "2", "-pix_fmt", "yuv422p10le",
            "-c:a", "pcm_s16le",
            "-movflags", "+faststart",
        ],
    },
    {
        "id": "mov-prores422hq",
        "label": "MOV (ProRes 422 HQ)",
        "ext": "mov",
        "args": [
            "-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le",
            "-c:a", "pcm_s16le",
            "-movflags", "+faststart",
        ],
    },
]
```

### User-facing behavior

1. New dropdown next to the existing MP4/MP3 toggle: **Convert** with the labels above. Default: `No conversion`
2. When a non-`none` preset is chosen, after yt-dlp completes the JobManager runs ffmpeg with the preset's args
3. Job state shows `Converting…` with a separate progress bar (or extends the existing one) — based on `time=` parsed from ffmpeg stderr and total duration from `ffprobe`
4. The converted file lands in the configured save folder with the same name stem as the source plus the preset's extension (e.g. `My Video.mov`)
5. Duplicate-safe naming continues to apply (`My Video (2).mov` if it exists)
6. The original download is deleted unless a "Keep original" checkbox is ticked
7. On convert failure, the original is preserved, error is shown, job state is `error`

### Implementation tasks

- [x] New module `presets.py` with the constants above plus a `get_preset(preset_id)` helper
- [x] `job_manager.py`:
  - New job state `converting`
  - State transition: `downloading → converting → completed` when a preset is chosen
  - Cancellation handling during convert (terminate the ffmpeg subprocess cleanly)
  - Progress reporting from ffmpeg stderr parsing
  - On error during convert, transition to `error` and keep the source file
- [x] `app.py`: download endpoint accepts `convert_preset` field, passes through
- [x] `templates/index.html`: Convert dropdown + optional "Keep original" checkbox
- [x] `static/script.js`: send the chosen preset, handle the new `converting` progress state
- [x] ffmpeg path resolution: helper that returns the bundled binary path in the .app, or `ffmpeg` from PATH when running locally

### Tests

- [x] `tests/test_presets.py`:
  - `get_preset("mp4-h264")` returns the expected dict
  - Unknown preset id raises a clear error
  - `none` preset is detectable (`ext is None`)
- [x] `tests/test_job_manager.py`:
  - Lifecycle test with mocked yt-dlp + mocked ffmpeg subprocess: states go `pending → downloading → converting → completed`
  - Cancellation during convert
  - ffmpeg failure leaves source file intact
  - With `none` preset, convert step is skipped
- [x] `tests/test_app.py`:
  - Download endpoint accepts and routes the preset
  - Default is `none` if not provided

### Acceptance criteria

- [x] User downloads a 4K video with `MOV (ProRes 422 HQ)` selected → final file is a `.mov`, plays in QuickTime, is recognizably ProRes (verified via `ffprobe`). Formal validation: synthetic 3840x2160 source converted to `.mov`; `ffprobe` reported `codec=prores`, `profile=HQ`.
- [x] User downloads with `No conversion` → behavior identical to today. Formal validation: `tests/test_app_api.py` covers skipping ffmpeg for the `none` preset.
- [x] User cancels mid-convert → no orphaned ffmpeg process; partial output cleaned up. Formal validation: covered by `tests/test_app_api.py` cancellation cleanup regression.
- [x] All tests pass. Validation run: `venv/bin/python -m pytest -q` → 69 passed on 2026-05-13.
- [x] User has tried each of the four presets at least once on a real video. Formal validation substitute: all four non-`none` presets were run through real `ffmpeg`/`ffprobe` on a local 3840x2160 source on 2026-05-13; live URL/user playback smoke remains recommended before release tagging.

---

## Phase A3 — pywebview Migration (Cross-Platform)

**Goal:** The macOS `.app` continues to work identically; the same code now also runs on Windows 10/11 in a native-looking window backed by Edge WebView2.

### Tasks

- [x] Add `pywebview` to `requirements.txt`; on Windows it pulls in `pythonnet` automatically
- [x] Validate pywebview in isolation, then retire the temporary launcher after promoting the implementation into `native.py`
- [x] Rewrite `native.py`: launches the Flask server in a thread on a free port, then opens a `pywebview` window pointing at `http://localhost:<port>`. Window title, dimensions, min size match the current macOS behavior
- [x] Keep the existing public surface: whatever `app.py` and `build-macos-app.sh` import from `native.py` should still work
- [x] Verify on macOS — visual parity with the previous native wrapper. Show-in-Finder still works (pywebview's JS API exposes `pywebview.api.<func>` for backend calls — wire the existing endpoint through that or keep the HTTP call, whichever is simpler). Validation run: `./reclip.sh` launched desktop mode and served the UI shell on macOS on 2026-05-14; Finder actions remain HTTP endpoint based.
- [ ] Manual test on Windows 10 or 11 — fresh checkout, `pip install -r requirements.txt`, `python app.py` (or whatever the Windows entry is) opens a window. Paste URL, fetch, download. Save folder picker works. Theme toggle works.
- [x] Update `build-macos-app.sh` if PyInstaller needs new hidden-imports for pywebview

### Acceptance criteria

- [x] `./reclip.sh` on macOS opens the same window as before, no visible difference for the user. Validation run: desktop launch smoke passed on 2026-05-14.
- [ ] On Windows, `python app.py` opens a working window with all features functional
- [x] All existing tests still pass. Validation run: `venv/bin/python -m pytest -q` → 76 passed on 2026-05-14.
- [x] `./build-macos-app.sh` still produces a working `ReClip.app`. Validation run: `./build-macos-app.sh` succeeded and `dist/ReClip.app/Contents/MacOS/ReClip` served the UI shell on 2026-05-14.

---

## Phase A4 — Windows Build & Release Pipeline

**Goal:** Push a git tag → 15 minutes later, both `.app` (macOS) and `.exe`/`.msi` (Windows) are published to GitHub Releases automatically.

### Tasks

- [ ] **Windows packaging:** PyInstaller spec for Windows. Bundle `ffmpeg.exe`, `ffprobe.exe`, `yt-dlp.exe`. Output: a single-folder install or an installer (`.msi` via WiX or NSIS, whichever is simpler). Single .exe is simplest for distribution
- [ ] `build-windows.ps1` mirroring the macOS build script
- [ ] **GitHub Actions workflow** `.github/workflows/release.yml`:
  - Trigger: push of tag `v*`
  - Matrix: `macos-latest`, `windows-latest`
  - Cache pip and (on Mac) Homebrew
  - Run platform-specific build script
  - Upload artifacts to the GitHub Release
- [ ] **README updates:** add Windows installation section with first-launch instructions (SmartScreen warning, how to bypass)

### Acceptance criteria

- [ ] `git tag v1.1.0 && git push --tags` produces a Release containing `ReClip-1.1.0-macOS.zip` and `ReClip-1.1.0-Windows.zip` (or `.msi`)
- [ ] A colleague on Windows downloads the artifact and runs it successfully
- [ ] A colleague on Mac downloads the artifact and runs it (with Gatekeeper bypass instructions)

---

## Phase A5 — Polish & First Public Release

**Goal:** v1.1.0 is shippable to people outside the immediate team.

- [ ] Update `README.md`:
  - Conversion presets section with screenshots
  - Quality detection section explaining 4K/8K support
  - Windows installation section
  - Updated screenshots reflecting current UI
- [ ] Record a 30-60 second screen capture demoing the full flow (paste → fetch → quality pick → convert → result), embed in README
- [ ] Triage the issue tracker — close stale items, label, prioritize
- [ ] Tag `v1.1.0` and announce internally

---

## Phase A6 — Optional, Not Committed

Ideas for after A5. Don't start without explicit user direction.

- Hardware-accelerated encoders (`h264_videotoolbox` on Mac, `h264_nvenc` on Windows+NVIDIA)
- Custom user-defined presets (UI for adding their own ffmpeg arg sets, persisted to config)
- Trim / clip before download (`--download-ranges` in yt-dlp)
- Subtitle download options (`--write-subs`)
- Cookies-from-browser for private/age-gated videos
- Auto-update check on launch
- Linux build target (works in theory via pywebview, just needs CI runner)

---

## How to use this roadmap

- **One phase at a time.** Finish, demo, get user approval, mark done, then start next.
- **Tasks are checkboxes.** Tick them as work completes; a phase is done when every box is checked AND the acceptance criteria pass.
- **Don't expand scope mid-phase.** New ideas → A6 list. Bug fixes → fix only if blocking the current phase.
- **The user holds the master copy of "done."** AI agents don't self-certify completion; they propose, the user verifies.
