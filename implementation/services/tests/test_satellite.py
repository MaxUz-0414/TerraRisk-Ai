import io

from PIL import Image

from .base import POINT, POLYGON, ServiceTest, registry

from tr_common.client import ServiceError


class SatelliteTests(ServiceTest):
    def setUp(self):
        super().setUp()
        self.sat = registry.client("satellite")

    def test_features_have_every_field_the_other_services_need(self):
        body = self.sat.post("/v1/features", json={"geometry": POLYGON, "buffer_km": 5}).json()
        for key in ("upstream_slope_deg", "dist_to_river_m", "ndvi_trend_pct", "lst_peak_c", "soil_moisture_change_pct", "siltation",
                    "soil_saturation", "ndvi_series", "lst_series", "rain_series", "landslide_inputs", "built_up_pct", "hand_m"):
            self.assertIn(key, body["features"], key)
        self.assertAlmostEqual(body["center"]["lat"], 41.305, places=2)
        self.assertEqual(body["mode"], "demo")

    def test_demo_features_are_stable_for_the_same_place(self):
        a = self.sat.post("/v1/features", json={"geometry": POLYGON, "buffer_km": 5}).json()["features"]
        b = self.sat.post("/v1/features", json={"geometry": POLYGON, "buffer_km": 5}).json()["features"]
        self.assertEqual(a, b)

    def test_point_geometry_works(self):
        self.assertIn("features", self.sat.post("/v1/features", json={"geometry": POINT, "buffer_km": 3}).json())

    def test_bad_input_is_400(self):
        for body in ({}, {"geometry": {"type": "Polygon", "coordinates": []}}, {"geometry": POLYGON, "buffer_km": 99},
                     {"geometry": {"type": "Point", "coordinates": [500, 500]}}):
            with self.assertRaises(ServiceError) as caught:
                self.sat.post("/v1/features", json=body)
            self.assertEqual(caught.exception.status, 400, body)

    def test_every_layer_is_a_1600x1000_jpeg(self):
        layers = self.sat.get("/v1/layers").json()["layers"]
        self.assertEqual(set(layers), {"truecolor", "ndvi", "heat", "water"})
        for layer in layers:
            reply = self.sat.post(f"/v1/layers/{layer}", json={"geometry": POLYGON, "features": {}})
            self.assertEqual(reply.headers["Content-Type"], "image/jpeg")
            image = Image.open(io.BytesIO(reply.content))
            self.assertEqual(image.size, (1600, 1000), layer)

    def test_second_request_is_served_from_cache(self):
        geometry = {"type": "Polygon", "coordinates": [[[10.0, 10.0], [10.01, 10.0], [10.01, 10.01], [10.0, 10.0]]]}
        first = self.sat.post("/v1/layers/ndvi", json={"geometry": geometry})
        second = self.sat.post("/v1/layers/ndvi", json={"geometry": geometry})
        self.assertEqual(first.headers["X-Cache"], "MISS")
        self.assertEqual(second.headers["X-Cache"], "HIT")
        self.assertEqual(first.content, second.content)

    def test_unknown_layer_is_404(self):
        with self.assertRaises(ServiceError) as caught:
            self.sat.post("/v1/layers/radar", json={"geometry": POLYGON})
        self.assertEqual(caught.exception.status, 404)
