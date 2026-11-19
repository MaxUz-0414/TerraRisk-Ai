from .base import ServiceTest, registry

FEATURES = {"upstream_slope_deg": 28.0, "dist_to_river_m": 400, "ndvi_trend_pct": -12.0, "lst_peak_c": 38.0,
            "soil_moisture_change_pct": -15.0, "siltation": "High", "soil_saturation": "High"}


class RiskTests(ServiceTest):
    def setUp(self):
        super().setUp()
        self.risk = registry.client("risk")

    def test_score_returns_score_parts_and_hazards(self):
        body = self.risk.post("/v1/score", json={"features": FEATURES}).json()
        self.assertTrue(0 <= body["risk_score"] <= 100)
        self.assertEqual(set(body["parts"]), {"flood", "landslide"})
        self.assertGreaterEqual(len(body["hazards"]), 4)  # 5 when the satellite service also sends landslide inputs
        for hazard in body["hazards"]:
            self.assertIn(hazard["level"], ("low", "medium", "high"))

    def test_steeper_and_closer_scores_higher(self):
        calm = dict(FEATURES, upstream_slope_deg=2.0, dist_to_river_m=6000, ndvi_trend_pct=8.0, lst_peak_c=22.0,
                    soil_moisture_change_pct=5.0, siltation="Low", soil_saturation="Low")
        risky = self.risk.post("/v1/score", json={"features": FEATURES}).json()["risk_score"]
        safe = self.risk.post("/v1/score", json={"features": calm}).json()["risk_score"]
        self.assertGreater(risky, safe)

    def test_missing_features_are_a_400_naming_the_fields(self):
        from tr_common.client import ServiceError

        with self.assertRaises(ServiceError) as caught:
            self.risk.post("/v1/score", json={"features": {"upstream_slope_deg": 3}})
        self.assertEqual(caught.exception.status, 400)

    def test_view_has_persona_content(self):
        for persona in ("farmer", "homebuyer", "investor", "developer", "analyst"):
            body = self.risk.post("/v1/view", json={"features": FEATURES, "score": 55, "persona": persona}).json()
            self.assertTrue(body["headline"]["value"], persona)
            self.assertTrue(body["view"]["cards"], persona)
            self.assertTrue(body["view"]["checklist"]["items"], persona)

    def test_scenarios_only_for_investor_group(self):
        investor = self.risk.post("/v1/view", json={"features": FEATURES, "score": 55, "persona": "investor"}).json()
        farmer = self.risk.post("/v1/view", json={"features": FEATURES, "score": 55, "persona": "farmer"}).json()
        self.assertTrue(investor["scenarios"])
        self.assertFalse(farmer.get("scenarios"))

    def test_model_info(self):
        body = self.risk.get("/v1/model").json()
        self.assertIn("flood", body)
        self.assertIn("landslide", body)
