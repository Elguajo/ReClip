"""
Native macOS launcher for ReClip.

The Flask app remains the source of truth. This file only starts it on
localhost and presents it inside a WKWebView window.
"""

import logging
import os
import socket
import subprocess
import sys
import threading
import urllib.request

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

PORT = int(os.environ.get("PORT", "8899"))
SERVER_URL = f"http://127.0.0.1:{PORT}"


def _port_available(port):
    """True if 127.0.0.1:port is free for us to bind to.

    A stale ReClip dev server squatting on the port silently breaks the
    desktop build — WKWebView would then load whatever HTML that other
    server happens to serve. Probing up front lets us fail loud instead.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        return False
    finally:
        sock.close()
    return True


def _describe_port_holder(port):
    """Best-effort 'pid command' description of who owns the port. Empty on miss."""
    try:
        out = subprocess.check_output(
            ["lsof", "-nP", "-iTCP:%d" % port, "-sTCP:LISTEN", "-Fpc"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    pid, command = "", ""
    for line in out.splitlines():
        if line.startswith("p"):
            pid = line[1:]
        elif line.startswith("c"):
            command = line[1:]
    return f"{pid} {command}".strip()

import objc
from AppKit import (
    NSAlert,
    NSApp,
    NSApplication,
    NSApplicationActivationPolicyRegular,
    NSBackingStoreBuffered,
    NSMenu,
    NSMenuItem,
    NSScreen,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskResizable,
    NSWindowStyleMaskTitled,
    NSObject,
)
from Foundation import NSPoint, NSRect, NSSize, NSTimer, NSURL, NSURLRequest
from WebKit import WKWebView, WKWebViewConfiguration, WKWebsiteDataStore


SPLASH_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    :root { color-scheme: light dark; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
      background: Canvas;
      color: CanvasText;
    }
    main {
      display: grid;
      gap: 14px;
      justify-items: center;
    }
    h1 {
      margin: 0;
      font-size: 42px;
      font-weight: 650;
      letter-spacing: 0;
    }
    p {
      margin: 0;
      color: color-mix(in srgb, CanvasText 60%, transparent);
      font-size: 13px;
    }
    .spinner {
      width: 24px;
      height: 24px;
      border: 3px solid color-mix(in srgb, CanvasText 20%, transparent);
      border-top-color: #e85d2a;
      border-radius: 50%;
      animation: spin .8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>
  <main>
    <h1>ReClip</h1>
    <div class="spinner" aria-hidden="true"></div>
    <p>Starting local downloader...</p>
  </main>
</body>
</html>
"""


class AppDelegate(NSObject):
    window = objc.ivar()
    webview = objc.ivar()
    _server_ready = objc.ivar()

    def applicationDidFinishLaunching_(self, notification):
        self._server_ready = False
        self._create_window()
        self._build_menu()
        NSApp.activateIgnoringOtherApps_(True)

        if not _port_available(PORT):
            holder = _describe_port_holder(PORT)
            details = f" (held by PID {holder})" if holder else ""
            alert = NSAlert.alloc().init()
            alert.setMessageText_("ReClip can’t start")
            alert.setInformativeText_(
                f"Port {PORT} is already in use{details}.\n\n"
                f"Another ReClip instance or a leftover dev server is bound "
                f"to it. If we continued, the window would load whatever "
                f"that other server returns instead of this build.\n\n"
                f"Quit it and relaunch:\n"
                f"    lsof -nP -iTCP:{PORT} -sTCP:LISTEN\n"
                f"    kill <PID>"
            )
            alert.runModal()
            NSApp.terminate_(None)
            return

        threading.Thread(target=self._start_flask, daemon=True).start()
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.15, self, "checkServer:", None, True
        )

    def _create_window(self):
        screen = NSScreen.mainScreen().frame()
        width, height = 720, 860
        x = (screen.size.width - width) / 2
        y = (screen.size.height - height) / 2

        style = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskMiniaturizable
            | NSWindowStyleMaskResizable
        )
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSRect(NSPoint(x, y), NSSize(width, height)),
            style,
            NSBackingStoreBuffered,
            False,
        )
        self.window.setTitle_("ReClip")
        self.window.setMinSize_(NSSize(480, 600))
        self.window.setTitlebarAppearsTransparent_(True)
        self.window.setTitleVisibility_(1)

        config = WKWebViewConfiguration.alloc().init()
        # Ephemeral store: HTML/JS/cookies don't persist across launches, so a
        # rebuilt app never serves stale UI from WebKit's on-disk cache.
        config.setWebsiteDataStore_(WKWebsiteDataStore.nonPersistentDataStore())
        config.preferences().setValue_forKey_(True, "developerExtrasEnabled")

        self.webview = WKWebView.alloc().initWithFrame_configuration_(
            self.window.contentView().bounds(),
            config,
        )
        self.webview.setAutoresizingMask_(0x12)
        self.webview.setValue_forKey_(False, "drawsBackground")
        self.webview.loadHTMLString_baseURL_(SPLASH_HTML, None)

        self.window.contentView().addSubview_(self.webview)
        self.window.makeKeyAndOrderFront_(None)

    def _start_flask(self):
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        from app import app

        app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)

    def checkServer_(self, timer):
        if self._server_ready:
            timer.invalidate()
            return

        try:
            urllib.request.urlopen(SERVER_URL, timeout=0.3)
        except Exception:
            return

        self._server_ready = True
        timer.invalidate()
        url = NSURL.URLWithString_(SERVER_URL)
        self.webview.loadRequest_(NSURLRequest.requestWithURL_(url))

    def _build_menu(self):
        menubar = NSMenu.alloc().init()

        app_menu_item = NSMenuItem.alloc().init()
        menubar.addItem_(app_menu_item)
        app_menu = NSMenu.alloc().init()
        app_menu.addItemWithTitle_action_keyEquivalent_("About ReClip", None, "")
        app_menu.addItem_(NSMenuItem.separatorItem())
        app_menu.addItemWithTitle_action_keyEquivalent_("Hide ReClip", "hide:", "h")
        app_menu.addItemWithTitle_action_keyEquivalent_("Hide Others", "hideOtherApplications:", "")
        app_menu.addItem_(NSMenuItem.separatorItem())
        app_menu.addItemWithTitle_action_keyEquivalent_("Quit ReClip", "terminate:", "q")
        app_menu_item.setSubmenu_(app_menu)

        edit_menu_item = NSMenuItem.alloc().init()
        menubar.addItem_(edit_menu_item)
        edit_menu = NSMenu.alloc().initWithTitle_("Edit")
        edit_menu.addItemWithTitle_action_keyEquivalent_("Undo", "undo:", "z")
        edit_menu.addItemWithTitle_action_keyEquivalent_("Redo", "redo:", "Z")
        edit_menu.addItem_(NSMenuItem.separatorItem())
        edit_menu.addItemWithTitle_action_keyEquivalent_("Cut", "cut:", "x")
        edit_menu.addItemWithTitle_action_keyEquivalent_("Copy", "copy:", "c")
        edit_menu.addItemWithTitle_action_keyEquivalent_("Paste", "paste:", "v")
        edit_menu.addItemWithTitle_action_keyEquivalent_("Select All", "selectAll:", "a")
        edit_menu_item.setSubmenu_(edit_menu)

        window_menu_item = NSMenuItem.alloc().init()
        menubar.addItem_(window_menu_item)
        window_menu = NSMenu.alloc().initWithTitle_("Window")
        window_menu.addItemWithTitle_action_keyEquivalent_("Minimize", "performMiniaturize:", "m")
        window_menu.addItemWithTitle_action_keyEquivalent_("Zoom", "performZoom:", "")
        window_menu.addItemWithTitle_action_keyEquivalent_("Close", "performClose:", "w")
        window_menu_item.setSubmenu_(window_menu)

        NSApp.setMainMenu_(menubar)
        NSApp.setWindowsMenu_(window_menu)

    def applicationShouldTerminateAfterLastWindowClosed_(self, app):
        return True


def main():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()


if __name__ == "__main__":
    main()
