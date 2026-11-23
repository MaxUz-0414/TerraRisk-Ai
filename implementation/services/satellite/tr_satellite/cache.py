"""Tiny file cache for generated pictures: the same parcel + layer is made only once."""
import hashlib
import json
import os
import time
from pathlib import Path

from tr_common.config import env_int, env_str

VERSION = "v3"  # bump when the picture design changes so old cached pictures are not reused


def cache_dir():
    path = Path(env_str("CACHE_DIR") or Path(os.environ.get("TMPDIR", "/tmp")) / "terrarisk-satellite-cache")
    path.mkdir(parents=True, exist_ok=True)
    return path


def key(geometry, layer, mode):
    raw = json.dumps([VERSION, mode, layer, geometry], sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()


def get(geometry, layer, mode):
    path = cache_dir() / f"{key(geometry, layer, mode)}.jpg"
    if path.exists() and time.time() - path.stat().st_mtime < env_int("CACHE_DAYS", 30) * 86400:
        return path.read_bytes()
    return None


def put(geometry, layer, mode, data):
    directory = cache_dir()
    (directory / f"{key(geometry, layer, mode)}.jpg").write_bytes(data)
    files = sorted(directory.glob("*.jpg"), key=lambda p: p.stat().st_mtime)
    for old in files[: max(0, len(files) - env_int("CACHE_MAX_FILES", 3000))]:
        old.unlink(missing_ok=True)


def stats():
    files = list(cache_dir().glob("*.jpg"))
    return {"files": len(files), "mb": round(sum(f.stat().st_size for f in files) / 1024 ** 2, 2)}
