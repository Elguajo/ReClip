import pytest

from presets import CONVERSION_PRESETS, get_preset, is_no_op


def test_get_preset_returns_h264():
    p = get_preset("mp4-h264")
    assert p["ext"] == "mp4"
    assert "libx264" in p["args"]


def test_get_preset_returns_prores422hq():
    p = get_preset("mov-prores422hq")
    assert p["ext"] == "mov"
    # ProRes 422 HQ is profile 3 — locking the spec so the JSON output
    # remains true to the preset's name.
    args = p["args"]
    assert args[args.index("-profile:v") + 1] == "3"


def test_get_preset_unknown_raises_value_error():
    with pytest.raises(ValueError, match="Unknown conversion preset"):
        get_preset("vp9")


def test_none_preset_is_detectable():
    assert is_no_op(get_preset("none")) is True
    assert is_no_op(get_preset("mp4-h264")) is False


def test_all_preset_ids_unique_and_labeled():
    ids = [p["id"] for p in CONVERSION_PRESETS]
    labels = [p["label"] for p in CONVERSION_PRESETS]
    assert len(ids) == len(set(ids))
    assert all(label for label in labels)
    # First preset must be `none` so the UI defaults to "no conversion".
    assert CONVERSION_PRESETS[0]["id"] == "none"
