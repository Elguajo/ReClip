import sys
import types

import pytest

import native_pywebview


def test_choose_port_uses_preferred_when_available(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr(native_pywebview, "_port_available", lambda host, port: True)

    assert native_pywebview._choose_port("127.0.0.1", 8899) == 8899


def test_choose_port_falls_back_when_default_is_busy(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr(native_pywebview, "_port_available", lambda host, port: False)
    monkeypatch.setattr(native_pywebview, "_free_port", lambda host: 49152)

    assert native_pywebview._choose_port("127.0.0.1", 8899) == 49152


def test_choose_port_respects_explicit_port(monkeypatch):
    monkeypatch.setenv("PORT", "8899")
    monkeypatch.setattr(native_pywebview, "_port_available", lambda host, port: False)

    with pytest.raises(RuntimeError, match="Port 8899 is already in use"):
        native_pywebview._choose_port("127.0.0.1", 8899)


def test_main_starts_server_and_window(monkeypatch):
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
    monkeypatch.setattr(native_pywebview, "_choose_port", lambda: 49152)
    monkeypatch.setattr(native_pywebview, "_start_flask", lambda host, port: calls.append(("flask", host, port)))
    monkeypatch.setattr(native_pywebview, "_wait_for_server", lambda url: True)
    monkeypatch.setattr(native_pywebview.threading, "Thread", InlineThread)

    native_pywebview.main()

    assert ("thread", ("127.0.0.1", 49152), True) in calls
    assert ("flask", "127.0.0.1", 49152) in calls
    assert (
        "create_window",
        ("ReClip", "http://127.0.0.1:49152"),
        {"width": 720, "height": 860, "min_size": (480, 600)},
    ) in calls
    assert ("start",) in calls


def test_main_reports_missing_pywebview(monkeypatch):
    monkeypatch.delitem(sys.modules, "webview", raising=False)
    monkeypatch.setattr(native_pywebview, "_choose_port", lambda: 49152)

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "webview":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(RuntimeError, match="pywebview is required"):
        native_pywebview.main()
