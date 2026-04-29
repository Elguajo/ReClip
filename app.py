import os
import uuid
import glob
import shutil
import sys
import threading
from flask import Flask, request, jsonify, send_file, render_template
from yt_dlp import YoutubeDL

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


BUNDLED_BIN_DIR = _find_bundled_bin_dir()

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
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

jobs = {}


def _ffmpeg_location():
    bundled_ffmpeg = os.path.join(BUNDLED_BIN_DIR, "ffmpeg")
    if os.path.isfile(bundled_ffmpeg):
        return BUNDLED_BIN_DIR

    ffmpeg = shutil.which("ffmpeg")
    return os.path.dirname(ffmpeg) if ffmpeg else None


def _yt_dlp_options(**extra):
    opts = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    ffmpeg_dir = _ffmpeg_location()
    if ffmpeg_dir:
        opts["ffmpeg_location"] = ffmpeg_dir
    opts.update(extra)
    return opts


def run_download(job_id, url, format_choice, format_id):
    job = jobs[job_id]
    out_template = os.path.join(DOWNLOAD_DIR, f"{job_id}.%(ext)s")

    if format_choice == "audio":
        ydl_opts = _yt_dlp_options(
            outtmpl=out_template,
            format="bestaudio/best",
            postprocessors=[{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
            }],
        )
    elif format_id:
        ydl_opts = _yt_dlp_options(
            outtmpl=out_template,
            format=f"{format_id}+bestaudio/best",
            merge_output_format="mp4",
        )
    else:
        ydl_opts = _yt_dlp_options(
            outtmpl=out_template,
            format="bestvideo+bestaudio/best",
            merge_output_format="mp4",
        )

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{job_id}.*"))
        if not files:
            job["status"] = "error"
            job["error"] = "Download completed but no file was found"
            return

        if format_choice == "audio":
            target = [f for f in files if f.endswith(".mp3")]
            chosen = target[0] if target else files[0]
        else:
            target = [f for f in files if f.endswith(".mp4")]
            chosen = target[0] if target else files[0]

        for f in files:
            if f != chosen:
                try:
                    os.remove(f)
                except OSError:
                    pass

        job["status"] = "done"
        job["file"] = chosen
        ext = os.path.splitext(chosen)[1]
        title = job.get("title", "").strip()
        # Sanitize title for filename
        if title:
            safe_title = "".join(c for c in title if c not in r'\/:*?"<>|').strip()[:20].strip()
            job["filename"] = f"{safe_title}{ext}" if safe_title else os.path.basename(chosen)
        else:
            job["filename"] = os.path.basename(chosen)
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/info", methods=["POST"])
def get_info():
    data = request.json
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        with YoutubeDL(_yt_dlp_options(skip_download=True)) as ydl:
            info = ydl.extract_info(url, download=False)

        # Build quality options — keep best format per resolution
        best_by_height = {}
        for f in info.get("formats", []):
            height = f.get("height")
            if height and f.get("vcodec", "none") != "none":
                tbr = f.get("tbr") or 0
                if height not in best_by_height or tbr > (best_by_height[height].get("tbr") or 0):
                    best_by_height[height] = f

        formats = []
        for height, f in best_by_height.items():
            formats.append({
                "id": f["format_id"],
                "label": f"{height}p",
                "height": height,
            })
        formats.sort(key=lambda x: x["height"], reverse=True)

        return jsonify({
            "title": info.get("title", ""),
            "thumbnail": info.get("thumbnail", ""),
            "duration": info.get("duration"),
            "uploader": info.get("uploader", ""),
            "formats": formats,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.json
    url = data.get("url", "").strip()
    format_choice = data.get("format", "video")
    format_id = data.get("format_id")
    title = data.get("title", "")

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    job_id = uuid.uuid4().hex[:10]
    jobs[job_id] = {"status": "downloading", "url": url, "title": title}

    thread = threading.Thread(target=run_download, args=(job_id, url, format_choice, format_id))
    thread.daemon = True
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def check_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "status": job["status"],
        "error": job.get("error"),
        "filename": job.get("filename"),
    })


@app.route("/api/file/<job_id>")
def download_file(job_id):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "File not ready"}), 404
    return send_file(job["file"], as_attachment=True, download_name=job["filename"])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8899))
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(host=host, port=port)
