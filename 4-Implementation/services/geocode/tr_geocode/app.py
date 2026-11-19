"""HTTP API of the geocode service.

GET /v1/search?q=<text>&limit=5   -> {results: [{display, short, lat, lng, bbox: [s, w, n, e], country, country_code}]}
GET /v1/reverse?lat=..&lng=..     -> {name, region, country, country_code, display}
GET /v1/ip/<address>              -> {ip, country, country_code, city, lat, lng, local}
"""
from flask import jsonify, request
from tr_common.service import create_service_app

from . import cache, logic


def create_app():
    app = create_service_app("geocode", "1.0.0", readiness=lambda: {"cache_entries": cache.size()})

    def upstream_failed(exc):
        app.logger.warning("Geocoding provider failed: %s", exc)
        return jsonify(error="upstream_failed", message="The place lookup service is not answering right now."), 502

    @app.get("/v1/search")
    def search():
        query = request.args.get("q", "").strip()
        if len(query) < 2:
            return jsonify(error="bad_request", message="Type at least 2 characters."), 400
        try:
            limit = max(1, min(8, int(request.args.get("limit", 5))))
        except ValueError:
            limit = 5
        try:
            return jsonify({"results": logic.search(query, limit)})
        except Exception as exc:
            return upstream_failed(exc)

    @app.get("/v1/reverse")
    def reverse():
        try:
            lat, lng = float(request.args["lat"]), float(request.args["lng"])
        except (KeyError, ValueError):
            return jsonify(error="bad_request", message="lat and lng are required numbers."), 400
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return jsonify(error="bad_request", message="Coordinates out of range."), 400
        try:
            return jsonify(logic.reverse(lat, lng))
        except Exception as exc:
            return upstream_failed(exc)

    @app.get("/v1/ip/<path:address>")
    def ip(address):
        try:
            return jsonify(logic.ip_location(address))
        except ValueError as exc:
            return jsonify(error="bad_request", message=str(exc)), 400
        except Exception as exc:
            return upstream_failed(exc)

    return app
