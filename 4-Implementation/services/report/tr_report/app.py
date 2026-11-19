"""HTTP API of the report service.

POST /v1/reports   JSON analysis -> application/pdf
  required: parcel_id, score, level, geometry, hazards
  optional: nickname, place, coords, area_ha, buffer_km, persona, date, headline, verdict, question, cards, factors, checklist,
            flags, scenarios, notes, advisory, advisory_source, features, ndvi, lst, rain, images {layer: base64 jpeg}
  The satellite pictures are fetched from the satellite service unless supplied; if it is down the PDF is still produced
  (with labelled placeholders) and the response header X-Images-Included says how many pictures made it in.
"""
from flask import Response, jsonify, request
from tr_common.service import create_service_app

from . import images as imagery
from .pdf import build_pdf

REQUIRED = ("parcel_id", "score", "level", "geometry", "hazards")


def create_app():
    app = create_service_app("report", "1.0.0")

    @app.post("/v1/reports")
    def make_report():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="bad_request", message="Send the analysis as a JSON object."), 400
        missing = [k for k in REQUIRED if data.get(k) in (None, "")]
        if missing:
            return jsonify(error="bad_request", message=f"Missing field(s): {', '.join(missing)}."), 400
        if data["level"] not in ("low", "medium", "high"):
            return jsonify(error="bad_request", message="level must be low, medium or high."), 400
        try:
            pictures = imagery.fetch_all(data["geometry"], data.get("features"), imagery.decode_supplied(data.get("images")))
            pdf = build_pdf(data, pictures)
        except (KeyError, TypeError, ValueError) as exc:
            app.logger.exception("Report data was malformed")
            return jsonify(error="bad_request", message=f"Could not build the report from this data: {type(exc).__name__}: {exc}"[:300]), 400
        return Response(pdf, mimetype="application/pdf", headers={
            "Content-Disposition": f'inline; filename="TerraRisk-{data["parcel_id"]}.pdf"',
            "X-Images-Included": str(len(pictures)), "Cache-Control": "no-store"})

    return app
