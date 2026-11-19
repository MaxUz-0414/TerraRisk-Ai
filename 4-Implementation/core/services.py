"""The web app's door to the microservices.

Views never build service URLs, never import service code and never see raw HTTP errors: they call a function here and get
either data or one of two exceptions:

    Unavailable(message)   the service could not be reached or failed: show `message` to the user (or degrade)
    Rejected(status, msg)  the service understood the request and said no (bad input, no searches left, ...)

Billing note: the billing service is the source of truth for search credits. User.free_searches / unlimited_until / plan_key in
the web database are a cached copy (read model) that this module refreshes after every billing call, so pages render
without a network call.
"""
import logging
from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from tr_common import registry
from tr_common.client import ServiceError, ServiceUnavailable

logger = logging.getLogger("tr.web.services")

__all__ = ["Unavailable", "Rejected"]


class Unavailable(Exception):
    def __init__(self, service, message):
        self.service = service
        super().__init__(message)


class Rejected(Exception):
    def __init__(self, service, status, message, payload=None):
        self.service, self.status, self.payload = service, status, payload or {}
        super().__init__(message)


def _call(service, method, path, *, json=None, params=None, timeout=None):
    """One service call with the error translation described above. Returns the Reply."""
    try:
        return registry.client(service).request(method, path, json=json, params=params, timeout=timeout)
    except ServiceUnavailable as exc:
        raise Unavailable(service, str(exc)) from exc
    except ServiceError as exc:
        if exc.status >= 500:
            raise Unavailable(service, str(exc)) from exc
        message = exc.payload.get("message") or exc.payload.get("error") or str(exc)
        raise Rejected(service, exc.status, message, exc.payload) from exc


# ---------------------------------------------------------------- billing
def _parse_dt(text):
    if not text:
        return None
    value = datetime.fromisoformat(text)
    return value if timezone.is_aware(value) else timezone.make_aware(value)


def mirror_account(user, account):
    """Copy the billing account onto the web user (cached read model). Returns the user."""
    until = _parse_dt(account.get("unlimited_until"))
    fields = []
    for name, value in (("free_searches", account["free_searches"]), ("unlimited_until", until), ("plan_key", account.get("plan_key", "free"))):
        if getattr(user, name) != value:
            setattr(user, name, value)
            fields.append(name)
    if fields:
        user.save(update_fields=fields)
    return user


def billing_account(user):
    """Make sure the user has a billing account (created on first sight with the balance they already had), then mirror it."""
    initial = {"free_searches": user.free_searches, "unlimited_until": user.unlimited_until.isoformat() if user.unlimited_until else None,
               "plan_key": user.plan_key}
    account = _call("billing", "PUT", f"/v1/accounts/{user.pk}", json={"email": user.email, "initial": initial}).json()
    mirror_account(user, account)
    return account


def consume_search(user, key):
    """Use one search (idempotent per `key`). Raises Rejected(402) when none are left."""
    billing_account(user)
    account = _call("billing", "POST", f"/v1/accounts/{user.pk}/consume", json={"key": key}).json()
    mirror_account(user, account)
    return account


def refund_search(user, key):
    """Give the search back after a failed analysis. Never raises: a failed refund is logged and fixed by support."""
    try:
        account = _call("billing", "POST", f"/v1/accounts/{user.pk}/refund", json={"key": key}).json()
        mirror_account(user, account)
    except (Unavailable, Rejected):
        logger.exception("Could not refund search %s for user %s", key, user.pk)


def checkout(user, plan_key):
    """Buy a plan. Returns (account, purchase_dict). Raises Rejected(501) when real payments are not connected."""
    from accounts.models import Purchase

    billing_account(user)
    account = _call("billing", "POST", f"/v1/accounts/{user.pk}/checkout", json={"plan_key": plan_key}).json()
    mirror_account(user, account)
    purchase = account["purchases"][0]
    Purchase.objects.create(user=user, plan_key=purchase["plan_key"], plan_name=purchase["plan_name"], searches=purchase["searches"],
                            price=purchase["price"])
    return account, purchase


def plans():
    """Plans for the pricing page: from the billing service, or the built-in copy (accounts/plans.py) when it is down."""
    from accounts.plans import PLANS, UNLIMITED_DAYS

    cached = cache.get("billing:plans")
    if cached:
        return cached
    try:
        body = _call("billing", "GET", "/v1/plans", timeout=3).json()
        result = {"plans": body["plans"], "unlimited_days": body.get("unlimited_days", UNLIMITED_DAYS), "live": True}
        cache.set("billing:plans", result, 60)
        return result
    except (Unavailable, Rejected):
        return {"plans": [{"key": p.key, "name": p.name, "searches": p.searches, "price": str(p.price), "tagline": p.tagline, "popular": p.popular,
                           "per_search": str(p.per_search) if p.per_search else None, "is_unlimited": p.is_unlimited} for p in PLANS],
                "unlimited_days": UNLIMITED_DAYS, "live": False}


def billing_stats():
    return _call("billing", "GET", "/v1/stats", timeout=4).json()


# ---------------------------------------------------------------- analysis / risk / satellite / report
def analyze(geometry, buffer_km, persona):
    return _call("analysis", "POST", "/v1/analyze", json={"geometry": geometry, "buffer_km": buffer_km, "persona": persona}).json()


def persona_view(features, score, persona):
    return _call("risk", "POST", "/v1/view", json={"features": features, "score": score, "persona": persona}, timeout=8).json()


def satellite_layer(geometry, layer, features=None):
    """JPEG bytes of one satellite picture."""
    return _call("satellite", "POST", f"/v1/layers/{layer}", json={"geometry": geometry, "features": features or {}}).content


def render_report(data):
    """PDF bytes of the certificate."""
    return _call("report", "POST", "/v1/reports", json=data).content


# ---------------------------------------------------------------- geocoding
def search_places(query, limit=6):
    return _call("geocode", "GET", "/v1/search", params={"q": query, "limit": limit}, timeout=8).json()["results"]


def reverse_place(lat, lng):
    return _call("geocode", "GET", "/v1/reverse", params={"lat": lat, "lng": lng}, timeout=6).json()


def locate_ip(ip):
    return _call("geocode", "GET", f"/v1/ip/{ip}", timeout=6).json()


# ---------------------------------------------------------------- chatbot
def chat(message, context):
    return _call("chatbot", "POST", "/v1/chat", json={"message": message, "context": context}, timeout=15).json()


def faq(context):
    return _call("chatbot", "POST", "/v1/faq", json={"context": context}, timeout=6).json()["faq"]


# ---------------------------------------------------------------- health (admin dashboard)
def health_report():
    """One row per service for the admin dashboard; never raises."""
    return [registry.health(name) for name in ("analysis", "satellite", "risk", "advisory", "report", "billing", "geocode", "chatbot")]


def mode():
    return settings.SERVICES_MODE
