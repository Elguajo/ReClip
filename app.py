import os
import glob
import json
import re
import shutil
import subprocess
import sys
import threading
from urllib.parse import urlparse
from flask import Flask, request, jsonify, send_file, render_template, make_response
from yt_dlp import YoutubeDL
from job_manager import DownloadCancelled, JobManager
from presets import CONVERSION_PRESETS, get_preset, is_no_op

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _runtime_roots():
    roots = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(meipass)

    if getattr(sys, "frozen", False):
        contents_dir = os.path.dirname(os.path.dirname(sys.executable))
        roots.extend([
            os.path.join(contents_dir, "Resources"),
            os.path.join(contents_dir, "Frameworks"),
            contents_dir,
        ])

    roots.append(APP_DIR)
    return roots


def _find_runtime_dir(name):
    for root in _runtime_roots():
        candidate = os.path.join(root, name)
        if os.path.isdir(candidate):
            return candidate
    return os.path.join(APP_DIR, name)


def _find_bundled_bin_dir():
    for root in _runtime_roots():
        candidate = os.path.join(root, "bin")
        if os.path.isfile(os.path.join(candidate, "ffmpeg")):
            return candidate
    return os.path.join(APP_DIR, "bin")


def _find_bgutil_server_dir():
    # Bundled layout: bgutil-server/{node (bun renamed), build/generate_once.js (bun-bundled JS)}.
    for root in _runtime_roots():
        candidate = os.path.join(root, "bgutil-server")
        if os.path.isfile(os.path.join(candidate, "build", "generate_once.js")) \
                and os.path.isfile(os.path.join(candidate, "node")):
            return candidate
    return None


BUNDLED_BIN_DIR = _find_bundled_bin_dir()
BGUTIL_SERVER_DIR = _find_bgutil_server_dir()
BGUTIL_NODE_PATH = (
    os.path.join(BGUTIL_SERVER_DIR, "node") if BGUTIL_SERVER_DIR else None
)

if os.path.isdir(BUNDLED_BIN_DIR):
    os.environ["PATH"] = BUNDLED_BIN_DIR + os.pathsep + os.environ.get("PATH", "")

try:
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except Exception:
    pass

app = Flask(
    __name__,
    template_folder=_find_runtime_dir("templates"),
    static_folder=_find_runtime_dir("static"),
)
DOWNLOAD_DIR = os.environ.get(
    "RECLIP_DOWNLOAD_DIR",
    os.path.join(os.path.expanduser("~"), "Downloads", "ReClip")
    if getattr(sys, "frozen", False)
    else os.path.join(APP_DIR, "downloads"),
)
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".reclip", "config.json")
TEMP_DOWNLOAD_DIR = os.path.join(APP_DIR, "downloads")


def _load_download_dir():
    if os.environ.get("RECLIP_DOWNLOAD_DIR"):
        return os.environ["RECLIP_DOWNLOAD_DIR"]
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            configured = json.load(f).get("download_dir")
        if isinstance(configured, str) and configured.strip():
            return os.path.expanduser(configured)
    except (OSError, ValueError, TypeError):
        pass
    return DOWNLOAD_DIR


def _set_download_dir(path):
    global DOWNLOAD_DIR
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Download folder cannot be empty")
    path = os.path.abspath(os.path.expanduser(path))
    os.makedirs(path, exist_ok=True)
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"download_dir": path}, f)
    DOWNLOAD_DIR = path
    return DOWNLOAD_DIR


DOWNLOAD_DIR = _load_download_dir()
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)

jobs = JobManager()


def _request_data():
    return request.get_json(silent=True) or {}


def _string_field(data, key, default=""):
    value = data.get(key, default)
    return value.strip() if isinstance(value, str) else default


def _clean_old_jobs():
    jobs.prune_terminal()


def _valid_url(url):
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _ffmpeg_location():
    bundled_ffmpeg = os.path.join(BUNDLED_BIN_DIR, "ffmpeg")
    if os.path.isfile(bundled_ffmpeg):
        return BUNDLED_BIN_DIR

    ffmpeg = shutil.which("ffmpeg")
    return os.path.dirname(ffmpeg) if ffmpeg else None


def _ffmpeg_binary():
    bundled = os.path.join(BUNDLED_BIN_DIR, "ffmpeg")
    if os.path.isfile(bundled):
        return bundled
    return shutil.which("ffmpeg")


def _ffprobe_binary():
    bundled = os.path.join(BUNDLED_BIN_DIR, "ffprobe")
    if os.path.isfile(bundled):
        return bundled
    return shutil.which("ffprobe")


def _ffprobe_duration(path):
    """Return the media duration in seconds, or None if unknown."""
    binary = _ffprobe_binary()
    if not binary:
        return None
    try:
        result = subprocess.run(
            [
                binary, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1",
                path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        out = result.stdout.strip()
        return float(out) if out else None
    except (ValueError, subprocess.SubprocessError, OSError):
        return None


def _run_ffmpeg_convert(job_id, source_path, output_path, preset_args, popen=None):
    """Run ffmpeg to convert source_path → output_path, streaming progress to JobManager.

    Returns (ok, error_message). ok=True on a clean exit; ok=False on cancellation
    or non-zero ffmpeg exit. Caller is responsible for cleanup of the partial output.
    """
    binary = _ffmpeg_binary()
    if not binary:
        return False, "ffmpeg not found"

    duration = _ffprobe_duration(source_path)

    cmd = [
        binary, "-y",
        "-i", source_path,
        *preset_args,
        "-progress", "pipe:1",
        "-nostats",
        "-loglevel", "error",
        output_path,
    ]

    proc = (popen or subprocess.Popen)(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    cancelled = False
    try:
        for line in proc.stdout or ():
            if jobs.is_cancelled(job_id):
                cancelled = True
                break

            secs = _parse_ffmpeg_progress_line(line)
            if secs is not None and duration:
                pct = max(0, min(99, int(secs / duration * 100)))
                try:
                    jobs.update_progress(job_id, {
                        "progress": pct,
                        "speed": None,
                        "eta": None,
                    })
                except DownloadCancelled:
                    cancelled = True
                    break

        if cancelled:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            except Exception:
                pass
            return False, "cancelled"

        proc.wait()
        if proc.returncode != 0:
            err = (proc.stderr.read() if proc.stderr else "").strip()
            return False, err or f"ffmpeg exited with code {proc.returncode}"
        return True, None
    finally:
        for stream in (proc.stdout, proc.stderr):
            try:
                if stream:
                    stream.close()
            except Exception:
                pass


def _parse_ffmpeg_progress_line(line):
    """Parse `out_time_us=...` lines emitted by `ffmpeg -progress pipe:1`.

    Returns the elapsed seconds, or None for any other line.
    """
    if not line:
        return None
    line = line.strip()
    if not line.startswith("out_time_us="):
        return None
    try:
        return int(line.split("=", 1)[1]) / 1_000_000
    except (ValueError, IndexError):
        return None


_KNOWN_BROWSERS = {"safari", "chrome", "chromium", "firefox", "edge", "brave", "opera", "vivaldi"}
_FRAGMENT_RE = re.compile(r"\.f\d+\.")


def _browser_candidates():
    # RECLIP_YT_BROWSER: 'none' disables cookies; a browser name pins to that one.
    # Bundled builds use the bgutil POT provider, so avoid browser cookies by
    # default. On macOS those cookie reads can trigger repeated Keychain prompts.
    override = os.environ.get("RECLIP_YT_BROWSER", "").strip().lower()
    if override == "none":
        return [None]
    if override in _KNOWN_BROWSERS:
        return [override]
    if BGUTIL_SERVER_DIR:
        return [None]
    if sys.platform == "darwin":
        return ["safari", "chrome", "firefox", None]
    return ["chrome", "firefox", None]


def _yt_dlp_options(_browser=None, **extra):
    opts = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    ffmpeg_dir = _ffmpeg_location()
    if ffmpeg_dir:
        opts["ffmpeg_location"] = ffmpeg_dir
    if _browser:
        opts["cookiesfrombrowser"] = (_browser,)
    if BGUTIL_SERVER_DIR:
        # bgutil-ytdlp-pot-provider (script mode) — bypasses YouTube bot check
        # by minting a PO token via the bundled JS server. Pinning the player
        # to `mweb` is the combo recommended by upstream so the generated
        # token is actually consumed (other clients like web_safari need
        # extra Visitor Data and fall back to the bot-check path).
        opts.setdefault("extractor_args", {})
        opts["extractor_args"].setdefault(
            "youtubepot-bgutilscript", {"server_home": [BGUTIL_SERVER_DIR]}
        )
        opts["extractor_args"].setdefault("youtube", {"player_client": ["mweb"]})
        # We ship Bun renamed as `node` inside bgutil-server/. Point yt-dlp at
        # it explicitly so neither the bgutil plugin's `node generate_once.js`
        # call nor yt-dlp's own n-signature/EJS fallback path picks up a
        # system Node (which may be missing on a clean user machine).
        opts.setdefault("js_runtimes", {"node": {"path": BGUTIL_NODE_PATH}})
    opts.update(extra)
    return opts


def _yt_dlp_run(action, **opts_extra):
    # Try each browser in _browser_candidates(); on any failure, fall through
    # to the next. DownloadCancelled bypasses the retry loop.
    last_exc = None
    for browser in _browser_candidates():
        opts = _yt_dlp_options(_browser=browser, **opts_extra)
        try:
            with YoutubeDL(opts) as ydl:
                return action(ydl)
        except DownloadCancelled:
            raise
        except Exception as exc:
            last_exc = exc
    raise last_exc


HEIGHT_LABELS = {
    4320: "8K (4320p)",
    2160: "4K (2160p)",
    1440: "2K (1440p)",
    1080: "Full HD (1080p)",
    720:  "HD (720p)",
    480:  "SD (480p)",
    360:  "360p",
    240:  "240p",
    144:  "144p",
}


def format_height(height):
    """Friendly label for a video height (e.g. 2160 → '4K (2160p)').

    Unknown heights fall back to '{height}p' so non-standard sources
    (3072, 6K, 16K, irregular) still render usefully.
    """
    return HEIGHT_LABELS.get(height, f"{height}p")


def build_format_string(max_height):
    """Build a yt-dlp format selector string capped at the given height.

    None → 'bv*+ba/b' (best available video + best audio, fallback to best combined).
    Positive int → 'bv*[height<=N]+ba/b[height<=N]'.
    Raises ValueError for non-positive or non-integer input.
    """
    if max_height is None:
        return "bv*+ba/b"
    if not isinstance(max_height, int) or max_height <= 0:
        raise ValueError(
            f"max_height must be a positive integer or None, got {max_height!r}"
        )
    return f"bv*[height<={max_height}]+ba/b[height<={max_height}]"


def _format_filename(title, chosen):
    ext = os.path.splitext(chosen)[1]
    title = title.strip()
    if not title:
        return os.path.basename(chosen)

    safe_title = "".join(c for c in title if c not in r'\/:*?"<>|').strip()[:120].strip()
    return f"{safe_title}{ext}" if safe_title else os.path.basename(chosen)


def _unique_destination(filename):
    target = os.path.join(DOWNLOAD_DIR, filename)
    if not os.path.exists(target):
        return target, filename

    stem, ext = os.path.splitext(filename)
    counter = 2
    while True:
        candidate_name = f"{stem} ({counter}){ext}"
        candidate = os.path.join(DOWNLOAD_DIR, candidate_name)
        if not os.path.exists(candidate):
            return candidate, candidate_name
        counter += 1


def _cleanup_job_files(job_id, keep=None):
    for file_path in glob.glob(os.path.join(TEMP_DOWNLOAD_DIR, f"{job_id}.*")):
        if file_path == keep:
            continue
        try:
            os.remove(file_path)
        except OSError:
            pass


def _progress_hook(job_id):
    def hook(data):
        if jobs.is_cancelled(job_id):
            raise DownloadCancelled()

        if data.get("status") != "downloading":
            return

        total = data.get("total_bytes") or data.get("total_bytes_estimate")
        downloaded = data.get("downloaded_bytes") or 0
        percent = int(downloaded * 100 / total) if total else 0
        jobs.update_progress(job_id, {
            "progress": min(percent, 99),
            "downloaded_bytes": downloaded,
            "total_bytes": total,
            "speed": data.get("speed"),
            "eta": data.get("eta"),
        })

    return hook


def run_download(job_id, url, format_choice, max_height, convert_preset="none", keep_original=False):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
    out_template = os.path.join(TEMP_DOWNLOAD_DIR, f"{job_id}.%(ext)s")

    if format_choice == "audio":
        opts_extra = dict(
            outtmpl=out_template,
            format="bestaudio/best",
            progress_hooks=[_progress_hook(job_id)],
            postprocessors=[{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
            }],
        )
        # Conversion presets are video-only.
        convert_preset = "none"
    else:
        opts_extra = dict(
            outtmpl=out_template,
            format=build_format_string(max_height),
            progress_hooks=[_progress_hook(job_id)],
        )

    try:
        _yt_dlp_run(lambda ydl: ydl.download([url]), **opts_extra)

        if jobs.is_cancelled(job_id):
            _cleanup_job_files(job_id)
            return

        files = glob.glob(os.path.join(TEMP_DOWNLOAD_DIR, f"{job_id}.*"))
        if not files:
            jobs.mark_error(job_id, "Download completed but no file was found")
            return

        if format_choice == "audio":
            target = [f for f in files if f.endswith(".mp3")]
            chosen = target[0] if target else files[0]
        else:
            # Skip yt-dlp's per-stream fragment files ({job_id}.fNNN.ext) so we pick
            # the merged output regardless of container (mp4/webm/mkv).
            non_fragment = [f for f in files if not _FRAGMENT_RE.search(os.path.basename(f))]
            chosen = non_fragment[0] if non_fragment else files[0]

        job = jobs.snapshot(job_id) or {}
        title = job.get("title", "")

        preset = get_preset(convert_preset)
        if not is_no_op(preset):
            _run_convert_step(job_id, chosen, title, preset, keep_original)
            return

        final_name = _format_filename(title, chosen)
        final_path, final_name = _unique_destination(final_name)
        shutil.move(chosen, final_path)
        _cleanup_job_files(job_id)

        if not jobs.mark_done(job_id, final_path, final_name):
            try:
                os.remove(final_path)
            except OSError:
                pass
    except DownloadCancelled:
        _cleanup_job_files(job_id)
    except Exception as e:
        jobs.mark_error(job_id, str(e))


def _run_convert_step(job_id, source_path, title, preset, keep_original):
    """Convert `source_path` with `preset`, finalize destination, update job state.

    Decisions on failure:
      - cancelled mid-convert → cleanup partials, leave job in 'cancelled' state
      - ffmpeg non-zero exit → preserve the original download in DOWNLOAD_DIR,
        cleanup the partial converted output, transition job to 'error' with
        the ffmpeg stderr summary
    """
    if not jobs.mark_converting(job_id):
        # Already cancelled or torn down between download and convert.
        _cleanup_job_files(job_id)
        return

    convert_output = os.path.join(
        TEMP_DOWNLOAD_DIR, f"{job_id}.converted.{preset['ext']}"
    )

    ok, err = _run_ffmpeg_convert(job_id, source_path, convert_output, preset["args"])

    if jobs.is_cancelled(job_id):
        for path in (source_path, convert_output):
            try:
                os.remove(path)
            except OSError:
                pass
        _cleanup_job_files(job_id)
        return

    if not ok:
        # Convert failed: preserve the original so the user doesn't lose the download.
        try:
            os.remove(convert_output)
        except OSError:
            pass
        rescued_name = _format_filename(title, source_path)
        rescued_dest, _ = _unique_destination(rescued_name)
        try:
            shutil.move(source_path, rescued_dest)
        except OSError:
            pass
        _cleanup_job_files(job_id)
        jobs.mark_error(job_id, f"Conversion failed: {err}" if err else "Conversion failed")
        return

    # Convert succeeded.
    converted_name_base = _format_filename(title, f"x.{preset['ext']}")
    converted_dest, converted_name = _unique_destination(converted_name_base)
    shutil.move(convert_output, converted_dest)

    if keep_original:
        original_name_base = _format_filename(title, source_path)
        original_dest, _ = _unique_destination(original_name_base)
        try:
            shutil.move(source_path, original_dest)
        except OSError:
            pass
    else:
        try:
            os.remove(source_path)
        except OSError:
            pass

    _cleanup_job_files(job_id)

    if not jobs.mark_done(job_id, converted_dest, converted_name):
        try:
            os.remove(converted_dest)
        except OSError:
            pass


@app.route("/")
def index():
    # no-store on the shell prevents WKWebView (and browsers) from serving a
    # stale UI after the app/template is updated — the rest is JSON APIs
    # that aren't cached anyway.
    resp = make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/api/config")
def get_config():
    return jsonify({"download_dir": DOWNLOAD_DIR})


@app.route("/api/select-folder", methods=["POST"])
def select_folder():
    script = (
        'POSIX path of (choose folder with prompt '
        '"Choose where ReClip should save downloads")'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return jsonify({"cancelled": True, "download_dir": DOWNLOAD_DIR})
        chosen = result.stdout.strip()
        if not chosen:
            return jsonify({"cancelled": True, "download_dir": DOWNLOAD_DIR})
        return jsonify({"download_dir": _set_download_dir(chosen)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/open-folder", methods=["POST"])
def open_folder():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    try:
        subprocess.Popen(["open", DOWNLOAD_DIR])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reveal/<job_id>", methods=["POST"])
def reveal_file(job_id):
    job = jobs.snapshot(job_id)
    file_path = job.get("file") if job else None
    if not file_path or not os.path.isfile(file_path):
        return jsonify({"error": "File not found"}), 404
    try:
        subprocess.Popen(["open", "-R", file_path])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/info", methods=["POST"])
def get_info():
    _clean_old_jobs()
    data = _request_data()
    url = _string_field(data, "url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    if not _valid_url(url):
        return jsonify({"error": "Only http(s) URLs are supported"}), 400

    try:
        info = _yt_dlp_run(lambda ydl: ydl.extract_info(url, download=False), skip_download=True)

        # Group video formats by height; per height the size estimate is the max of
        # filesize/filesize_approx across all formats at that height. Heights with no
        # size info still appear (filesize=None) so the dropdown stays complete.
        sizes_by_height = {}
        for f in info.get("formats", []):
            height = f.get("height")
            if not height or f.get("vcodec", "none") == "none":
                continue
            size = f.get("filesize") or f.get("filesize_approx")
            if size is not None:
                current = sizes_by_height.get(height)
                if current is None or size > current:
                    sizes_by_height[height] = size
            else:
                sizes_by_height.setdefault(height, None)

        formats = [
            {"height": h, "label": format_height(h), "filesize": sizes_by_height[h]}
            for h in sorted(sizes_by_height.keys(), reverse=True)
        ]

        return jsonify({
            "title": info.get("title", ""),
            "thumbnail": info.get("thumbnail", ""),
            "duration": info.get("duration"),
            "uploader": info.get("uploader", ""),
            "formats": formats,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/presets")
def list_presets():
    return jsonify({
        "presets": [
            {"id": p["id"], "label": p["label"], "ext": p["ext"]}
            for p in CONVERSION_PRESETS
        ]
    })


@app.route("/api/download", methods=["POST"])
def start_download():
    _clean_old_jobs()
    data = _request_data()
    url = _string_field(data, "url")
    format_choice = _string_field(data, "format", "video")
    max_height = data.get("max_height")
    title = data.get("title", "")
    convert_preset = _string_field(data, "convert_preset", "none") or "none"
    keep_original = bool(data.get("keep_original", False))

    if not url:
        return jsonify({"error": "No URL provided"}), 400
    if not _valid_url(url):
        return jsonify({"error": "Only http(s) URLs are supported"}), 400
    if format_choice not in {"video", "audio"}:
        return jsonify({"error": "Format must be video or audio"}), 400
    if max_height is not None:
        if (
            not isinstance(max_height, int)
            or isinstance(max_height, bool)
            or max_height <= 0
        ):
            return jsonify({"error": "max_height must be a positive integer or null"}), 400
    try:
        get_preset(convert_preset)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not isinstance(title, str):
        title = ""

    job_id = jobs.create(url, title)

    thread = threading.Thread(
        target=run_download,
        args=(job_id, url, format_choice, max_height, convert_preset, keep_original),
    )
    thread.daemon = True
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def check_status(job_id):
    _clean_old_jobs()
    job = jobs.snapshot(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "status": job["status"],
        "progress": job.get("progress", 0),
        "speed": job.get("speed"),
        "eta": job.get("eta"),
        "error": job.get("error"),
        "filename": job.get("filename"),
    })


@app.route("/api/cancel/<job_id>", methods=["POST"])
def cancel_download(job_id):
    job = jobs.cancel(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"status": job["status"]})


@app.route("/api/file/<job_id>")
def download_file(job_id):
    job = jobs.snapshot(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "File not ready"}), 404
    return send_file(job["file"], as_attachment=True, download_name=job["filename"])


def _truthy_env(name):
    """Return True when an environment flag is set to a truthy value."""
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _should_run_server_only(host):
    """Return True when ReClip should expose Flask without a native window."""
    return _truthy_env("RECLIP_SERVER_ONLY") or host not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }


def main():
    """Start ReClip in native desktop mode unless server-only mode is requested."""
    port = int(os.environ.get("PORT", 8899))
    host = os.environ.get("HOST", "127.0.0.1")

    if _should_run_server_only(host):
        app.run(host=host, port=port)
        return

    from native import main as native_main

    native_main()


if __name__ == "__main__":
    main()
