from .base import POLYGON, ServiceTest, dead_client, install, registry

from tr_common.client import ServiceError


class AnalysisTests(ServiceTest):
    def setUp(self):
        super().setUp()
        self.analysis = registry.client("analysis")
        # the sandbox has no internet: stand in for the place lookup so the happy path is deterministic
        from unittest import mock

        self._patch = mock.patch("tr_geocode.providers.fetch_json", return_value={
            "display_name": "Yunusabad, Tashkent, Uzbekistan", "address": {"suburb": "Yunusabad", "state": "Tashkent", "country": "Uzbekistan", "country_code": "uz"}})
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def analyze(self, **extra):
        return self.analysis.post("/v1/analyze", json={"geometry": POLYGON, "buffer_km": 5, "persona": "investor", **extra}).json()

    def test_happy_path_returns_everything_the_web_app_stores_and_shows(self):
        body = self.analyze()
        for key in ("center", "features", "risk_score", "parts", "hazards", "headline", "view", "scenarios", "advisory", "place", "timings_ms"):
            self.assertIn(key, body, key)
        self.assertEqual(body["degraded"], [])
        self.assertEqual(body["place"]["country_code"], "UZ")
        self.assertTrue(0 <= body["risk_score"] <= 100)
        self.assertEqual(body["advisory_source"], "template")

    def test_farmer_gets_no_scenarios(self):
        self.assertFalse(self.analyze(persona="farmer")["scenarios"])

    def test_advisory_down_degrades_but_still_answers(self):
        install("advisory", dead_client("advisory"))
        body = self.analyze()
        self.assertEqual(body["advisory"], [])
        self.assertEqual([d["service"] for d in body["degraded"]], ["advisory"])
        self.assertTrue(body["hazards"])

    def test_geocode_down_degrades_but_still_answers(self):
        install("geocode", dead_client("geocode"))
        body = self.analyze()
        self.assertEqual(body["place"], {})
        self.assertIn("geocode", [d["service"] for d in body["degraded"]])
        self.assertTrue(body["advisory"])

    def test_satellite_down_is_a_502_naming_the_service(self):
        install("satellite", dead_client("satellite"))
        with self.assertRaises(ServiceError) as caught:
            self.analyze()
        self.assertEqual(caught.exception.status, 502)
        self.assertEqual(caught.exception.payload["step"], "satellite")

    def test_risk_down_is_a_502_naming_the_service(self):
        install("risk", dead_client("risk"))
        with self.assertRaises(ServiceError) as caught:
            self.analyze()
        self.assertEqual(caught.exception.payload["step"], "risk")

    def test_bad_input_is_400(self):
        for body in ({}, {"geometry": POLYGON, "persona": "wizard"}, {"geometry": POLYGON, "buffer_km": "far"},
                     {"geometry": {"type": "Polygon", "coordinates": []}}):
            with self.assertRaises(ServiceError) as caught:
                self.analysis.post("/v1/analyze", json=body)
            self.assertEqual(caught.exception.status, 400, body)
