"""Small SQLite key/value cache with expiry."""
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from tr_common.config import env_str


def path():
    return Path(env_str("GEOCODE_DB") or "/tmp/terrarisk-geocode.sqlite3")


def _conn():
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, timeout=10)
    conn.execute("CREATE TABLE IF NOT EXISTS cache(k TEXT PRIMARY KEY, v TEXT NOT NULL, t REAL NOT NULL)")
    return conn


def get(key, ttl_seconds):
    with closing(_conn()) as conn:
        row = conn.execute("SELECT v, t FROM cache WHERE k=?", (key,)).fetchone()
    if row and time.time() - row[1] < ttl_seconds:
        return json.loads(row[0])
    return None


def put(key, value):
    with closing(_conn()) as conn:
        conn.execute("INSERT OR REPLACE INTO cache(k, v, t) VALUES(?,?,?)", (key, json.dumps(value), time.time()))
        conn.commit()


def size():
    with closing(_conn()) as conn:
        return conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
