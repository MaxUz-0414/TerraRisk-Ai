from .base import ServiceTest, registry
from .test_risk import FEATURES

from tr_common.client import ServiceError


class AdvisoryTests(ServiceTest):
    def setUp(self):
        super().setUp()
        self.advisory = registry.client("advisory")

    def test_without_a_key_it_uses_templates_and_says_so(self):
        body = self.advisory.post("/v1/advice", json={"features": FEATURES, "score": 70, "persona": "farmer"}).json()
        self.assertEqual(body["source"], "template")
        self.assertGreaterEqual(len(body["advisory"]), 3)
        for item in body["advisory"]:
            self.assertTrue(item["label"] and item["text"])

    def test_advice_differs_by_persona(self):
        farmer = self.advisory.post("/v1/advice", json={"features": FEATURES, "score": 70, "persona": "farmer"}).json()["advisory"]
        investor = self.advisory.post("/v1/advice", json={"features": FEATURES, "score": 70, "persona": "investor"}).json()["advisory"]
        self.assertNotEqual(farmer, investor)

    def test_validates_input(self):
        for body in ({}, {"features": {}, "score": 5}, {"features": FEATURES, "score": "high"}):
            with self.assertRaises(ServiceError) as caught:
                self.advisory.post("/v1/advice", json=body)
            self.assertEqual(caught.exception.status, 400)
