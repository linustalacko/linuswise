"""Native desktop window around the local web app (optional `desktop` extra).

`linuswise app` opens a real macOS window via pywebview. If pywebview isn't
installed it falls back to opening the UI in your browser, so the command always
works.
"""

from __future__ import annotations

import threading

from .config import Config
from .web import create_app, serve


def run(cfg: Config) -> None:
    try:
        import webview  # type: ignore
    except ImportError:
        print("pywebview not installed — opening in your browser instead.")
        print("For a native window: uv sync --extra desktop")
        serve(cfg, open_browser=True)
        return

    app = create_app(cfg)
    port = cfg.web_port

    def _serve():
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

    threading.Thread(target=_serve, daemon=True).start()
    webview.create_window("Linuswise", f"http://127.0.0.1:{port}/", width=840, height=900)
    webview.start()
