import os
import sys
import tempfile
from pathlib import Path


def is_frozen() -> bool:
    """Return True when running inside a PyInstaller/frozen executable."""
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def get_bundle_dir() -> Path:
    """Return the root directory containing bundled assets (dev repo or _MEIPASS)."""
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def get_backend_dir() -> Path:
    """Return the backend directory containing de421.bsp and Python modules."""
    return get_bundle_dir() / "backend"


def get_frontend_dir() -> Path:
    """Return the frontend directory containing index.html and static assets."""
    return get_bundle_dir() / "frontend"


def get_data_dir() -> Path:
    """Return the bundled backend data directory (offline city registry, etc.)."""
    return get_backend_dir() / "data"


def get_assets_dir() -> Path:
    """Return the desktop assets directory (application icons, etc.)."""
    return get_bundle_dir() / "assets"


def get_app_data_dir() -> Path:
    """Return a writable directory for runtime caches (Skyfield, Geobuf grids)."""
    if os.environ.get("VERCEL"):
        base_dir = Path("/tmp") / "hiltron"
    elif os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
        base_dir = Path(local_app_data) / "HILTRON"
    else:
        xdg_data = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        base_dir = Path(xdg_data) / "HILTRON"

    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "hiltron"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

