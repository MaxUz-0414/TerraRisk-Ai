"""Finds the other services. One function: client("satellite") -> Client.

SERVICES_MODE=http       (docker compose / production): each service is a separate container
                         URL: <NAME>_URL (e.g. SATELLITE_URL=http://satellite:8000), default http://<name>:8000
SERVICES_MODE=inprocess  (unit tests, and `python manage.py runserver` on a laptop without Docker):
                         the service apps run inside the calling process; same code, same API, no network.
"""
import importlib
import sys
import threading
from pathlib import Path

from .client import Client
from .config import env_str

SERVICES = ("analysis", "satellite", "risk", "advisory", "report", "billing", "geocode", "chatbot")
TIMEOUTS = {"analysis": 170, "satellite": 130, "risk": 15, "advisory": 30, "report": 120, "billing": 10, "geocode": 10, "chatbot": 25}

_clients = {}
_apps = {}
_lock = threading.Lock()


def mode():
    return env_str("SERVICES_MODE", "http").lower()


def _app(name):
    with _lock:
        if name not in _apps:
            root = Path(__file__).resolve().parents[2]  # .../services
            for candidate in (root / name,):
                if candidate.is_dir() and str(candidate) not in sys.path:
                    sys.path.insert(0, str(candidate))
            _apps[name] = importlib.import_module(f"tr_{name}.app").create_app()
        return _apps[name]


def client(name):
    if name not in SERVICES:
        raise KeyError(f"Unknown service {name!r}")
    with _lock:
        cached = _clients.get(name)
    if cached is not None:
        return cached
    token = env_str("INTERNAL_TOKEN")
    if mode() == "inprocess":
        created = Client(name, token=token, timeout=TIMEOUTS[name], app=_app(name))
    else:
        created = Client(name, base_url=env_str(f"{name.upper()}_URL") or f"http://{name}:8000", token=token, timeout=TIMEOUTS[name])
    with _lock:
        _clients[name] = created
    return created


def reset():
    """Forget cached clients and apps (tests change environment variables between runs)."""
    with _lock:
        _clients.clear()
        _apps.clear()


def ensure_path(name):
    """Make `import tr_<name>` work (adds services/<name> to sys.path). Used by tests that import service modules directly."""
    root = Path(__file__).resolve().parents[2]
    path = str(root / name)
    if path not in sys.path:
        sys.path.insert(0, path)


def health(name):
    """{"status", "ms", ...} for the admin dashboard. Never raises."""
    import time

    started = time.perf_counter()
    try:
        c = client(name)
        body = c.get("/healthz", timeout=3).json()
        info = {}
        try:
            info = c.get("/v1/info", timeout=3).json()
        except Exception:
            pass
        return {"name": name, "up": True, "status": body.get("status", "ok"), "ms": round((time.perf_counter() - started) * 1000),
                "checks": body.get("checks", {}), "uptime_s": body.get("uptime_s"), "requests": info.get("requests"),
                "errors": info.get("errors"), "avg_ms": info.get("avg_ms"), "version": body.get("version"), "last_error": info.get("last_error", "")}
    except Exception as exc:
        return {"name": name, "up": False, "status": "down", "ms": round((time.perf_counter() - started) * 1000), "checks": {},
                "error": f"{type(exc).__name__}: {exc}"[:160]}
