"""Native launcher port-selection contract."""

import socket
import sys
import types

import pytest


from native import (  # noqa: E402  (import-after-skip is intentional)
    WINDOW_HEIGHT,
    WINDOW_MIN_SIZE,
    WINDOW_WIDTH,
    _choose_port,
    _port_available,
)


def test_window_geometry_matches_launch_contract():
    assert WINDOW_WIDTH == 925
    assert WINDOW_HEIGHT == 820
    assert WINDOW_MIN_SIZE == (760, 600)


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


def test_choose_port_falls_back_when_default_is_busy(monkeypatch):
    import native

    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr(native, "_port_available", lambda port, host="127.0.0.1": False)
    monkeypatch.setattr(native, "_free_port", lambda host="127.0.0.1": 49152)

    assert _choose_port("127.0.0.1", 8899) == 49152


def test_choose_port_respects_explicit_port(monkeypatch):
    import native

    monkeypatch.setenv("PORT", "8899")
    monkeypatch.setattr(native, "_port_available", lambda port, host="127.0.0.1": False)

    with pytest.raises(RuntimeError, match="Port 8899 is already in use"):
        _choose_port("127.0.0.1", 8899)


def test_main_starts_server_and_window(monkeypatch):
    import native

    calls = []

    class InlineThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            calls.append(("thread", self.args, self.daemon))
            self.target(*self.args)

    fake_webview = types.SimpleNamespace()

    def create_window(*args, **kwargs):
        calls.append(("create_window", args, kwargs))

    def start():
        calls.append(("start",))

    fake_webview.create_window = create_window
    fake_webview.start = start

    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    monkeypatch.setattr(native, "_choose_port", lambda: 49152)
    monkeypatch.setattr(
        native,
        "_start_flask",
        lambda host, port: calls.append(("flask", host, port)),
    )
    monkeypatch.setattr(native, "_wait_for_server", lambda url: True)
    monkeypatch.setattr(native.threading, "Thread", InlineThread)

    native.main()

    assert ("thread", ("127.0.0.1", 49152), True) in calls
    assert ("flask", "127.0.0.1", 49152) in calls
    assert (
        "create_window",
        ("ReClip", "http://127.0.0.1:49152"),
        {"width": 925, "height": 820, "min_size": (760, 600)},
    ) in calls
    assert ("start",) in calls


def test_main_reports_missing_pywebview(monkeypatch):
    import native

    monkeypatch.delitem(sys.modules, "webview", raising=False)
    monkeypatch.setattr(native, "_choose_port", lambda: 49152)

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "webview":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(RuntimeError, match="pywebview is required"):
        native.main()
