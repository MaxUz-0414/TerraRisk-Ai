"""Records every sign-in (and failed attempt) with where it came from, for the admin dashboard.

The row is saved straight away; the country/city lookup (geocode service -> ipwho.is) runs in a background thread so
signing in never waits for it, and a failing lookup only leaves the location empty.
"""
import logging
import threading

from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db import close_old_connections
from django.dispatch import receiver

from core.netutil import client_ip, short_agent

from .models import LoginEvent

logger = logging.getLogger(__name__)


def locate(event_id, ip):
    """Fill in the location of a stored LoginEvent. Safe to call from a thread."""
    from core import services

    try:
        place = services.locate_ip(ip)
        LoginEvent.objects.filter(pk=event_id).update(
            country=(place.get("country") or "")[:80], country_code=(place.get("country_code") or "")[:2],
            city=(place.get("city") or ("Local network" if place.get("local") else ""))[:80], lat=place.get("lat"), lng=place.get("lng"))
    except Exception as exc:  # geocode service down, ipwho.is blocked, ...
        logger.info("Could not locate %s: %s", ip, exc)
    finally:
        close_old_connections()


def _record(request, user, email, success):
    if request is None:
        return
    ip = client_ip(request)
    try:
        event = LoginEvent.objects.create(user=user, email=(email or "")[:254], success=success, ip=ip or None, user_agent=short_agent(request))
    except Exception:  # a malformed IP header must never break sign-in
        logger.exception("Could not record login event")
        return
    if not ip:
        return
    if settings.LOGIN_GEO_ASYNC:
        threading.Thread(target=locate, args=(event.pk, ip), daemon=True).start()
    else:
        locate(event.pk, ip)


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    _record(request, user, user.email, True)


@receiver(user_login_failed)
def on_failed_login(sender, credentials, request=None, **kwargs):
    _record(request, None, (credentials or {}).get("username", ""), False)
