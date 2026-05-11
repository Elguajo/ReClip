"""Native launcher port-conflict probe.

The desktop build silently breaks when another process (a leftover dev
server, a second ReClip) already holds the wrapper's port — WKWebView
would just render whatever HTML that other server happens to serve.
``_port_available`` is what gates the launcher; pin its contract here.
"""
import socket

import pytest


pytest.importorskip("AppKit", reason="native.py needs PyObjC")
from native import (  # noqa: E402  (import-after-skip is intentional)
    WINDOW_HEIGHT,
    WINDOW_MIN_SIZE,
    WINDOW_WIDTH,
    _port_available,
)


def test_window_geometry_matches_launch_contract():
    assert WINDOW_WIDTH == 720
    assert WINDOW_HEIGHT == 640
    assert WINDOW_MIN_SIZE == (620, 560)


def test_port_available_when_nothing_listens():
    # Find a free port by binding to 0, releasing, then probing — the OS
    # almost never reassigns it before our probe.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    assert _port_available(port) is True


def test_port_unavailable_when_someone_listens():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        assert _port_available(port) is False
    finally:
        sock.close()
