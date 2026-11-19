import base64
import io

from PIL import Image

from .base import POLYGON, ServiceTest, dead_client, install, registry

from tr_common.client import ServiceError


def sample(include_extras=True):
    sat, risk = registry.client("satellite"), registry.client("risk")
    body = sat.post("/v1/features", json={"geometry": POLYGON, "buffer_km": 5}).json()
    features = body["features"]
    scored = risk.post("/v1/score", json={"features": features}).json()
    view = risk.post("/v1/view", json={"features": features, "score": scored["risk_score"], "persona": "investor"}).json()
    level = "low" if scored["risk_score"] < 40 else "medium" if scored["risk_score"] < 65 else "high"
    data = {"parcel_id": "TR-00001", "nickname": "Test plot", "place": "Yunusabad, Tashkent, Uzbekistan", "coords": "41.3, 69.2", "area_ha": 90.0,
            "buffer_km": 5, "persona": "Investor", "date": "Nov 11, 2026", "score": scored["risk_score"], "level": level, "headline": view["headline"],
            "hazards": scored["hazards"], "geometry": POLYGON, "features": features}
    if include_extras:
        v = view["view"]
        data.update(verdict=v["verdict"], cards=v["cards"], factors=v["factors"], checklist=v["checklist"], flags=v.get("flags"), notes=v["notes"],
                    scenarios=view.get("scenarios"), question=v["question"], ndvi=features["ndvi_series"], lst=features["lst_series"],
                    rain=features["rain_series"], advisory=[{"label": "Advisory", "text": "Test advice."}], advisory_source="template")
    return data


class ReportTests(ServiceTest):
    def setUp(self):
        super().setUp()
        self.report = registry.client("report")

    def pdf(self, data):
        reply = self.report.post("/v1/reports", json=data)
        self.assertEqual(reply.headers["Content-Type"], "application/pdf")
        self.assertTrue(reply.content.startswith(b"%PDF"))
        return reply

    def test_full_report_has_all_four_satellite_pictures(self):
        reply = self.pdf(sample())
        self.assertEqual(reply.headers["X-Images-Included"], "4")
        self.assertGreater(len(reply.content), 200_000)  # four embedded JPEGs

    def test_minimal_report_still_works(self):
        self.pdf(sample(include_extras=False))

    def test_report_survives_a_dead_satellite_service(self):
        data = sample(include_extras=False)  # built while the satellite service is still up
        install("satellite", dead_client("satellite"))
        self.assertEqual(self.pdf(data).headers["X-Images-Included"], "0")

    def test_supplied_pictures_are_used_without_calling_the_satellite_service(self):
        data = sample()
        buf = io.BytesIO()
        Image.new("RGB", (160, 100), (10, 120, 60)).save(buf, "JPEG")
        data["images"] = {layer: base64.b64encode(buf.getvalue()).decode() for layer in ("truecolor", "ndvi", "heat", "water")}
        install("satellite", dead_client("satellite"))
        self.assertEqual(self.pdf(data).headers["X-Images-Included"], "4")

    def test_non_latin_text_does_not_crash(self):
        data = sample()
        data.update(nickname="Тошкент — тест ✓", place="Chilonzor — Тошкент, O‘zbekiston")
        self.pdf(data)

    def test_validation(self):
        for body in ({}, {"parcel_id": "x"}, {**sample(False), "level": "extreme"}):
            with self.assertRaises(ServiceError) as caught:
                self.report.post("/v1/reports", json=body)
            self.assertEqual(caught.exception.status, 400)
