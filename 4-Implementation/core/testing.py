"""Shared helpers for the web tests.

Every test gets its own throw-away billing / geocode / satellite storage and fresh in-process services, so tests never see each
other's data and never touch the network (Nominatim / ipwho.is are replaced by canned answers when a test needs a place name).
"""
import os
import tempfile
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from tr_common import registry
from tr_common.client import Client

PASSWORD = "Str0ng-pass!"
SQUARE = {"type": "Polygon", "coordinates": [[[69.2, 41.3], [69.3, 41.3], [69.3, 41.4], [69.2, 41.4], [69.2, 41.3]]]}

# What Nominatim / ipwho.is would say, so tests need no internet.
REVERSE_TASHKENT = {"display_name": "Yunusabad, Tashkent, Uzbekistan",
                    "address": {"suburb": "Yunusabad", "state": "Tashkent", "country": "Uzbekistan", "country_code": "uz"}}
SEARCH_TASHKENT = [{"display_name": "Tashkent, Uzbekistan", "lat": "41.3", "lon": "69.2", "boundingbox": ["41.2", "41.4", "69.1", "69.3"],
                    "type": "city", "name": "Tashkent", "address": {"city": "Tashkent", "country": "Uzbekistan", "country_code": "uz"}}]
IP_TASHKENT = {"success": True, "country": "Uzbekistan", "country_code": "UZ", "city": "Tashkent", "region": "Tashkent", "latitude": 41.3, "longitude": 69.2}


def fake_geocoder(url, *args, **kwargs):
    """Stand-in for tr_geocode.providers.fetch_json: answers search, reverse and IP lookups for Tashkent."""
    if "ipwho" in url:
        return IP_TASHKENT
    if "reverse" in url:
        return REVERSE_TASHKENT
    return SEARCH_TASHKENT


def dead_client(name):
    """A client for a service that is not running (connection refused at once)."""
    return Client(name, base_url="http://127.0.0.1:9", token=os.environ.get("INTERNAL_TOKEN", "dev-internal-token"), timeout=1)


def install(name, client):
    registry._clients[name] = client


@override_settings(USE_FAKE_DATA=True, GEMINI_API_KEY="", LOGIN_GEO_ASYNC=False, PAYMENTS_DEMO=True, GOOGLE_MAPS_API_KEY="")
class ServiceCase(TestCase):
    """TestCase whose services run in-process on temporary storage and never reach the internet."""

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        env = mock.patch.dict(os.environ, {
            "USE_FAKE_DATA": "True", "GEMINI_API_KEY": "", "SERVICES_MODE": "inprocess",
            "BILLING_DB": os.path.join(self._tmp.name, "billing.sqlite3"), "GEOCODE_DB": os.path.join(self._tmp.name, "geocode.sqlite3"),
            "CACHE_DIR": os.path.join(self._tmp.name, "sat-cache"),
        })
        env.start()
        self.addCleanup(env.stop)
        geo = mock.patch("tr_geocode.providers.fetch_json", side_effect=fake_geocoder) if self.fake_geocoder else None
        registry.reset()
        registry.ensure_path("geocode")
        self.addCleanup(registry.reset)
        if geo:
            geo.start()
            self.addCleanup(geo.stop)
        cache.clear()

    fake_geocoder = True
