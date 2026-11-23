"""Service-to-service HTTP client with timeouts, retries and a small circuit breaker.

Two transports with the same interface:
  * HTTP (production / docker compose): requests.Session to http://<service>:<port>
  * in-process (tests and `python manage.py runserver` without Docker): calls the Flask app directly

Failure behaviour (what callers can rely on):
  * connection error / timeout / HTTP 5xx  -> counted as a failure; GETs are retried once
  * 5 failures in a row                    -> the circuit opens for 15 s: calls fail instantly (ServiceUnavailable)
                                              instead of piling up behind a dead service
  * HTTP 4xx                               -> returned to the caller as ServiceError(status, payload); not a failure
"""
import logging
import threading
import time

from .context import current_request_id

logger = logging.getLogger("tr.client")


class ServiceError(Exception):
    """The service answered with an error (HTTP 4xx/5xx)."""

    def __init__(self, service, status, payload=None):
        self.service, self.status, self.payload = service, status, payload or {}
        super().__init__(f"{service} returned {status}: {self.payload.get('message') or self.payload.get('error') or ''}")


class ServiceUnavailable(ServiceError):
    """The service could not be reached (down, timed out, or circuit open)."""

    def __init__(self, service, reason):
        super().__init__(service, 503, {"error": "unavailable", "message": reason})


class Reply:
    def __init__(self, status_code, content, headers):
        self.status_code, self.content, self.headers = status_code, content, headers

    def json(self):
        import json

        return json.loads(self.content.decode("utf-8")) if self.content else {}


class Client:
    def __init__(self, name, base_url="", token="", timeout=10.0, app=None, breaker_threshold=5, breaker_reset=15.0):
        self.name, self.base_url, self.token, self.timeout, self.app = name, base_url.rstrip("/"), token, timeout, app
        self.breaker_threshold, self.breaker_reset = breaker_threshold, breaker_reset
        self._failures, self._opened_at = 0, 0.0
        self._lock = threading.Lock()
        self._session = None

    # ------------------------------------------------------------------ breaker
    def _check_circuit(self):
        with self._lock:
            if self._failures >= self.breaker_threshold:
                if time.time() - self._opened_at < self.breaker_reset:
                    raise ServiceUnavailable(self.name, "circuit open: too many recent failures")
                self._failures = self.breaker_threshold - 1  # half-open: let one call through

    def _record(self, ok):
        with self._lock:
            if ok:
                self._failures = 0
            else:
                self._failures += 1
                if self._failures >= self.breaker_threshold:
                    self._opened_at = time.time()

    # ------------------------------------------------------------------ transports
    def _send(self, method, path, json_body, params, headers, timeout):
        if self.app is not None:
            client = self.app.test_client()
            resp = client.open(path, method=method, json=json_body, query_string=params, headers=headers)
            return Reply(resp.status_code, resp.get_data(), dict(resp.headers))
        import requests

        if self._session is None:
            self._session = requests.Session()
        resp = self._session.request(method, self.base_url + path, json=json_body, params=params, headers=headers, timeout=timeout)
        return Reply(resp.status_code, resp.content, dict(resp.headers))

    def request(self, method, path, json=None, params=None, timeout=None, extra_headers=None):
        headers = {"X-Request-ID": current_request_id(), **(extra_headers or {})}
        if self.token:
            headers["X-Service-Token"] = self.token
        self._check_circuit()
        attempts = 2 if method.upper() == "GET" else 1
        last = None
        for attempt in range(attempts):
            try:
                reply = self._send(method.upper(), path, json, params, headers, timeout or self.timeout)
            except Exception as exc:  # connection refused, DNS, timeout...
                last = f"{type(exc).__name__}: {exc}"[:160]
                logger.warning("%s %s failed (attempt %d): %s", self.name, path, attempt + 1, last)
                continue
            if reply.status_code >= 500:
                last = f"HTTP {reply.status_code}"
                logger.warning("%s %s -> %s (attempt %d)", self.name, path, last, attempt + 1)
                if attempt + 1 == attempts:
                    self._record(False)
                    raise ServiceError(self.name, reply.status_code, _safe_json(reply))
                continue
            self._record(True)
            if reply.status_code >= 400:
                raise ServiceError(self.name, reply.status_code, _safe_json(reply))
            return reply
        self._record(False)
        raise ServiceUnavailable(self.name, last or "no answer")

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, json=None, **kw):
        return self.request("POST", path, json=json, **kw)


def _safe_json(reply):
    try:
        data = reply.json()
        return data if isinstance(data, dict) else {"message": str(data)[:200]}
    except Exception:
        return {"message": (reply.content or b"")[:200].decode("utf-8", "replace")}
