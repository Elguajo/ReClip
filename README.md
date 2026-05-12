# ReClip

A self-hosted, open-source video and audio downloader with a clean web UI. Paste links from YouTube, TikTok, Instagram, Twitter/X, and 1000+ other sites — download as MP4 or MP3.

This fork keeps the original lightweight Flask + vanilla UI approach, but adds
macOS-focused quality-of-life features, safer download handling, and tests.

![Python](https://img.shields.io/badge/python-3.8+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

![ReClip MP3 Mode](assets/preview-mp3.png)

## Features

- Download videos from 1000+ supported sites (via [yt-dlp](https://github.com/yt-dlp/yt-dlp))
- MP4 video or MP3 audio extraction
- Quality/resolution picker
- Bulk downloads — paste multiple URLs at once
- Automatic URL deduplication
- Choose where downloaded files are saved
- Reveal a finished file in Finder
- Light/dark theme toggle with saved preference
- Native macOS app wrapper with a WKWebView window
- Progress, cancel, retry, and safer job state handling
- Clean, responsive UI — no frameworks, no build step

## What This Fork Adds

Compared with the original ReClip repo, this fork adds:

- **Configurable save location:** use the folder button in the top-right corner
  to choose where ReClip saves completed downloads. The choice is persisted in
  `~/.reclip/config.json`.
- **Finder action:** click **Show** after a download finishes to reveal the saved
  file in Finder.
- **Dark theme:** a top-right theme button toggles light/dark mode and stores the
  preference in `localStorage`.
- **Safer download pipeline:** files are downloaded to an internal temp folder,
  then moved into the configured destination only after `yt-dlp` finishes.
- **Duplicate-safe filenames:** existing files are not overwritten; duplicates
  are saved as `Name (2).mp4`, `Name (3).mp4`, and so on.
- **Job manager:** download progress, cancellation, completion, errors, and
  cleanup are handled through a dedicated `JobManager` instead of loose globals.
- **Regression tests:** API and job lifecycle tests cover URL validation, format
  parsing, save-folder behavior, final file movement, duplicate naming, and
  cancellation.
- **macOS launcher behavior:** the app launcher respects the saved folder instead
  of resetting downloads to the default path on every launch.

## Quick Start

### Download for macOS

Download the latest `ReClip-*-macOS.zip` from
[GitHub Releases](https://github.com/Elguajo/ReClip/releases), unzip it, and
move `ReClip.app` to `/Applications`.

After installation: press **Cmd+Space**, type **ReClip**, and launch it.

The release build bundles Python dependencies and `ffmpeg`, so you do not need
to clone the repository or run an install script.

Pre-built app bundles are published as GitHub release artifacts, not committed
to the source repository. Local builds create `dist/ReClip.app`.

If macOS blocks the app because it is not notarized yet, remove quarantine for
this app only:

```bash
xattr -dr com.apple.quarantine /Applications/ReClip.app
```

### Run locally in a browser

```bash
brew install yt-dlp ffmpeg    # or apt install ffmpeg && pip install yt-dlp
git clone https://github.com/Elguajo/ReClip.git
cd ReClip
./reclip.sh
```

Open **http://localhost:8899**.

### Build your own macOS app

```bash
brew install python3 ffmpeg
./build-macos-app.sh
open dist/ReClip.app
```

The standalone build bundles Python dependencies, the local `ffmpeg`
binary, a portable Node.js 22 runtime, and the
[bgutil POT provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider)
JS server (see *YouTube bot-checks* below). The first build downloads Node
and clones bgutil into `.build-cache/`; subsequent builds reuse the cache
and finish in ~30s. The resulting bundle is ~220MB and is ad-hoc signed,
not notarized.

### Run with Docker

```bash
docker build -t reclip . && docker run -p 8899:8899 reclip
```

### Continue development on another machine

Use the handoff checklist in
[`docs/handoff/CONTINUE_ON_NEW_MACHINE.md`](docs/handoff/CONTINUE_ON_NEW_MACHINE.md)
to clone from GitHub, recreate the local environment, run tests, and avoid
committing local build artifacts.

## Usage

1. Paste one or more video URLs into the input box
2. Choose **MP4** (video) or **MP3** (audio)
3. Click **Fetch** to load video info and thumbnails
4. Select quality/resolution if available
5. Optional: click the folder button in the top-right corner to choose a save folder
6. Click **Download** on individual videos, or **Download All**
7. Click **Show** to reveal the saved file in Finder, or use **Save As** for a browser download copy

## YouTube bot-checks

YouTube increasingly gates extraction behind a "Sign in to confirm you're not a bot" challenge. ReClip handles this in two ways:

**Bundled macOS app** ships with [bgutil POT provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) running in script mode against a bundled Node.js runtime. Each extraction mints a Proof-of-Origin token that satisfies the bot check without needing browser cookies or a YouTube login. The first call after launch is slow (~60–90s) while the token is generated; subsequent calls reuse the cached token (TTL 6h, stored in `~/.cache/bgutil-ytdlp-pot-provider/`).

**Source / local installs** without the POT bundle fall back to reading cookies from a browser where you're already logged in. By default ReClip tries **Safari → Chrome → Firefox** per request, falling back to no cookies if all three fail. To make this work:

- Be signed in to YouTube in at least one of those browsers.
- On macOS, Safari cookies require **Full Disk Access** for the process reading them (System Settings → Privacy & Security → Full Disk Access → add Terminal). Chrome/Firefox should be running with the profile that has the YouTube session; on first read, Chrome may show a Keychain prompt.

Override either path with `RECLIP_YT_BROWSER`: a specific browser name (`safari`, `chrome`, `firefox`, `edge`, `brave`, `chromium`, `opera`, `vivaldi`) pins to that one with no fallback; `none` disables the cookie lookup entirely (recommended when running the bundled `.app`, since the POT provider already handles the bot check).

## Supported Sites

Anything [yt-dlp supports](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md), including:

YouTube, TikTok, Instagram, Twitter/X, Reddit, Facebook, Vimeo, Twitch, Dailymotion, SoundCloud, Loom, Streamable, Pinterest, Tumblr, Threads, LinkedIn, and many more.

## Stack

- **Backend:** Python + Flask
- **Frontend:** Vanilla HTML/CSS/JS (single file, no build step)
- **Native macOS wrapper:** PyObjC + WKWebView (`native.py`); experimental pywebview migration launcher in `native_pywebview.py`
- **Download engine:** [yt-dlp](https://github.com/yt-dlp/yt-dlp) + [ffmpeg](https://ffmpeg.org/)
- **YouTube bot-check bypass (bundled `.app` only):** [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) + [yt-dlp-ejs](https://github.com/yt-dlp/yt-dlp-ejs) running on a bundled Node.js 22 runtime
- **Dependencies:** Flask, pywebview, yt-dlp, yt-dlp-ejs, bgutil-ytdlp-pot-provider, certifi, and macOS-only PyObjC packages
- **Tests:** pytest

## Tests

```bash
python -m pytest -q
```

## Disclaimer

This tool is intended for personal use only. Please respect copyright laws and the terms of service of the platforms you download from. The developers are not responsible for any misuse of this tool.

## License

[MIT](LICENSE)
