"""Shared test setup: demo data, in-process transport, throw-away databases. Import this first in every test module."""
import os
import sys
import tempfile
from pathlib import Path

SERVICES = Path(__file__).resolve().parents[1]
for sub in ("common", "analysis", "satellite", "risk", "advisory", "report", "billing", "geocode", "chatbot"):
    path = str(SERVICES / sub)
    if path not in sys.path:
        sys.path.insert(0, path)

_TMP = tempfile.mkdtemp(prefix="tr-tests-")
os.environ.update(
    USE_FAKE_DATA="True", SERVICES_MODE="inprocess", INTERNAL_TOKEN="test-token", GEMINI_API_KEY="", PAYMENTS_DEMO="True",
    BILLING_DB=os.path.join(_TMP, "billing.sqlite3"), GEOCODE_DB=os.path.join(_TMP, "geocode.sqlite3"), CACHE_DIR=os.path.join(_TMP, "sat-cache"),
)

import unittest  # noqa: E402

from tr_common import registry  # noqa: E402
from tr_common.client import Client  # noqa: E402

POLYGON = {"type": "Polygon", "coordinates": [[[69.2, 41.3], [69.21, 41.3], [69.21, 41.31], [69.2, 41.31], [69.2, 41.3]]]}
POINT = {"type": "Point", "coordinates": [69.2, 41.3]}
HEADERS = {"X-Service-Token": "test-token"}


class ServiceTest(unittest.TestCase):
    def setUp(self):
        registry.reset()


def dead_client(name):
    """A client for a service that is not running (connection refused, instantly)."""
    return Client(name, base_url="http://127.0.0.1:9", token="test-token", timeout=1)


def install(name, client):
    registry._clients[name] = client
