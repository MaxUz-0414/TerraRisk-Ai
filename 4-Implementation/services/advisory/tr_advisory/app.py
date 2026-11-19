"""HTTP API of the advisory service.

POST /v1/advice  {features, score, persona}  -> {advisory: [{label, text}, ...], source: "gemini"|"template", note}
"""
from flask import jsonify, request
from tr_common.config import env_str
from tr_common.service import create_service_app

from .advice import generate_advice

REQUIRED = ("upstream_slope_deg", "dist_to_river_m", "ndvi_trend_pct", "lst_peak_c", "soil_moisture_change_pct")


def create_app():
    app = create_service_app("advisory", "1.0.0", readiness=lambda: {"gemini": "configured" if env_str("GEMINI_API_KEY") else "templates only"})

    @app.post("/v1/advice")
    def advice():
        body = request.get_json(silent=True) or {}
        features, score = body.get("features"), body.get("score")
        if not isinstance(features, dict) or any(k not in features for k in REQUIRED):
            return jsonify(error="bad_request", message="'features' must contain: " + ", ".join(REQUIRED)), 400
        if not isinstance(score, (int, float)):
            return jsonify(error="bad_request", message="'score' must be a number."), 400
        items, source, note = generate_advice(features, score, body.get("persona", "investor"))
        return jsonify({"advisory": items, "source": source, "note": note})

    return app
