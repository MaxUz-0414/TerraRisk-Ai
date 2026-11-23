#!/usr/bin/env python3
"""End-to-end check of a RUNNING stack over real HTTP (docker compose or scripts/run_services.py).

    python scripts/e2e_check.py                       # services on 127.0.0.1:8101-8108 (run_services.py)
    python scripts/e2e_check.py --web http://localhost:8000 --email you@x.com --password '...'   # also drives the website

It prints one line per check and exits with 1 if anything failed. It only needs the `requests` package.
"""
import argparse
import os
import re
import sys
import time

import requests

NAMES = ["analysis", "satellite", "risk", "advisory", "report", "billing", "geocode", "chatbot"]
TOKEN = os.environ.get("INTERNAL_TOKEN", "dev-internal-token")
SQUARE = {"type": "Polygon", "coordinates": [[[69.2, 41.3], [69.21, 41.3], [69.21, 41.31], [69.2, 41.31], [69.2, 41.3]]]}
failures = []


def check(label, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + label + (f"   ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(label)
    return ok


def warn(label, detail=""):
    print(f"  warn {label}   ({detail})")


def service_url(name):
    return os.environ.get(f"{name.upper()}_URL") or f"http://127.0.0.1:{8101 + NAMES.index(name)}"


def call(name, method, path, **kwargs):
    headers = {"X-Service-Token": TOKEN, **kwargs.pop("headers", {})}
    return requests.request(method, service_url(name) + path, headers=headers, timeout=kwargs.pop("timeout", 60), **kwargs)


def services():
    print("Services")
    for name in NAMES:
        try:
            r = call(name, "GET", "/healthz", timeout=5)
            check(f"{name}: healthy", r.status_code == 200 and r.json()["status"] == "ok", r.text[:120])
        except Exception as exc:
            check(f"{name}: healthy", False, str(exc)[:100])
    check("services refuse calls without the internal token", requests.get(service_url("risk") + "/v1/info", timeout=5).status_code == 401)

    print("Analysis (talks to satellite, risk, advisory, geocode)")
    started = time.time()
    r = call("analysis", "POST", "/v1/analyze", json={"geometry": SQUARE, "buffer_km": 3, "persona": "investor"})
    body = r.json() if r.ok else {}
    check("analysis answers 200", r.status_code == 200, r.text[:200])
    check("score between 0 and 100", 0 <= body.get("risk_score", -1) <= 100)
    check("persona view and scenarios present", bool(body.get("view")) and len(body.get("scenarios", [])) == 3)
    check("timings recorded per service", {"satellite", "risk"} <= set(body.get("timings_ms", {})), str(body.get("timings_ms")))
    print(f"       took {time.time() - started:.1f} s, mode={body.get('mode')}, degraded={[d['service'] for d in body.get('degraded', [])]}")
    check("bad input is a clean 400", call("analysis", "POST", "/v1/analyze", json={"geometry": "nope"}).status_code == 400)

    print("Satellite pictures")
    r = call("satellite", "POST", "/v1/layers/truecolor", json={"geometry": SQUARE, "features": body.get("features", {})})
    check("true colour JPEG, 1600x1000", r.status_code == 200 and r.content[:2] == b"\xff\xd8" and _size(r.content) == (1600, 1000), r.text[:100])
    check("unknown layer is 404", call("satellite", "POST", "/v1/layers/nope", json={"geometry": SQUARE}).status_code == 404)

    print("Report (talks to satellite)")
    data = _report_payload(body)
    r = call("report", "POST", "/v1/reports", json=data, timeout=120)
    check("PDF report", r.status_code == 200 and r.content[:4] == b"%PDF" and len(r.content) > 20000, f"{r.status_code} {len(r.content)} bytes")

    print("Billing (own database)")
    user = int(time.time())
    a = call("billing", "PUT", f"/v1/accounts/{user}", json={"email": "e2e@example.com"}).json()
    check("new account starts with free searches", a.get("free_searches", 0) >= 1, str(a)[:100])
    n = a["free_searches"]
    c1 = call("billing", "POST", f"/v1/accounts/{user}/consume", json={"key": "k1"}).json()
    c2 = call("billing", "POST", f"/v1/accounts/{user}/consume", json={"key": "k1"}).json()
    check("consume is idempotent", c1["free_searches"] == c2["free_searches"] == n - 1)
    r = call("billing", "POST", f"/v1/accounts/{user}/refund", json={"key": "k1"}).json()
    check("refund gives it back", r["free_searches"] == n)

    print("Geocode, chatbot")
    check("IP lookup of a private address stays local", call("geocode", "GET", "/v1/ip/192.168.1.2").json().get("local") is True)
    r = call("chatbot", "POST", "/v1/chat", json={"message": "how much does it cost", "context": {}})
    check("chatbot answers about pricing", r.status_code == 200 and "Starter" in r.json().get("reply", ""), r.text[:100])


def _size(jpeg):
    import io

    from PIL import Image

    return Image.open(io.BytesIO(jpeg)).size


def _report_payload(a):
    view = a["view"]
    return {"parcel_id": "TR-E2E", "nickname": "E2E parcel", "place": "Test place", "coords": "41.3N, 69.2E", "area_ha": 120, "buffer_km": 3,
            "persona": "Land Investor", "date": time.strftime("%b %d, %Y"), "score": a["risk_score"], "level": "medium", "headline": a["headline"],
            "verdict": view["verdict"], "question": view.get("question"), "cards": view.get("cards"), "factors": view.get("factors"),
            "checklist": view.get("checklist"), "flags": view.get("flags"), "scenarios": a.get("scenarios"), "notes": view.get("notes"),
            "hazards": a["hazards"], "advisory": a["advisory"], "advisory_source": a.get("advisory_source", ""), "features": a["features"],
            "ndvi": a["features"].get("ndvi_series"), "lst": a["features"].get("lst_series"), "rain": a["features"].get("rain_series"),
            "geometry": SQUARE, "imagery_note": ""}


def website(base, email, password):
    print(f"Website {base}")
    s = requests.Session()
    page = s.get(base + "/accounts/login/", timeout=30)
    check("login page", page.status_code == 200)
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.text).group(1)
    r = s.post(base + "/accounts/login/", data={"username": email, "password": password, "csrfmiddlewaretoken": token}, headers={"Referer": base}, timeout=30)
    check("sign in", r.ok and "/accounts/login" not in r.url, r.url)
    check("home for signed-in users", "Welcome back" in s.get(base + "/", timeout=30).text)
    csrf = s.cookies.get("csrftoken")
    r = s.get(base + "/api/places/search/", params={"q": "tashkent"}, timeout=30)
    if r.status_code == 503:   # no internet from this machine to Nominatim: the website says so politely instead of failing
        warn("place search is not available (is this machine online?)", r.text[:80])
    else:
        check("place search", r.status_code == 200 and r.json().get("results") is not None, r.text[:100])
    r = s.post(base + "/api/analyze/", json={"geometry": SQUARE, "buffer_km": 3}, headers={"X-CSRFToken": csrf, "Referer": base}, timeout=180)
    check("analysis through the website", r.status_code == 201, r.text[:200])
    if r.status_code == 201:
        pid = r.json()["id"]
        check("results page", s.get(f"{base}/dashboard/{pid}/", timeout=60).status_code == 200)
        img = s.get(f"{base}/parcels/{pid}/satellite/truecolor/", timeout=120)
        check("satellite picture", img.status_code == 200 and img.headers["Content-Type"] == "image/jpeg")
        pdf = s.get(f"{base}/parcels/{pid}/report/", timeout=180)
        check("PDF download", pdf.status_code == 200 and pdf.content[:4] == b"%PDF")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--web")
    parser.add_argument("--email")
    parser.add_argument("--password")
    parser.add_argument("--skip-services", action="store_true")
    args = parser.parse_args()
    if not args.skip_services:
        services()
    if args.web:
        website(args.web.rstrip("/"), args.email, args.password)
    print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} CHECK(S) FAILED: " + "; ".join(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
