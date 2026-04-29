"""
Native macOS launcher for ReClip.

The Flask app remains the source of truth. This file only starts it on
localhost and presents it inside a WKWebView window.
"""

import logging
import os
import sys
import threading
import urllib.request

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

PORT = int(os.environ.get("PORT", "8899"))
SERVER_URL = f"http://127.0.0.1:{PORT}"

import objc
from AppKit import (
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
from WebKit import WKWebView, WKWebViewConfiguration


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
