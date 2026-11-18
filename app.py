# -*- coding: utf-8 -*-
import os
import sys
import time
import socket
import threading

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="ignore")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="ignore")

if getattr(sys, "frozen", False):
    _BASE = os.path.dirname(sys.executable)
    _BUNDLE = sys._MEIPASS
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))
    _BUNDLE = _BASE

os.environ["APP_BASE"] = _BASE
os.environ["APP_BUNDLE"] = _BUNDLE

from server import app


def _find_free_port(preferred: int = 5055) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


if __name__ == "__main__":
    port = _find_free_port(5055)
    url = f"http://127.0.0.1:{port}"

    def start_server():
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)

    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    try:
        import webview
        webview.create_window(
            "Reflowia PDF to EPUB",
            url,
            width=1140,
            height=740,
            min_size=(800, 500),
        )
        webview.start()
    except ImportError:
        import webbrowser
        time.sleep(1.0)
        webbrowser.open(url)
        try:
            t.join()
        except KeyboardInterrupt:
            pass
