import pytest

from job_manager import DownloadCancelled, JobManager


def test_job_lifecycle_tracks_progress_and_done():
    now = [1000]
    jobs = JobManager(time_func=lambda: now[0])

    job_id = jobs.create("https://example.com/video", "Demo")
    jobs.update_progress(job_id, {
        "progress": 42,
        "downloaded_bytes": 420,
        "total_bytes": 1000,
        "speed": 10,
        "eta": 58,
    })

    job = jobs.snapshot(job_id)
    assert job["status"] == "downloading"
    assert job["progress"] == 42
    assert job["eta"] == 58

    assert jobs.mark_done(job_id, "/tmp/demo.mp4", "demo.mp4") is True
    job = jobs.snapshot(job_id)
    assert job["status"] == "done"
    assert job["progress"] == 100
    assert job["filename"] == "demo.mp4"


def test_cancel_prevents_late_progress_and_done():
    jobs = JobManager()
    job_id = jobs.create("https://example.com/video", "Demo")

    cancelled = jobs.cancel(job_id)

    assert cancelled["status"] == "cancelled"
    assert jobs.mark_done(job_id, "/tmp/demo.mp4", "demo.mp4") is False
    with pytest.raises(DownloadCancelled):
        jobs.update_progress(job_id, {"progress": 50})


def test_mark_converting_transitions_from_downloading_and_resets_progress():
    jobs = JobManager()
    job_id = jobs.create("https://example.com/video", "Demo")
    jobs.update_progress(job_id, {"progress": 80, "speed": 100, "eta": 5})

    assert jobs.mark_converting(job_id) is True
    job = jobs.snapshot(job_id)
    assert job["status"] == "converting"
    # Progress is reset so the convert phase reuses the bar from 0.
    assert job["progress"] == 0
    assert job["speed"] is None
    assert job["eta"] is None


def test_mark_converting_refuses_when_cancelled():
    jobs = JobManager()
    job_id = jobs.create("https://example.com/video", "Demo")
    jobs.cancel(job_id)

    assert jobs.mark_converting(job_id) is False


def test_update_progress_works_during_convert():
    jobs = JobManager()
    job_id = jobs.create("https://example.com/video", "Demo")
    jobs.mark_converting(job_id)

    jobs.update_progress(job_id, {"progress": 33})
    assert jobs.snapshot(job_id)["progress"] == 33


def test_cancel_during_convert_marks_cancelled():
    jobs = JobManager()
    job_id = jobs.create("https://example.com/video", "Demo")
    jobs.mark_converting(job_id)

    cancelled = jobs.cancel(job_id)
    assert cancelled["status"] == "cancelled"
    # Subsequent progress updates raise so a long-running ffmpeg loop bails out.
    with pytest.raises(DownloadCancelled):
        jobs.update_progress(job_id, {"progress": 50})


def test_mark_done_succeeds_from_converting():
    jobs = JobManager()
    job_id = jobs.create("https://example.com/video", "Demo")
    jobs.mark_converting(job_id)

    assert jobs.mark_done(job_id, "/tmp/demo.mov", "demo.mov") is True
    job = jobs.snapshot(job_id)
    assert job["status"] == "done"
    assert job["filename"] == "demo.mov"


def test_prune_terminal_keeps_active_jobs():
    now = [1000]
    jobs = JobManager(ttl_seconds=60, time_func=lambda: now[0])
    done_id = jobs.create("https://example.com/done", "Done")
    active_id = jobs.create("https://example.com/active", "Active")

    assert jobs.mark_done(done_id, "/tmp/done.mp4", "done.mp4") is True
    now[0] = 1061

    removed = jobs.prune_terminal()

    assert [job["id"] for job in removed] == [done_id]
    assert jobs.snapshot(done_id) is None
    assert jobs.snapshot(active_id)["status"] == "downloading"
