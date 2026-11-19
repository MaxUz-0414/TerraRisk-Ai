"""Map helpers for the platform page: place search, "what is this place called", and the optional Google tile session.

These are thin BFF endpoints: the browser talks to Django (login + rate limit + search log), Django talks to the geocode service.
"""
import logging

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

from core import services

from .models import SearchEvent

logger = logging.getLogger(__name__)
LIMIT_PER_MINUTE = 40


def _limited(request):
    key = f"places:{request.user.pk}"
    cache.add(key, 0, 60)
    return cache.incr(key) > LIMIT_PER_MINUTE


class PlaceSearchView(LoginRequiredMixin, View):
    """GET /api/places/search/?q=tashkent[&commit=1] -> {results: [{short, display, lat, lng, bbox, country, country_code}]}

    `commit=1` means the user pressed Enter / Go (not just typed): that search is logged for the admin "most searched places" chart.
    """

    def get(self, request):
        query = request.GET.get("q", "").strip()
        if len(query) < 2:
            return JsonResponse({"results": []})
        if _limited(request):
            return JsonResponse({"results": [], "detail": "Too many searches. Wait a moment."}, status=429)
        try:
            results = services.search_places(query[:120])
        except (services.Unavailable, services.Rejected) as exc:
            logger.warning("Place search failed: %s", exc)
            return JsonResponse({"results": [], "detail": "Place search is not available right now. Pan the map manually."}, status=503)
        if request.GET.get("commit") == "1":
            top = results[0] if results else {}
            SearchEvent.objects.create(
                user=request.user, query=query[:120], place=(top.get("short") or "")[:160], country=(top.get("country") or "")[:80],
                country_code=(top.get("country_code") or "")[:2], lat=top.get("lat"), lng=top.get("lng"))
        return JsonResponse({"results": results})


class PlaceReverseView(LoginRequiredMixin, View):
    """GET /api/places/reverse/?lat=..&lng=.. -> {name, region, country, country_code}  (what is this spot called?)"""

    def get(self, request):
        try:
            lat, lng = float(request.GET["lat"]), float(request.GET["lng"])
        except (KeyError, ValueError):
            return JsonResponse({"detail": "lat and lng are required."}, status=400)
        if _limited(request):
            return JsonResponse({"detail": "Too many requests."}, status=429)
        try:
            return JsonResponse(services.reverse_place(lat, lng))
        except services.Rejected as exc:
            return JsonResponse({"detail": str(exc)}, status=400)
        except services.Unavailable:
            return JsonResponse({"name": "", "country": "", "country_code": ""}, status=200)  # a missing name is not an error for the map


class MapConfigView(LoginRequiredMixin, View):
    """GET /api/map/config/ -> {google: {tiles, attribution} | null}

    With GOOGLE_MAPS_API_KEY set we open a Google Map Tiles API session (hybrid = satellite + labels) and hand the browser the
    tile URL. Without a key, or if Google refuses, `google` is null and the map uses the free Esri satellite + Esri labels.
    """

    def get(self, request):
        return JsonResponse({"google": google_tiles()})


def google_tiles():
    key = settings.GOOGLE_MAPS_API_KEY
    if not key:
        return None
    cached = cache.get("google:tiles")
    if cached:
        return cached
    try:
        import requests

        reply = requests.post("https://tile.googleapis.com/v1/createSession", params={"key": key}, timeout=6,
                              json={"mapType": "satellite", "language": "en-US", "region": "US", "layerTypes": ["layerRoadmap"]})
        reply.raise_for_status()
        session = reply.json()["session"]
    except Exception as exc:
        logger.warning("Google Map Tiles session failed: %s", exc)
        cache.set("google:tiles", None, 60)
        return None
    result = {"tiles": f"https://tile.googleapis.com/v1/2dtiles/{{z}}/{{x}}/{{y}}?session={session}&key={key}", "attribution": "Map data &copy; Google"}
    cache.set("google:tiles", result, 6 * 3600)
    return result
