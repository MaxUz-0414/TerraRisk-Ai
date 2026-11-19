"""HTTP API of the risk service.

POST /v1/score   {features}                        -> {risk_score, parts, hazards}
POST /v1/view    {features, score, persona}        -> {headline, view, scenarios}   (everything the results page needs)
GET  /v1/model                                     -> {flood: {...}, landslide: {...}|null}
"""
from flask import jsonify, request
from tr_common.service import create_service_app

from . import ml
from .headline import persona_headline
from .persona_view import build_persona_view
from .risk import PERSONA_GROUP
from .scenarios import stress_scenarios
from .scoring import build_hazards, score_features

REQUIRED_FEATURES = ("upstream_slope_deg", "dist_to_river_m", "ndvi_trend_pct", "lst_peak_c",
                     "soil_moisture_change_pct", "siltation", "soil_saturation")


def _bad(message, status=400):
    return jsonify(error="bad_request", message=message), status


def _features_from(payload):
    features = (payload or {}).get("features")
    if not isinstance(features, dict):
        return None, "Body must contain a 'features' object."
    missing = [k for k in REQUIRED_FEATURES if k not in features]
    if missing:
        return None, "Missing features: " + ", ".join(missing)
    return features, None


def create_app():
    app = create_service_app("risk", "1.0.0", readiness=lambda: {"flood_model": ml.flood_model_info()["kind"],
                                                                  "landslide_model": "loaded" if ml.landslide_model_info() else "missing (flood score only)"})

    @app.post("/v1/score")
    def score():
        features, error = _features_from(request.get_json(silent=True))
        if error:
            return _bad(error)
        composite, flood, landslide = score_features(features)
        return jsonify({
            "risk_score": composite,
            "parts": {"flood": flood, "landslide": landslide},
            "hazards": build_hazards(features, landslide),
        })

    @app.post("/v1/view")
    def view():
        body = request.get_json(silent=True) or {}
        features, error = _features_from(body)
        if error:
            return _bad(error)
        score_value, persona = body.get("score"), body.get("persona", "investor")
        if not isinstance(score_value, (int, float)):
            return _bad("'score' must be a number.")
        if persona not in PERSONA_GROUP:
            persona = "investor"
        pv = build_persona_view(features, score_value, persona)
        out = {"headline": persona_headline(features, score_value, persona), "view": pv, "scenarios": []}
        if pv["group"] == "investor":
            out["scenarios"] = stress_scenarios(features, score_value)
        return jsonify(out)

    @app.get("/v1/model")
    def model():
        return jsonify({"flood": ml.flood_model_info(), "landslide": ml.landslide_model_info()})

    return app


app = None


def get_app():
    global app
    if app is None:
        app = create_app()
    return app
