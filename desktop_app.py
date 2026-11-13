"""
HILTRON Desktop Application Launcher (PyWebView + Embedded FastAPI/Uvicorn).
"""

import argparse
import os
import shutil
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

# Ensure backend package is importable in both dev and frozen PyInstaller builds
ROOT_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
BACKEND_DIR = ROOT_DIR / "backend"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import uvicorn
import webview

from backend.main import app
from backend.paths import get_app_data_dir


def find_available_port(preferred_port: int = 8000) -> int:
    """Return preferred_port if free, otherwise bind an ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("0.0.0.0", preferred_port))
            return preferred_port
        except OSError:
            pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("0.0.0.0", 0))
        return sock.getsockname()[1]


def get_local_ip() -> str:
    """Best-effort detection of the machine's LAN IP for ESP32 WebSocket setup."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def wait_for_server(port: int, timeout_sec: float = 15.0) -> bool:
    """Poll /api/health until the embedded FastAPI server responds with HTTP 200."""
    deadline = time.monotonic() + timeout_sec
    url = f"http://127.0.0.1:{port}/api/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.15)
    return False


def configure_windowed_stdio() -> None:
    """Redirect None stdout/stderr in PyInstaller windowed (--noconsole) builds."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    log_path = get_app_data_dir() / "hiltron.log"
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = log_file
    if sys.stderr is None:
        sys.stderr = log_file


def main() -> int:
    configure_windowed_stdio()
    parser = argparse.ArgumentParser(description="HILTRON Desktop Observatory")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    parser.add_argument("--debug", action="store_true", help="Enable WebView DevTools")
    args = parser.parse_args()

    port = find_available_port(args.port)
    app.state.hiltron_port = port
    app.state.desktop_mode = True
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info" if args.debug else "warning",
        access_log=args.debug,
        log_config=None if getattr(sys, "frozen", False) else uvicorn.config.LOGGING_CONFIG,
    )
    server = uvicorn.Server(config)

    server_thread = threading.Thread(target=server.run, name="hiltron-uvicorn", daemon=True)
    server_thread.start()

    if not wait_for_server(port):
        print(f"[HILTRON] Embedded backend failed to start on port {port}.", file=sys.stderr)
        server.should_exit = True
        return 1

    local_ip = get_local_ip()
    print(f"[HILTRON] Desktop server active: http://127.0.0.1:{port}/ (LAN ESP32 WS: ws://{local_ip}:{port}/ws/esp32)")

    window = webview.create_window(
        title="HILTRON — Islamic Astronomical Observatory",
        url=f"http://127.0.0.1:{port}/app.html",
        width=1366,
        height=840,
        min_size=(1024, 680),
        background_color="#0B0F19",
    )

    def on_closing():
        server.should_exit = True

    window.events.closing += on_closing

    storage_dir = str(get_app_data_dir() / "webview_storage")
    os.makedirs(storage_dir, exist_ok=True)

    # Clear WebView2 HTTP/JS cache so rebuilt or updated frontend bundles load cleanly
    for cache_rel in ("EBWebView/Default/Cache", "EBWebView/Default/Code Cache"):
        cache_path = Path(storage_dir) / cache_rel
        if cache_path.exists():
            shutil.rmtree(cache_path, ignore_errors=True)

    webview.start(
        debug=args.debug,
        private_mode=False,
        storage_path=storage_dir,
    )

    server.should_exit = True
    server_thread.join(timeout=3.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

