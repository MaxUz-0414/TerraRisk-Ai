from unittest import mock

from .base import ServiceTest, registry

from tr_common.client import ServiceError

SEARCH = [{"display_name": "Tashkent, Uzbekistan", "lat": "41.3", "lon": "69.2", "boundingbox": ["41.2", "41.4", "69.1", "69.3"],
           "type": "city", "name": "Tashkent", "address": {"city": "Tashkent", "country": "Uzbekistan", "country_code": "uz"}}]
REVERSE = {"display_name": "Yunusabad, Tashkent, Uzbekistan", "address": {"suburb": "Yunusabad", "state": "Tashkent", "country": "Uzbekistan", "country_code": "uz"}}


class GeocodeTests(ServiceTest):
    def setUp(self):
        super().setUp()
        self.geo = registry.client("geocode")

    def test_search_normalises_results(self):
        with mock.patch("tr_geocode.providers.fetch_json", return_value=SEARCH):
            results = self.geo.get("/v1/search", params={"q": "tashkent"}).json()["results"]
        self.assertEqual(results[0]["country_code"], "UZ")
        self.assertEqual(results[0]["bbox"], [41.2, 69.1, 41.4, 69.3])
        self.assertIn("Tashkent", results[0]["short"])

    def test_second_search_comes_from_the_cache(self):
        with mock.patch("tr_geocode.providers.fetch_json", return_value=SEARCH) as fetch:
            self.geo.get("/v1/search", params={"q": "cache me please"})
            self.geo.get("/v1/search", params={"q": "cache me please"})
        self.assertEqual(fetch.call_count, 1)

    def test_reverse(self):
        with mock.patch("tr_geocode.providers.fetch_json", return_value=REVERSE):
            body = self.geo.get("/v1/reverse", params={"lat": 41.3, "lng": 69.2}).json()
        self.assertEqual(body["country_code"], "UZ")
        self.assertEqual(body["name"], "Yunusabad, Tashkent")

    def test_provider_failure_is_a_clean_502(self):
        with mock.patch("tr_geocode.providers.fetch_json", side_effect=OSError("offline")):
            with self.assertRaises(ServiceError) as caught:
                self.geo.get("/v1/reverse", params={"lat": 1.5, "lng": 2.5})
        self.assertEqual(caught.exception.status, 502)

    def test_validation(self):
        for path, params in (("/v1/search", {"q": "a"}), ("/v1/reverse", {"lat": 91, "lng": 0}), ("/v1/reverse", {"lat": "x", "lng": 0})):
            with self.assertRaises(ServiceError) as caught:
                self.geo.get(path, params=params)
            self.assertEqual(caught.exception.status, 400, params)

    def test_private_ips_are_not_sent_to_the_outside_world(self):
        with mock.patch("tr_geocode.providers.fetch_json") as fetch:
            body = self.geo.get("/v1/ip/192.168.1.5").json()
        fetch.assert_not_called()
        self.assertTrue(body["local"])

    def test_public_ip_lookup(self):
        data = {"success": True, "country": "Uzbekistan", "country_code": "UZ", "city": "Tashkent", "region": "Tashkent", "latitude": 41.3, "longitude": 69.2}
        with mock.patch("tr_geocode.providers.fetch_json", return_value=data):
            body = self.geo.get("/v1/ip/8.8.4.4").json()
        self.assertEqual(body["city"], "Tashkent")
        with self.assertRaises(ServiceError):
            self.geo.get("/v1/ip/not-an-ip")
