"""Conversion presets for the post-download ffmpeg step.

Each preset has:
    id     — identifier sent from the client and stored in jobs
    label  — user-facing string for the dropdown
    ext    — output extension (None marks "no conversion")
    args   — list of ffmpeg arguments inserted between `-i input` and `output_path`
"""

CONVERSION_PRESETS = [
    {
        "id": "none",
        "label": "No conversion (keep original)",
        "ext": None,
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

_BY_ID = {p["id"]: p for p in CONVERSION_PRESETS}


def get_preset(preset_id):
    """Return the preset dict for the given id.

    Raises ValueError if the id is unknown so the caller surfaces a clear
    400 to the client rather than silently picking a default.
    """
    try:
        return _BY_ID[preset_id]
    except KeyError:
        raise ValueError(f"Unknown conversion preset: {preset_id!r}")


def is_no_op(preset):
    """True for the 'none' preset (no ffmpeg step)."""
    return preset["ext"] is None
