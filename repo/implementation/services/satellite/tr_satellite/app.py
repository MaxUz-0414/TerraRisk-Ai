"""HTTP API of the satellite service.

POST /v1/features        {geometry, buffer_km}              -> {center: {lat, lng}, features}
POST /v1/layers/<layer>  {geometry, features?}              -> image/jpeg   (X-Cache: HIT | MISS)
GET  /v1/layers                                             -> {layers: {key: label}}
"""
from flask import Response, jsonify, request
from tr_common.config import env_bool
from tr_common.service import create_service_app

from . import cache, gee, geo, imagery


def _bad(message, status=400):
    return jsonify(error="bad_request", message=message), status


def _geometry(payload):
    geometry = (payload or {}).get("geometry")
    try:
        geo.validate_geometry(geometry)
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        return None, str(exc) or "Invalid geometry."
    return geometry, None


def create_app():
    app = create_service_app("satellite", "1.0.0", readiness=lambda: {
        "mode": "demo" if env_bool("USE_FAKE_DATA", True) else "earth-engine", "cache": cache.stats()})

    @app.post("/v1/features")
    def features():
        body = request.get_json(silent=True)
        geometry, error = _geometry(body)
        if error:
            return _bad(error)
        try:
            buffer_km = float((body or {}).get("buffer_km", 5))
        except (TypeError, ValueError):
            return _bad("buffer_km must be a number.")
        if not 1 <= buffer_km <= 10:
            return _bad("buffer_km must be between 1 and 10.")
        lat, lng = geo.centroid(geometry)
        try:
            data = gee.get_features(geometry, buffer_km, (lat, lng))
        except Exception as exc:  # Earth Engine down, no data for this place...
            app.logger.exception("Feature extraction failed")
            return jsonify(error="upstream_failed", message=f"{type(exc).__name__}: {exc}"[:300]), 502
        return jsonify({"center": {"lat": lat, "lng": lng}, "features": data, "mode": "demo" if env_bool("USE_FAKE_DATA", True) else "live"})

    @app.get("/v1/layers")
    def layers():
        return jsonify({"layers": imagery.LAYERS})

    @app.post("/v1/layers/<layer>")
    def layer(layer):
        if layer not in imagery.LAYERS:
            return jsonify(error="not_found", message=f"Unknown layer {layer!r}."), 404
        body = request.get_json(silent=True)
        geometry, error = _geometry(body)
        if error:
            return _bad(error)
        mode = "demo" if env_bool("USE_FAKE_DATA", True) else "live"
        data = cache.get(geometry, layer, mode)
        hit = data is not None
        if not hit:
            try:
                data, _ = imagery.render_layer(geometry, layer, (body or {}).get("features") or {})
            except Exception as exc:
                app.logger.exception("Picture failed")
                return jsonify(error="upstream_failed", message=f"{type(exc).__name__}: {exc}"[:300]), 502
            cache.put(geometry, layer, mode, data)
        return Response(data, mimetype="image/jpeg", headers={"X-Cache": "HIT" if hit else "MISS", "Cache-Control": "private, max-age=3600"})

    return app
