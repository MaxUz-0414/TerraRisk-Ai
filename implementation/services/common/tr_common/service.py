"""Flask app factory used by every service.

Every service gets, for free:
  * GET /healthz  : liveness + (optional) readiness checks, public, used by Docker healthchecks
  * GET /v1/info  : uptime, request counts, error counts, average latency (shown in the admin dashboard)
  * service-token check (X-Service-Token == INTERNAL_TOKEN) on everything else, so only our own services can call it
  * X-Request-ID propagation and one structured log line per request
  * JSON error bodies: {"error": "<code>", "message": "<human text>"}
"""
import hmac
import json
import logging
import threading
import time

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException

from .config import env_str
from .context import new_request_id, request_id

PUBLIC_PATHS = ("/healthz",)


def create_service_app(name, version="1.0.0", readiness=None):
    """readiness: optional callable returning {"check name": True/False/"text"}; a False makes /healthz return 503."""
    app = Flask(name)
    app.json.sort_keys = False
    started = time.time()
    lock = threading.Lock()
    stats = {"requests": 0, "errors": 0, "total_ms": 0.0, "last_error": ""}
    logger = logging.getLogger(f"tr.{name}")
    app.extensions["tr_stats"] = stats

    @app.before_request
    def _begin():
        g.t0 = time.perf_counter()
        g.rid = request.headers.get("X-Request-ID") or new_request_id()
        request_id.set(g.rid)
        if request.path in PUBLIC_PATHS:
            return None
        expected = env_str("INTERNAL_TOKEN")
        if expected and not hmac.compare_digest(request.headers.get("X-Service-Token", ""), expected):
            return jsonify(error="unauthorized", message="Missing or wrong service token."), 401
        return None

    @app.after_request
    def _end(response):
        elapsed = (time.perf_counter() - getattr(g, "t0", time.perf_counter())) * 1000
        if request.path not in PUBLIC_PATHS:
            with lock:
                stats["requests"] += 1
                stats["total_ms"] += elapsed
                if response.status_code >= 500:
                    stats["errors"] += 1
        response.headers["X-Request-ID"] = getattr(g, "rid", "")
        response.headers["X-Service"] = name
        logger.info(json.dumps({"svc": name, "rid": getattr(g, "rid", ""), "method": request.method, "path": request.path,
                                "status": response.status_code, "ms": round(elapsed, 1)}))
        return response

    @app.errorhandler(HTTPException)
    def _http_error(exc):
        return jsonify(error=(exc.name or "error").lower().replace(" ", "_"), message=exc.description or exc.name), exc.code

    @app.errorhandler(Exception)
    def _crash(exc):
        logger.exception("Unhandled error in %s", name)
        with lock:
            stats["last_error"] = f"{type(exc).__name__}: {exc}"[:200]
        return jsonify(error="internal_error", message="The service hit an unexpected error."), 500

    @app.get("/healthz")
    def _healthz():
        checks, ok = {}, True
        if readiness:
            try:
                checks = readiness() or {}
            except Exception as exc:  # a broken check must not crash the endpoint
                checks, ok = {"readiness": f"{type(exc).__name__}: {exc}"}, False
            ok = ok and all(v is not False for v in checks.values())
        body = {"status": "ok" if ok else "unavailable", "service": name, "version": version,
                "uptime_s": int(time.time() - started), "checks": checks}
        return jsonify(body), (200 if ok else 503)

    @app.get("/v1/info")
    def _info():
        with lock:
            n = stats["requests"]
            return jsonify({"service": name, "version": version, "uptime_s": int(time.time() - started),
                            "requests": n, "errors": stats["errors"],
                            "avg_ms": round(stats["total_ms"] / n, 1) if n else 0.0, "last_error": stats["last_error"]})

    return app
