"""Calls to the outside world. Everything else in the service is plain Python, so tests replace fetch_json()."""
import threading
import time

from tr_common.config import env_str

NOMINATIM = "https://nominatim.openstreetmap.org"
IP_LOOKUP = "https://ipwho.is"
_lock = threading.Lock()
_last = [0.0]


def user_agent():
    contact = env_str("GEOCODE_CONTACT") or "support@terrarisk.ai"
    return f"TerraRiskAI/1.0 (student project; {contact})"


def fetch_json(url, params=None, polite=False, timeout=6):
    """GET a JSON document. polite=True keeps to 1 request per second (Nominatim policy)."""
    import requests

    if polite:
        with _lock:
            wait = 1.05 - (time.time() - _last[0])
            if wait > 0:
                time.sleep(wait)
            _last[0] = time.time()
    response = requests.get(url, params=params, headers={"User-Agent": user_agent(), "Accept-Language": "en"}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def nominatim_search(query, limit):
    base = env_str("NOMINATIM_URL") or NOMINATIM
    return fetch_json(f"{base}/search", {"format": "jsonv2", "q": query, "limit": limit, "addressdetails": 1, "accept-language": "en"}, polite=True)


def nominatim_reverse(lat, lng):
    base = env_str("NOMINATIM_URL") or NOMINATIM
    return fetch_json(f"{base}/reverse", {"format": "jsonv2", "lat": lat, "lon": lng, "zoom": 12, "addressdetails": 1, "accept-language": "en"}, polite=True)


def ip_lookup(ip):
    return fetch_json(f"{IP_LOOKUP}/{ip}")
