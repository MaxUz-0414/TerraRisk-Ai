"""SQLite storage for accounts, purchases and the search ledger. Every change is one atomic transaction.

The ledger makes consume/refund safe to retry: the same idempotency key never changes the balance twice.
"""
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from tr_common.config import env_int, env_str

from .plans import UNLIMITED_DAYS, get_plan

_init_lock = threading.Lock()
_initialised = set()


class NoSearchesLeft(Exception):
    pass


def db_path():
    return Path(env_str("BILLING_DB") or "/tmp/terrarisk-billing.sqlite3")


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat() if dt else None


def _parse(text):
    return datetime.fromisoformat(text) if text else None


SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts(
  user_id INTEGER PRIMARY KEY, email TEXT NOT NULL DEFAULT '',
  free_searches INTEGER NOT NULL DEFAULT 0, unlimited_until TEXT, plan_key TEXT NOT NULL DEFAULT 'free',
  created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS purchases(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, plan_key TEXT NOT NULL, plan_name TEXT NOT NULL,
  searches INTEGER NOT NULL, price TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS purchases_user ON purchases(user_id, id DESC);
CREATE TABLE IF NOT EXISTS ledger(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, delta INTEGER NOT NULL, reason TEXT NOT NULL,
  idem_key TEXT UNIQUE, created_at TEXT NOT NULL);
"""


@contextmanager
def connect():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15, isolation_level=None)  # we manage transactions explicitly
    conn.row_factory = sqlite3.Row
    with _init_lock:
        if str(path) not in _initialised:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
            _initialised.add(str(path))
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction():
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise


def _account_dict(conn, row):
    until = _parse(row["unlimited_until"])
    purchases = conn.execute("SELECT plan_key, plan_name, searches, price, created_at FROM purchases WHERE user_id=? ORDER BY id DESC LIMIT 10",
                             (row["user_id"],)).fetchall()
    return {
        "user_id": row["user_id"], "email": row["email"], "free_searches": row["free_searches"],
        "unlimited": bool(until and until > _now()), "unlimited_until": row["unlimited_until"], "plan_key": row["plan_key"],
        "purchases": [dict(p) for p in purchases],
    }


def _row(conn, user_id):
    return conn.execute("SELECT * FROM accounts WHERE user_id=?", (user_id,)).fetchone()


def ensure_account(user_id, email="", initial=None):
    """Create the account on first sight (optionally with the balance it already had), else return it."""
    initial = initial or {}
    with transaction() as conn:
        if _row(conn, user_id) is None:
            free = initial.get("free_searches")
            conn.execute("INSERT INTO accounts(user_id, email, free_searches, unlimited_until, plan_key, created_at) VALUES(?,?,?,?,?,?)",
                         (user_id, email, free if isinstance(free, int) and free >= 0 else env_int("FREE_SEARCHES", 5),
                          initial.get("unlimited_until"), initial.get("plan_key") or "free", _iso(_now())))
        elif email:
            conn.execute("UPDATE accounts SET email=? WHERE user_id=? AND email<>?", (email, user_id, email))
        return _account_dict(conn, _row(conn, user_id))


def get_account(user_id):
    with connect() as conn:
        row = _row(conn, user_id)
        return _account_dict(conn, row) if row else None


def consume(user_id, key=None):
    """Use one search. Unlimited plans are not charged. Raises NoSearchesLeft. Safe to retry with the same key."""
    with transaction() as conn:
        row = _row(conn, user_id)
        if row is None:
            raise KeyError(user_id)
        if key and conn.execute("SELECT 1 FROM ledger WHERE idem_key=?", (key,)).fetchone():
            return _account_dict(conn, row)  # already applied
        until = _parse(row["unlimited_until"])
        if until and until > _now():
            delta = 0
        elif row["free_searches"] > 0:
            delta = -1
        else:
            raise NoSearchesLeft()
        conn.execute("UPDATE accounts SET free_searches = free_searches + ? WHERE user_id=?", (delta, user_id))
        conn.execute("INSERT INTO ledger(user_id, delta, reason, idem_key, created_at) VALUES(?,?,?,?,?)",
                     (user_id, delta, "analysis", key, _iso(_now())))
        return _account_dict(conn, _row(conn, user_id))


def refund(user_id, key):
    """Give the search back when an analysis failed. Only works once, and only for a search that was really charged."""
    with transaction() as conn:
        row = _row(conn, user_id)
        if row is None:
            raise KeyError(user_id)
        charged = conn.execute("SELECT delta FROM ledger WHERE idem_key=? AND user_id=?", (key, user_id)).fetchone()
        done = conn.execute("SELECT 1 FROM ledger WHERE idem_key=?", (f"refund:{key}",)).fetchone()
        if charged and charged["delta"] < 0 and not done:
            conn.execute("UPDATE accounts SET free_searches = free_searches + 1 WHERE user_id=?", (user_id,))
            conn.execute("INSERT INTO ledger(user_id, delta, reason, idem_key, created_at) VALUES(?,?,?,?,?)",
                         (user_id, 1, "refund", f"refund:{key}", _iso(_now())))
        return _account_dict(conn, _row(conn, user_id))


def checkout(user_id, plan_key):
    plan = get_plan(plan_key)
    if plan is None:
        raise ValueError("Unknown plan")
    with transaction() as conn:
        row = _row(conn, user_id)
        if row is None:
            raise KeyError(user_id)
        now = _now()
        if plan.is_unlimited:
            start = max(_parse(row["unlimited_until"]) or now, now)  # buying again extends the period
            conn.execute("UPDATE accounts SET unlimited_until=?, plan_key=? WHERE user_id=?",
                         (_iso(start + timedelta(days=UNLIMITED_DAYS)), plan.key, user_id))
        else:
            conn.execute("UPDATE accounts SET free_searches = free_searches + ?, plan_key=? WHERE user_id=?", (plan.searches, plan.key, user_id))
        conn.execute("INSERT INTO purchases(user_id, plan_key, plan_name, searches, price, created_at) VALUES(?,?,?,?,?,?)",
                     (user_id, plan.key, plan.name, plan.searches or 0, str(plan.price), _iso(now)))
        return _account_dict(conn, _row(conn, user_id))


def stats(days=30):
    with connect() as conn:
        accounts = conn.execute("SELECT COUNT(*) n FROM accounts").fetchone()["n"]
        paying = conn.execute("SELECT COUNT(DISTINCT user_id) n FROM purchases").fetchone()["n"]
        rows = conn.execute("SELECT plan_key, plan_name, price, created_at FROM purchases ORDER BY id").fetchall()
        used = conn.execute("SELECT COUNT(*) n FROM ledger WHERE reason='analysis'").fetchone()["n"]
    revenue = sum((Decimal(r["price"]) for r in rows), Decimal("0"))
    cutoff = _now() - timedelta(days=days)
    by_plan, by_day = {}, {}
    for r in rows:
        by_plan[r["plan_name"]] = by_plan.get(r["plan_name"], 0) + 1
        created = _parse(r["created_at"])
        if created >= cutoff:
            day = created.date().isoformat()
            by_day[day] = str(Decimal(by_day.get(day, "0")) + Decimal(r["price"]))
    return {"accounts": accounts, "paying_accounts": paying, "purchases": len(rows), "revenue": str(revenue),
            "analyses_charged": used, "by_plan": by_plan, "revenue_by_day": by_day}
