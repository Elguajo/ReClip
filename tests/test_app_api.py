import io
import os
import json

import app as reclip_app
from job_manager import JobManager


class InlineThread:
    def __init__(self, target, args):
        self.target = target
        self.args = args
        self.daemon = False

    def start(self):
        self.target(*self.args)


def make_client(tmp_path, monkeypatch):
    reclip_app.jobs = JobManager()
    monkeypatch.setattr(reclip_app, "DOWNLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(reclip_app, "TEMP_DOWNLOAD_DIR", str(tmp_path / "tmp"))
    monkeypatch.setattr(reclip_app, "CONFIG_PATH", str(tmp_path / "config.json"))
    reclip_app.app.config.update(TESTING=True)
    return reclip_app.app.test_client()


def test_index_sends_no_store_header(tmp_path, monkeypatch):
    # WKWebView/browsers must not cache the shell across rebuilds — otherwise
    # a freshly-built .app can serve a stale UI from WebKit's disk cache.
    client = make_client(tmp_path, monkeypatch)

    res = client.get("/")

    assert res.status_code == 200
    assert "no-store" in res.headers.get("Cache-Control", "")


def test_info_rejects_invalid_json(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    res = client.post("/api/info", data="not-json", content_type="application/json")

    assert res.status_code == 400
    assert res.get_json()["error"] == "No URL provided"


def test_bundled_pot_provider_disables_browser_cookie_reads(monkeypatch):
    monkeypatch.delenv("RECLIP_YT_BROWSER", raising=False)
    monkeypatch.setattr(reclip_app, "BGUTIL_SERVER_DIR", "/bundle/bgutil-server")

    assert reclip_app._browser_candidates() == [None]


def test_browser_override_still_works_with_bundled_pot_provider(monkeypatch):
    monkeypatch.setenv("RECLIP_YT_BROWSER", "chrome")
    monkeypatch.setattr(reclip_app, "BGUTIL_SERVER_DIR", "/bundle/bgutil-server")

    assert reclip_app._browser_candidates() == ["chrome"]


def test_source_run_keeps_browser_cookie_fallbacks_on_macos(monkeypatch):
    monkeypatch.delenv("RECLIP_YT_BROWSER", raising=False)
    monkeypatch.setattr(reclip_app, "BGUTIL_SERVER_DIR", None)
    monkeypatch.setattr(reclip_app.sys, "platform", "darwin")

    assert reclip_app._browser_candidates() == ["safari", "chrome", "firefox", None]


def test_info_returns_heights_with_labels_and_size_estimates(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url, download):
            return {
                "title": "Demo",
                "thumbnail": "https://example.com/thumb.jpg",
                "duration": 65,
                "uploader": "Uploader",
                "formats": [
                    # 8K — single format, exact filesize
                    {"format_id": "8k", "height": 4320, "vcodec": "av01", "filesize": 4_500_000_000},
                    # 4K — two video formats; size estimate must be the max across both,
                    # mixing filesize and filesize_approx
                    {"format_id": "4k-low", "height": 2160, "vcodec": "avc1", "filesize": 800_000_000},
                    {"format_id": "4k-hi",  "height": 2160, "vcodec": "av01", "filesize_approx": 900_000_000},
                    # 1080
                    {"format_id": "fhd", "height": 1080, "vcodec": "avc1", "filesize": 350_000_000},
                    # 720 — no size info at all
                    {"format_id": "hd", "height": 720, "vcodec": "avc1"},
                    # Audio-only formats — must be filtered out (no height / vcodec=none)
                    {"format_id": "audio1", "vcodec": "none", "acodec": "mp4a", "filesize": 5_000_000},
                    {"format_id": "audio2", "vcodec": "none", "acodec": "opus", "filesize": 4_000_000},
                    # Format with no height — must be filtered out
                    {"format_id": "weird", "vcodec": "avc1", "filesize": 1_000_000},
                ],
            }

    monkeypatch.setattr(reclip_app, "YoutubeDL", FakeYDL)

    res = client.post("/api/info", json={"url": "https://example.com/watch?v=1"})

    assert res.status_code == 200
    body = res.get_json()
    assert body["title"] == "Demo"
    assert body["formats"] == [
        {"height": 4320, "label": "8K (4320p)",     "filesize": 4_500_000_000},
        {"height": 2160, "label": "4K (2160p)",     "filesize": 900_000_000},
        {"height": 1080, "label": "Full HD (1080p)", "filesize": 350_000_000},
        {"height": 720,  "label": "HD (720p)",      "filesize": None},
    ]


def test_info_includes_irregular_heights_with_raw_label(tmp_path, monkeypatch):
    # Future-proofs sources that report non-standard heights (e.g. 3072 instead of 2160).
    client = make_client(tmp_path, monkeypatch)

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url, download):
            return {
                "title": "Irregular",
                "formats": [
                    {"format_id": "weird", "height": 3072, "vcodec": "avc1"},
                    {"format_id": "fhd",   "height": 1080, "vcodec": "avc1"},
                ],
            }

    monkeypatch.setattr(reclip_app, "YoutubeDL", FakeYDL)

    res = client.post("/api/info", json={"url": "https://example.com/watch?v=2"})

    assert res.status_code == 200
    assert res.get_json()["formats"] == [
        {"height": 3072, "label": "3072p",          "filesize": None},
        {"height": 1080, "label": "Full HD (1080p)", "filesize": None},
    ]


def test_download_validation_rejects_bad_input(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    bad_url = client.post("/api/download", json={"url": "file:///tmp/demo.mp4"})
    bad_format = client.post(
        "/api/download",
        json={"url": "https://example.com/video", "format": "gif"},
    )

    assert bad_url.status_code == 400
    assert bad_url.get_json()["error"] == "Only http(s) URLs are supported"
    assert bad_format.status_code == 400
    assert bad_format.get_json()["error"] == "Format must be video or audio"


def test_download_status_and_file_flow(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    def fake_run_download(job_id, url, format_choice, max_height, convert_preset="none", keep_original=False):
        file_path = tmp_path / f"{job_id}.mp4"
        file_path.write_bytes(b"video")
        reclip_app.jobs.mark_done(job_id, str(file_path), "Demo.mp4")

    monkeypatch.setattr(reclip_app.threading, "Thread", InlineThread)
    monkeypatch.setattr(reclip_app, "run_download", fake_run_download)

    start = client.post(
        "/api/download",
        json={"url": "https://example.com/video", "format": "video", "title": "Demo"},
    )
    job_id = start.get_json()["job_id"]
    status = client.get(f"/api/status/{job_id}")
    file_res = client.get(f"/api/file/{job_id}")

    assert start.status_code == 200
    assert status.get_json()["status"] == "done"
    assert status.get_json()["progress"] == 100
    assert file_res.status_code == 200
    assert file_res.data == b"video"


def test_select_folder_persists_config(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    chosen = tmp_path / "chosen"

    class Result:
        returncode = 0
        stdout = f"{chosen}\n"

    monkeypatch.setattr(reclip_app.subprocess, "run", lambda *args, **kwargs: Result())

    res = client.post("/api/select-folder")
    config = client.get("/api/config")

    assert res.status_code == 200
    assert res.get_json()["download_dir"] == str(chosen)
    assert config.get_json()["download_dir"] == str(chosen)
    with open(tmp_path / "config.json", encoding="utf-8") as f:
        assert json.load(f) == {"download_dir": str(chosen)}


def test_select_folder_cancel_keeps_current_dir(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    class Result:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(reclip_app.subprocess, "run", lambda *args, **kwargs: Result())

    res = client.post("/api/select-folder")

    assert res.status_code == 200
    assert res.get_json() == {"cancelled": True, "download_dir": str(tmp_path)}


def test_run_download_moves_file_to_configured_dir_and_keeps_it_after_prune(tmp_path, monkeypatch):
    now = [1000]
    reclip_app.jobs = JobManager(ttl_seconds=1, time_func=lambda: now[0])
    monkeypatch.setattr(reclip_app, "DOWNLOAD_DIR", str(tmp_path / "dest"))
    monkeypatch.setattr(reclip_app, "TEMP_DOWNLOAD_DIR", str(tmp_path / "tmp"))

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def download(self, urls):
            file_path = self.opts["outtmpl"].replace("%(ext)s", "mp4")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(b"video")

    monkeypatch.setattr(reclip_app, "YoutubeDL", FakeYDL)

    job_id = reclip_app.jobs.create("https://example.com/video", "Demo: Video?")
    reclip_app.run_download(job_id, "https://example.com/video", "video", None)
    job = reclip_app.jobs.snapshot(job_id)
    now[0] = 1002
    reclip_app._clean_old_jobs()

    assert job["status"] == "done"
    assert job["filename"] == "Demo Video.mp4"
    assert os.path.isfile(job["file"])
    assert str(tmp_path / "dest") in job["file"]
    assert not list((tmp_path / "tmp").glob(f"{job_id}.*"))
    assert os.path.isfile(job["file"])


def test_run_download_uses_unique_filename_for_duplicates(tmp_path, monkeypatch):
    reclip_app.jobs = JobManager()
    monkeypatch.setattr(reclip_app, "DOWNLOAD_DIR", str(tmp_path / "dest"))
    monkeypatch.setattr(reclip_app, "TEMP_DOWNLOAD_DIR", str(tmp_path / "tmp"))
    os.makedirs(tmp_path / "dest", exist_ok=True)
    (tmp_path / "dest" / "Demo.mp4").write_bytes(b"existing")

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def download(self, urls):
            file_path = self.opts["outtmpl"].replace("%(ext)s", "mp4")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(b"new")

    monkeypatch.setattr(reclip_app, "YoutubeDL", FakeYDL)

    job_id = reclip_app.jobs.create("https://example.com/video", "Demo")
    reclip_app.run_download(job_id, "https://example.com/video", "video", None)
    job = reclip_app.jobs.snapshot(job_id)

    assert job["filename"] == "Demo (2).mp4"
    assert (tmp_path / "dest" / "Demo.mp4").read_bytes() == b"existing"
    assert (tmp_path / "dest" / "Demo (2).mp4").read_bytes() == b"new"


def test_cancel_marks_active_job_cancelled(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    job_id = reclip_app.jobs.create("https://example.com/video", "Demo")

    res = client.post(f"/api/cancel/{job_id}")

    assert res.status_code == 200
    assert res.get_json()["status"] == "cancelled"


class CapturingYDL:
    """Records ydl_opts for assertion; writes a fake file so run_download completes."""
    captured = {}
    written_ext = "mp4"

    def __init__(self, opts):
        CapturingYDL.captured["opts"] = opts

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def download(self, urls):
        outtmpl = CapturingYDL.captured["opts"]["outtmpl"]
        file_path = outtmpl.replace("%(ext)s", CapturingYDL.written_ext)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(b"data")


def _setup_capturing_download(tmp_path, monkeypatch, ext="mp4"):
    client = make_client(tmp_path, monkeypatch)
    CapturingYDL.captured = {}
    CapturingYDL.written_ext = ext
    monkeypatch.setattr(reclip_app, "YoutubeDL", CapturingYDL)
    monkeypatch.setattr(reclip_app.threading, "Thread", InlineThread)
    return client


def test_download_accepts_max_height_and_passes_capped_format_string(tmp_path, monkeypatch):
    client = _setup_capturing_download(tmp_path, monkeypatch)

    res = client.post(
        "/api/download",
        json={
            "url": "https://example.com/video",
            "format": "video",
            "max_height": 2160,
            "title": "Demo",
        },
    )

    assert res.status_code == 200
    assert CapturingYDL.captured["opts"]["format"] == "bv*[height<=2160]+ba/b[height<=2160]"


def test_download_without_max_height_uses_best_available(tmp_path, monkeypatch):
    client = _setup_capturing_download(tmp_path, monkeypatch)

    res = client.post(
        "/api/download",
        json={"url": "https://example.com/video", "format": "video", "title": "Demo"},
    )

    assert res.status_code == 200
    assert CapturingYDL.captured["opts"]["format"] == "bv*+ba/b"


def test_download_with_explicit_null_max_height_uses_best_available(tmp_path, monkeypatch):
    client = _setup_capturing_download(tmp_path, monkeypatch)

    res = client.post(
        "/api/download",
        json={
            "url": "https://example.com/video",
            "format": "video",
            "max_height": None,
            "title": "Demo",
        },
    )

    assert res.status_code == 200
    assert CapturingYDL.captured["opts"]["format"] == "bv*+ba/b"


def test_download_audio_ignores_max_height(tmp_path, monkeypatch):
    client = _setup_capturing_download(tmp_path, monkeypatch, ext="mp3")

    res = client.post(
        "/api/download",
        json={
            "url": "https://example.com/audio",
            "format": "audio",
            "max_height": 720,
            "title": "Audio",
        },
    )

    assert res.status_code == 200
    assert CapturingYDL.captured["opts"]["format"] == "bestaudio/best"


def test_download_rejects_invalid_max_height(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    for bad in [0, -100, "1080", 1.5, [], {}]:
        res = client.post(
            "/api/download",
            json={"url": "https://example.com/video", "format": "video", "max_height": bad},
        )
        assert res.status_code == 400, f"expected 400 for max_height={bad!r}"
        assert "max_height" in res.get_json()["error"].lower()


def test_presets_endpoint_lists_all_presets(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    res = client.get("/api/presets")

    assert res.status_code == 200
    presets = res.get_json()["presets"]
    ids = [p["id"] for p in presets]
    assert ids[0] == "none"
    assert "mp4-h264" in ids
    assert "mov-prores422hq" in ids


def test_download_default_preset_is_none(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    captured = {}

    def fake_run_download(job_id, url, format_choice, max_height, convert_preset="none", keep_original=False):
        captured["preset"] = convert_preset
        captured["keep_original"] = keep_original
        reclip_app.jobs.mark_done(job_id, "/tmp/x.mp4", "x.mp4")

    monkeypatch.setattr(reclip_app.threading, "Thread", InlineThread)
    monkeypatch.setattr(reclip_app, "run_download", fake_run_download)

    client.post(
        "/api/download",
        json={"url": "https://example.com/video", "format": "video", "title": "Demo"},
    )

    assert captured["preset"] == "none"
    assert captured["keep_original"] is False


def test_download_routes_convert_preset_and_keep_original(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    captured = {}

    def fake_run_download(job_id, url, format_choice, max_height, convert_preset="none", keep_original=False):
        captured["preset"] = convert_preset
        captured["keep_original"] = keep_original
        reclip_app.jobs.mark_done(job_id, "/tmp/x.mov", "x.mov")

    monkeypatch.setattr(reclip_app.threading, "Thread", InlineThread)
    monkeypatch.setattr(reclip_app, "run_download", fake_run_download)

    client.post(
        "/api/download",
        json={
            "url": "https://example.com/video",
            "format": "video",
            "title": "Demo",
            "convert_preset": "mov-prores422hq",
            "keep_original": True,
        },
    )

    assert captured["preset"] == "mov-prores422hq"
    assert captured["keep_original"] is True


def test_download_rejects_unknown_preset(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    res = client.post(
        "/api/download",
        json={
            "url": "https://example.com/video",
            "format": "video",
            "convert_preset": "vp9-mystery",
        },
    )

    assert res.status_code == 400
    assert "Unknown conversion preset" in res.get_json()["error"]


# --- run_download with conversion ----------------------------------------


class FakeFFmpegPopen:
    """Drop-in stand-in for subprocess.Popen invoked by _run_ffmpeg_convert.

    Behavior is class-level so a test can switch returncode / output writing
    by setting attributes before triggering the convert.
    """
    progress_lines = ["out_time_us=500000\n", "out_time_us=1000000\n"]
    return_code = 0
    write_output = True
    stderr_text = ""
    last_cmd = None

    def __init__(self, cmd, **kwargs):
        FakeFFmpegPopen.last_cmd = list(cmd)
        self.returncode = self.return_code
        self.stdout = iter(self.progress_lines)
        self.stderr = io.StringIO(self.stderr_text)
        if self.write_output:
            output_path = cmd[-1]
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(b"converted")

    def terminate(self):
        self.stdout = iter([])

    def kill(self):
        self.stdout = iter([])

    def wait(self, timeout=None):
        return self.returncode


def _patch_ffmpeg_binaries(monkeypatch):
    monkeypatch.setattr(reclip_app, "_ffmpeg_binary", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(reclip_app, "_ffprobe_binary", lambda: "/fake/ffprobe")
    monkeypatch.setattr(reclip_app, "_ffprobe_duration", lambda path: 10.0)


def _setup_convert_run(tmp_path, monkeypatch):
    reclip_app.jobs = JobManager()
    monkeypatch.setattr(reclip_app, "DOWNLOAD_DIR", str(tmp_path / "dest"))
    monkeypatch.setattr(reclip_app, "TEMP_DOWNLOAD_DIR", str(tmp_path / "tmp"))
    os.makedirs(tmp_path / "dest", exist_ok=True)
    os.makedirs(tmp_path / "tmp", exist_ok=True)
    _patch_ffmpeg_binaries(monkeypatch)

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def download(self, urls):
            file_path = self.opts["outtmpl"].replace("%(ext)s", "mp4")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(b"video-source")

    monkeypatch.setattr(reclip_app, "YoutubeDL", FakeYDL)

    # Reset Popen state to defaults each time.
    FakeFFmpegPopen.return_code = 0
    FakeFFmpegPopen.write_output = True
    FakeFFmpegPopen.stderr_text = ""
    FakeFFmpegPopen.last_cmd = None
    FakeFFmpegPopen.progress_lines = ["out_time_us=500000\n", "out_time_us=1000000\n"]
    monkeypatch.setattr(reclip_app.subprocess, "Popen", FakeFFmpegPopen)


def test_run_download_with_preset_writes_converted_file_and_drops_original(tmp_path, monkeypatch):
    _setup_convert_run(tmp_path, monkeypatch)

    job_id = reclip_app.jobs.create("https://example.com/video", "Demo")
    reclip_app.run_download(
        job_id, "https://example.com/video", "video", None,
        convert_preset="mov-prores422hq", keep_original=False,
    )
    job = reclip_app.jobs.snapshot(job_id)

    assert job["status"] == "done"
    assert job["filename"] == "Demo.mov"
    assert os.path.isfile(job["file"])
    # Original mp4 should not be in the destination folder when keep_original is off.
    assert not any(p.suffix == ".mp4" for p in (tmp_path / "dest").iterdir())
    # ffmpeg was invoked with the preset's prores args.
    assert "-profile:v" in FakeFFmpegPopen.last_cmd
    assert "prores_ks" in FakeFFmpegPopen.last_cmd


def test_run_download_with_keep_original_writes_both_files(tmp_path, monkeypatch):
    _setup_convert_run(tmp_path, monkeypatch)

    job_id = reclip_app.jobs.create("https://example.com/video", "Demo")
    reclip_app.run_download(
        job_id, "https://example.com/video", "video", None,
        convert_preset="mp4-h264", keep_original=True,
    )
    job = reclip_app.jobs.snapshot(job_id)

    assert job["status"] == "done"
    # Both the original (mp4) and converted (mp4 with the same ext but distinct via unique-naming)
    # should now live in dest. Since both share the .mp4 extension the duplicate-safe naming
    # appends "(2)" to the original.
    files = sorted(p.name for p in (tmp_path / "dest").iterdir())
    assert "Demo.mp4" in files
    assert "Demo (2).mp4" in files


def test_run_download_convert_failure_preserves_original_and_marks_error(tmp_path, monkeypatch):
    _setup_convert_run(tmp_path, monkeypatch)
    FakeFFmpegPopen.return_code = 1
    FakeFFmpegPopen.write_output = False
    FakeFFmpegPopen.stderr_text = "x265 codec missing"

    job_id = reclip_app.jobs.create("https://example.com/video", "Demo")
    reclip_app.run_download(
        job_id, "https://example.com/video", "video", None,
        convert_preset="mp4-hevc", keep_original=False,
    )
    job = reclip_app.jobs.snapshot(job_id)

    assert job["status"] == "error"
    assert "Conversion failed" in job["error"]
    # The user keeps the source video they paid for downloading.
    files = sorted(p.name for p in (tmp_path / "dest").iterdir())
    assert "Demo.mp4" in files


def test_run_download_cancel_during_convert_cleans_up(tmp_path, monkeypatch):
    _setup_convert_run(tmp_path, monkeypatch)

    captured_jobs_attr = reclip_app.jobs

    def cancel_during_convert(job_id, source_path, output_path, preset_args, popen=None):
        captured_jobs_attr.cancel(job_id)
        return False, "cancelled"

    monkeypatch.setattr(reclip_app, "_run_ffmpeg_convert", cancel_during_convert)

    job_id = reclip_app.jobs.create("https://example.com/video", "Demo")
    reclip_app.run_download(
        job_id, "https://example.com/video", "video", None,
        convert_preset="mp4-h264", keep_original=False,
    )
    job = reclip_app.jobs.snapshot(job_id)

    assert job["status"] == "cancelled"
    # Nothing left in dest, nothing left in temp.
    assert not list((tmp_path / "dest").iterdir())
    assert not list((tmp_path / "tmp").iterdir())


def test_run_download_with_none_preset_skips_ffmpeg(tmp_path, monkeypatch):
    _setup_convert_run(tmp_path, monkeypatch)

    def boom(*args, **kwargs):
        raise AssertionError("ffmpeg must not run for the 'none' preset")

    monkeypatch.setattr(reclip_app.subprocess, "Popen", boom)

    job_id = reclip_app.jobs.create("https://example.com/video", "Demo")
    reclip_app.run_download(
        job_id, "https://example.com/video", "video", None,
        convert_preset="none", keep_original=False,
    )
    job = reclip_app.jobs.snapshot(job_id)

    assert job["status"] == "done"
    assert job["filename"] == "Demo.mp4"


def test_run_ffmpeg_convert_streams_progress_updates(tmp_path, monkeypatch):
    reclip_app.jobs = JobManager()
    _patch_ffmpeg_binaries(monkeypatch)
    monkeypatch.setattr(reclip_app, "_ffprobe_duration", lambda path: 10.0)
    FakeFFmpegPopen.return_code = 0
    FakeFFmpegPopen.write_output = True
    FakeFFmpegPopen.progress_lines = [
        "out_time_us=2500000\n",  # 2.5s of 10s → 25%
        "out_time_us=5000000\n",  # 5.0s of 10s → 50%
        "out_time_us=9000000\n",  # 9.0s of 10s → 90%
    ]

    job_id = reclip_app.jobs.create("https://example.com/video", "Demo")
    reclip_app.jobs.mark_converting(job_id)

    out = str(tmp_path / "out.mov")
    ok, err = reclip_app._run_ffmpeg_convert(
        job_id, str(tmp_path / "src.mp4"), out, ["-c:v", "prores_ks"],
        popen=FakeFFmpegPopen,
    )

    assert ok is True
    assert err is None
    # Last progress before exit is at 90%, capped at 99 by the convert helper.
    assert reclip_app.jobs.snapshot(job_id)["progress"] == 90
