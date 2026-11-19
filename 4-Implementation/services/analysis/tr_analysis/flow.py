"""The analysis workflow: what is critical, what is optional, what happens when a step fails."""
import contextvars
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from tr_common import registry
from tr_common.client import ServiceError

logger = logging.getLogger("tr.analysis")


class AnalysisFailed(Exception):
    """A critical step failed; `status` is the HTTP status to answer with, `step` names the service."""

    def __init__(self, step, status, message):
        self.step, self.status, self.message = step, status, message
        super().__init__(message)


def _call(step, fn):
    """Run fn(); return (value, ms). Errors become AnalysisFailed for critical steps (the caller decides)."""
    started = time.perf_counter()
    value = fn()
    return value, round((time.perf_counter() - started) * 1000)


def _message(exc):
    payload = getattr(exc, "payload", {}) or {}
    return payload.get("message") or str(exc)


def run(geometry, buffer_km, persona):
    timings, degraded = {}, []
    satellite, risk, advisory, geocode = (registry.client(n) for n in ("satellite", "risk", "advisory", "geocode"))

    # 1. features (critical): everything else is computed from them
    try:
        reply, timings["satellite"] = _call("satellite", lambda: satellite.post("/v1/features", json={"geometry": geometry, "buffer_km": buffer_km}))
    except ServiceError as exc:
        status = 400 if exc.status == 400 else 502
        raise AnalysisFailed("satellite", status, _message(exc))
    body = reply.json()
    features, center, mode = body["features"], body["center"], body.get("mode", "")

    # 2. the place name runs in the background while we score (optional)
    context = contextvars.copy_context()

    def name_place():
        try:
            data, ms = _call("geocode", lambda: context.run(lambda: geocode.get("/v1/reverse", params={"lat": center["lat"], "lng": center["lng"]}, timeout=6)))
            timings["geocode"] = ms
            return data.json()
        except Exception as exc:
            logger.info("Place name unavailable: %s", exc)
            degraded.append({"service": "geocode", "effect": "The place name could not be looked up."})
            return {}

    with ThreadPoolExecutor(max_workers=1) as pool:
        place_future = pool.submit(name_place)

        # 3. score (critical)
        try:
            reply, timings["risk"] = _call("risk", lambda: risk.post("/v1/score", json={"features": features}))
        except ServiceError as exc:
            raise AnalysisFailed("risk", 502, _message(exc))
        scored = reply.json()

        # 4. persona view + headline (critical for the page we show)
        try:
            reply, ms = _call("risk", lambda: risk.post("/v1/view", json={"features": features, "score": scored["risk_score"], "persona": persona}))
            timings["risk"] += ms
        except ServiceError as exc:
            raise AnalysisFailed("risk", 502, _message(exc))
        view = reply.json()

        # 5. written advice (optional: the page works without it)
        advice, source, note = [], "unavailable", "The advice service is not answering; the numbers above are unaffected."
        try:
            reply, timings["advisory"] = _call("advisory", lambda: advisory.post("/v1/advice", json={"features": features, "score": scored["risk_score"], "persona": persona}))
            data = reply.json()
            advice, source, note = data["advisory"], data.get("source", ""), data.get("note", "")
        except ServiceError as exc:
            logger.warning("Advice unavailable: %s", exc)
            degraded.append({"service": "advisory", "effect": "Written advice is missing; scores and charts are complete."})
        place = place_future.result()

    return {
        "center": center, "mode": mode, "features": features,
        "risk_score": scored["risk_score"], "parts": scored.get("parts", {}), "hazards": scored["hazards"],
        "headline": view["headline"], "view": view["view"], "scenarios": view.get("scenarios", []),
        "advisory": advice, "advisory_source": source, "advisory_note": note,
        "place": place, "degraded": degraded, "timings_ms": timings,
    }
