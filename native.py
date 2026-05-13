"""
Native desktop launcher for ReClip.

The Flask app remains the source of truth. This wrapper starts it on a local
port and presents it inside a pywebview window.
"""

import logging
import os
import socket
import sys
import threading
import time
import urllib.request

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8899"))
SERVER_URL = f"http://{HOST}:{PORT}"
WINDOW_WIDTH = 720
WINDOW_HEIGHT = 640
WINDOW_MIN_SIZE = (620, 560)


def _port_available(port, host=HOST):
    """Return True when host:port is free for ReClip to bind."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
    except OSError:
        return False
    finally:
        sock.close()
    return True


def _free_port(host=HOST):
    """Ask the OS for an available local port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def _choose_port(host=HOST, preferred=PORT):
    """Use the preferred port when possible; otherwise fall back to a free one."""
    if _port_available(preferred, host):
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
        raise RuntimeError("pywebview is required; install requirements.txt first") from exc

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
