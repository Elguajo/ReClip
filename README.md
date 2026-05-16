# ReClip

Self-hosted media downloader for AV workflows. Paste one or more links, fetch real source formats with `yt-dlp`, choose the best available quality up to 8K and beyond, optionally convert the result with `ffmpeg`, and save it to the folder you choose.

This fork keeps ReClip lightweight: Python + Flask, vanilla HTML/CSS/JS, no frontend build step, and a native desktop window powered by `pywebview`.

![Python](https://img.shields.io/badge/python-3.8+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

![ReClip MP3 Mode](assets/preview-mp3.png)

## Features

- Download from 1000+ supported sites via [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- MP4 video downloads and MP3 audio extraction
- Dynamic quality detection from actual source formats, including 4K, 8K, and irregular heights
- Maximum available quality by default, with optional per-video height caps
- Post-download conversion presets for AV deliverables: H.264, HEVC, ProRes 422, and ProRes 422 HQ
- Bulk downloads from multiple pasted URLs
- Automatic URL deduplication
- Configurable output folder persisted to `~/.reclip/config.json`
- Duplicate-safe filenames, so existing files are not overwritten
- Optional original-file retention after conversion
- Reveal completed files in Finder on macOS
- Light/dark theme toggle saved in `localStorage`
- Progress, cancel, retry, conversion state, and safer temp-folder cleanup through `JobManager`
- Native desktop wrapper powered by `pywebview`
- Clean responsive UI with no React, no Tailwind, no bundler, and no frontend build step

## What This Fork Adds

Compared with the original ReClip repo, this fork adds a more production-minded download pipeline:

- **Dynamic quality picker:** ReClip reads `info["formats"]` from `yt-dlp` per video, extracts the available heights, sorts them highest-first, and labels common resolutions such as `8K (4320p)`, `4K (2160p)`, `Full HD (1080p)`, and `HD (720p)`.
- **Best-available downloads:** the default selector uses `bv*+ba/b`; choosing a capped height uses `bv*[height<=N]+ba/b[height<=N]`.
- **Conversion presets:** after download, ReClip can run `ffmpeg` to create MP4 H.264, MP4 HEVC/H.265, MOV ProRes 422, or MOV ProRes 422 HQ outputs.
- **Safer conversion behavior:** failed conversions preserve the downloaded source file; cancelled conversions clean up partial output.
- **Configurable save location:** use the folder button in the top-right corner to choose where completed downloads are saved. The choice is persisted in `~/.reclip/config.json`.
- **Finder action:** click **Show** after a download finishes to reveal the saved file in Finder.
- **Dark theme:** the top-right theme button toggles light/dark mode and stores the preference in `localStorage`.
- **Safer download pipeline:** files are downloaded into an internal temp folder, then moved into the configured destination only after `yt-dlp` succeeds.
- **Duplicate-safe filenames:** duplicates are saved as `Name (2).mp4`, `Name (3).mp4`, and so on.
- **Centralized job lifecycle:** download progress, conversion progress, cancellation, completion, errors, and cleanup are handled through `JobManager`.
- **pywebview wrapper:** the app now opens in a native desktop window backed by WKWebView on macOS and Edge WebView2 on Windows.
- **Regression tests:** API and job lifecycle tests cover URL validation, format parsing, quality selection, save-folder behavior, final file movement, duplicate naming, conversion, cancellation, and pywebview startup helpers.

## Quick Start

### Download for macOS

Download the latest `ReClip-*-macOS.zip` from [GitHub Releases](https://github.com/Elguajo/ReClip/releases), unzip it, and move `ReClip.app` to `/Applications`.

After downloading and moving the app, remove quarantine for this app only:

```bash
xattr -dr com.apple.quarantine /Applications/ReClip.app
```

### Run locally on macOS or Linux

Install the media tools first:

```bash
brew install yt-dlp ffmpeg                    # macOS
sudo apt install ffmpeg && pip install yt-dlp # Debian/Ubuntu
```

Then clone and start ReClip:

```bash
git clone https://github.com/Elguajo/ReClip.git
cd ReClip
./reclip.sh
```

ReClip opens in a native desktop window. For browser/self-hosted mode, run:

```bash
RECLIP_SERVER_ONLY=1 ./reclip.sh
```

Then open **http://localhost:8899**.

### Run locally on Windows

Windows support is in source-level cross-platform mode through `pywebview`. The packaged Windows build/release pipeline is still pending.

From PowerShell:

```powershell
git clone https://github.com/Elguajo/ReClip.git
cd ReClip
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Install `ffmpeg` separately and make sure `ffmpeg.exe` and `ffprobe.exe` are on `PATH` until the Windows packaging phase bundles them. On first launch, Windows SmartScreen or WebView2 setup may prompt depending on the machine.

### Build your own macOS app

```bash
brew install python3 ffmpeg
./build-macos-app.sh
open dist/ReClip.app
```

The standalone build bundles Python dependencies, the local `ffmpeg` binary, a portable Node.js 22 runtime, and the [bgutil POT provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) JS server. The first build downloads Node and clones bgutil into `.build-cache/`; later builds reuse the cache. The resulting bundle is ad-hoc signed, not notarized.

### Run with Docker

```bash
docker build -t reclip . && docker run -p 8899:8899 reclip
```

### Continue development on another machine

Use the handoff checklist in [`docs/handoff/CONTINUE_ON_NEW_MACHINE.md`](docs/handoff/CONTINUE_ON_NEW_MACHINE.md) to clone from GitHub, recreate the local environment, run tests, and avoid committing local build artifacts.

## Usage

1. Paste one or more media URLs into the input box.
2. Choose **MP4** for video or **MP3** for audio.
3. Click **Fetch** to load metadata, thumbnails, and available qualities.
4. Choose **Maximum available** or cap a video to a detected source height.
5. Optional: choose a conversion preset.
6. Optional: enable **Keep original** if you want the source download preserved after conversion.
7. Optional: click the folder button in the top-right corner to choose the output folder.
8. Click **Download** on one item, or **Download All**.
9. Click **Show** to reveal the saved file in Finder, or use **Save As** for a browser download copy.

## Quality Detection

ReClip does not use a hardcoded quality list. During fetch, it asks `yt-dlp` for source metadata and builds the dropdown from the actual `formats` returned for that URL.

Common heights get friendly labels:

| Height | Label |
|---:|---|
| 4320 | `8K (4320p)` |
| 2160 | `4K (2160p)` |
| 1440 | `2K (1440p)` |
| 1080 | `Full HD (1080p)` |
| 720 | `HD (720p)` |
| 480 | `SD (480p)` |
| Other | `{height}p` |

Each video defaults to **Maximum available**. Selecting a height caps the download at that height while still allowing `yt-dlp` to choose the best video/audio combination at or below the cap.

## Conversion Presets

Conversion presets apply to video downloads. MP3/audio mode skips conversion and keeps the audio extraction flow focused on the original MP3 output.

For video mode, conversion runs after a successful download and writes the final deliverable into the configured output folder.

| Preset | Output | Intended use |
|---|---|---|
| No conversion | Original download | Fastest path; leaves `yt-dlp` output unchanged |
| MP4 (H.264) | `.mp4` | Broad compatibility |
| MP4 (HEVC / H.265) | `.mp4` | Smaller high-quality deliverables |
| MOV (ProRes 422) | `.mov` | AV editing workflows |
| MOV (ProRes 422 HQ) | `.mov` | Higher-bitrate AV editing workflows |

When conversion is enabled, the job enters a separate **Converting** state. If conversion fails, ReClip keeps the downloaded source file and shows a user-facing error. If conversion succeeds, the original source is removed unless **Keep original** is enabled.

## YouTube bot-checks

YouTube increasingly gates extraction behind a "Sign in to confirm you're not a bot" challenge. ReClip handles this in two ways:

**Bundled macOS app** ships with [bgutil POT provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) running in script mode against a bundled Node.js runtime. Each extraction mints a Proof-of-Origin token that satisfies the bot check without needing browser cookies or a YouTube login. The first call after launch can be slow while the token is generated; later calls reuse the cached token.

**Source / local installs** without the POT bundle fall back to reading cookies from a browser where you're already logged in. By default ReClip tries **Safari → Chrome → Firefox** per request, falling back to no cookies if all three fail. To make this work:

- Be signed in to YouTube in at least one of those browsers.
- On macOS, Safari cookies require **Full Disk Access** for the process reading them: System Settings → Privacy & Security → Full Disk Access → add Terminal.
- Chrome and Firefox should be running with the profile that has the YouTube session. On first read, Chrome may show a Keychain prompt.

Override either path with `RECLIP_YT_BROWSER`: a browser name such as `safari`, `chrome`, `firefox`, `edge`, `brave`, `chromium`, `opera`, or `vivaldi` pins to that browser with no fallback; `none` disables cookie lookup entirely.

## Supported Sites

Anything [yt-dlp supports](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md), including:

YouTube, TikTok, Instagram, Twitter/X, Reddit, Facebook, Vimeo, Twitch, Dailymotion, SoundCloud, Loom, Streamable, Pinterest, Tumblr, Threads, LinkedIn, and many more.

## Stack

- **Backend:** Python + Flask
- **Frontend:** Vanilla HTML/CSS/JS, no build step
- **Native desktop wrapper:** `pywebview` via `native.py`, backed by WKWebView on macOS and Edge WebView2 on Windows
- **Download engine:** [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- **Media processing:** [ffmpeg](https://ffmpeg.org/) + `ffprobe`
- **YouTube bot-check support in bundled macOS app:** [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) + [yt-dlp-ejs](https://github.com/yt-dlp/yt-dlp-ejs) on a bundled Node.js runtime
- **State management:** `JobManager`
- **Configuration:** `~/.reclip/config.json` for output folder, `localStorage` for frontend theme
- **Tests:** pytest

## Tests

```bash
python -m pytest -q
```

For code changes:

- Run the relevant test file first.
- Run the full suite if `app.py` or `job_manager.py` changed.
- Smoke-test the UI after frontend changes with `./reclip.sh`.

## Current Roadmap Status

- **Phase A1:** Dynamic quality detection is implemented and tested.
- **Phase A2:** Conversion presets are implemented and tested.
- **Phase A3:** pywebview migration is implemented on macOS; Windows manual validation remains open.
- **Phase A4:** Windows packaging and GitHub Actions release automation are not complete yet.

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the phased plan and acceptance criteria.

## Disclaimer

This tool is intended for personal use only. Respect copyright laws and the terms of service of the platforms you download from. The developers are not responsible for misuse of this tool.

## License

[MIT](LICENSE)
