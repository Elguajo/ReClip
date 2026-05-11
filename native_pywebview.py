"""
Experimental pywebview launcher for ReClip.

This keeps Flask as the source of truth and opens the existing local server
inside a native webview window. It is intentionally not wired into packaging
yet; native.py remains the production macOS launcher until the A3 migration is
approved and verified.
"""

import logging
import os
import socket
import sys
import time
import threading
import urllib.request

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

HOST = os.environ.get("HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("PORT", "8899"))
WINDOW_WIDTH = 720
WINDOW_HEIGHT = 640
WINDOW_MIN_SIZE = (620, 560)


def _port_available(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
    except OSError:
        return False
    finally:
        sock.close()
    return True


def _free_port(host):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def _choose_port(host=HOST, preferred=DEFAULT_PORT):
    if _port_available(host, preferred):
        return preferred

    if os.environ.get("PORT"):
        raise RuntimeError(f"Port {preferred} is already in use")

    return _free_port(host)


def _server_url(host, port):
    return f"http://{host}:{port}"


def _start_flask(host, port):
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    from app import app

    app.run(host=host, port=port, debug=False, use_reloader=False)


def _wait_for_server(url, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=0.3)
            return True
        except Exception:
            time.sleep(0.1)
    return False


def main():
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError(
            "pywebview is required for native_pywebview.py; "
            "install requirements.txt first"
        ) from exc

    port = _choose_port()
    url = _server_url(HOST, port)

    threading.Thread(target=_start_flask, args=(HOST, port), daemon=True).start()
    if not _wait_for_server(url):
        raise RuntimeError("ReClip server did not start in time")

    webview.create_window(
        "ReClip",
        url,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=WINDOW_MIN_SIZE,
    )
    webview.start()


if __name__ == "__main__":
    main()
