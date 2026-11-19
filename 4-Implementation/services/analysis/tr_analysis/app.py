"""HTTP API of the analysis service.

POST /v1/analyze  {geometry, buffer_km?, persona?}  ->
  {center, mode, features, risk_score, parts, hazards, headline, view, scenarios,
   advisory, advisory_source, advisory_note, place: {name, region, country, country_code, display},
   degraded: [{service, effect}], timings_ms: {service: ms}}
  400 bad input | 502 a critical step failed (body says which service) | 200 with `degraded` when only optional steps failed
"""
from flask import jsonify, request
from tr_common.service import create_service_app

from . import flow

PERSONAS = ("farmer", "homebuyer", "investor", "developer", "analyst")


def create_app():
    app = create_service_app("analysis", "1.0.0")

    @app.post("/v1/analyze")
    def analyze():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get("geometry"), dict):
            return jsonify(error="bad_request", message="Send {geometry, buffer_km, persona} as JSON."), 400
        try:
            buffer_km = float(body.get("buffer_km", 5))
        except (TypeError, ValueError):
            return jsonify(error="bad_request", message="buffer_km must be a number."), 400
        persona = body.get("persona", "investor")
        if persona not in PERSONAS:
            return jsonify(error="bad_request", message=f"persona must be one of: {', '.join(PERSONAS)}."), 400
        try:
            return jsonify(flow.run(body["geometry"], buffer_km, persona))
        except flow.AnalysisFailed as exc:
            return jsonify(error="step_failed", step=exc.step, message=exc.message), exc.status

    return app
