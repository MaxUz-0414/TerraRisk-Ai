"""All numbers on the admin dashboard. Everything here comes from the database or the services: nothing is simulated.

build() is called when the admin home page opens (database only, so the page is fast even when a service is down);
live() is polled by the page every few seconds for the parts that change (service health, CPU, memory).
"""
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.db.models import Avg, Count, Sum
from django.db.models.functions import ExtractHour, ExtractWeekDay, TruncDate
from django.utils import timezone

from accounts.models import LoginEvent, Purchase, User
from analysis.models import Parcel, SearchEvent, SystemEvent, risk_level

STARTED = time.time()
PERSONA_GROUPS = {"Farmers": ("farmer",), "Homebuyers": ("homebuyer",), "Investors": ("investor", "developer", "analyst")}
PERSONA_LABELS = dict(User.Persona.choices)


# ---------------------------------------------------------------- helpers
def flag(code):
    """Country code -> flag emoji ('UZ' -> a flag). Empty for unknown codes."""
    code = (code or "").upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code)


def _days(n):
    today = timezone.now().date()
    return [today - timedelta(days=n - 1 - i) for i in range(n)]


def _label(day):
    return day.strftime("%b %d").replace(" 0", " ")


def _per_day(qs, field, days, **count_kwargs):
    """{date: count} for a queryset, over the given days."""
    rows = qs.filter(**{f"{field}__date__gte": days[0]}).annotate(d=TruncDate(field)).values("d").annotate(n=Count("id", **count_kwargs))
    got = {row["d"]: row["n"] for row in rows}
    return [got.get(day, 0) for day in days]


def _change(current, previous):
    """Percent change as an int, or None when there is nothing to compare with."""
    if not previous:
        return None
    return round((current - previous) / previous * 100)


def _uptime():
    seconds = int(time.time() - STARTED)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    return f"{days}d {hours}h" if days else f"{hours}h {rem // 60}m"


# ---------------------------------------------------------------- headline numbers
def kpis():
    now = timezone.now()
    week, two_weeks = now - timedelta(days=7), now - timedelta(days=14)
    days = _days(14)

    users_total = User.objects.count()
    new_7 = User.objects.filter(date_joined__gte=week).count()
    new_prev = User.objects.filter(date_joined__gte=two_weeks, date_joined__lt=week).count()
    active_7 = LoginEvent.objects.filter(success=True, created_at__gte=week).values("user").distinct().count()
    active_prev = LoginEvent.objects.filter(success=True, created_at__gte=two_weeks, created_at__lt=week).values("user").distinct().count()
    an_7 = Parcel.objects.filter(created_at__gte=week).count()
    an_prev = Parcel.objects.filter(created_at__gte=two_weeks, created_at__lt=week).count()
    avg = Parcel.objects.aggregate(a=Avg("risk_score"))["a"]
    paid = Purchase.objects.aggregate(total=Sum("price"), n=Count("id"))
    paid_7 = Purchase.objects.filter(created_at__gte=week).aggregate(total=Sum("price"))["total"] or 0
    failed_7 = LoginEvent.objects.filter(success=False, created_at__gte=week).count()
    errors_7 = SystemEvent.objects.filter(level="error", created_at__gte=week).count()
    return [
        {"key": "users", "label": "Users", "value": users_total, "sub": f"{new_7} joined in 7 days", "change": _change(new_7, new_prev),
         "spark": _per_day(User.objects.all(), "date_joined", days)},
        {"key": "active", "label": "Active users (7 days)", "value": active_7, "sub": "signed in at least once", "change": _change(active_7, active_prev),
         "spark": _per_day(LoginEvent.objects.filter(success=True), "created_at", days)},
        {"key": "analyses", "label": "Analyses (7 days)", "value": an_7, "sub": f"{Parcel.objects.count()} saved in total", "change": _change(an_7, an_prev),
         "spark": _per_day(Parcel.objects.all(), "created_at", days)},
        {"key": "risk", "label": "Average risk score", "value": round(avg) if avg is not None else "-", "suffix": "%" if avg is not None else "",
         "sub": "across all parcels", "change": None, "spark": None},
        {"key": "revenue", "label": "Revenue", "value": f"${paid['total'] or 0:,.2f}", "sub": f"${paid_7:,.2f} in the last 7 days · {paid['n']} purchases",
         "change": None, "spark": None},
        {"key": "security", "label": "Failed sign-ins (7 days)", "value": failed_7, "sub": "wrong password or unknown email", "change": None,
         "spark": _per_day(LoginEvent.objects.filter(success=False), "created_at", days), "tone": "warn" if failed_7 >= 10 else ""},
        {"key": "errors", "label": "System errors (7 days)", "value": errors_7, "sub": "from the services and the pipeline", "change": None,
         "spark": _per_day(SystemEvent.objects.filter(level="error"), "created_at", days), "tone": "bad" if errors_7 else ""},
    ]


# ---------------------------------------------------------------- time series
def growth(days_count=30):
    days = _days(days_count)
    groups = {}
    for name, personas in PERSONA_GROUPS.items():
        groups[name] = _per_day(User.objects.filter(persona__in=personas), "date_joined", days)
    return {"labels": [_label(d) for d in days], "series": [{"name": n, "values": v} for n, v in groups.items()]}


def analyses_by_day(days_count=30):
    days = _days(days_count)
    series = [{"name": n, "values": _per_day(Parcel.objects.filter(persona__in=p), "created_at", days)} for n, p in PERSONA_GROUPS.items()]
    return {"labels": [_label(d) for d in days], "series": series}


def logins_by_day(days_count=30):
    days = _days(days_count)
    return {"labels": [_label(d) for d in days], "series": [
        {"name": "Successful", "values": _per_day(LoginEvent.objects.filter(success=True), "created_at", days)},
        {"name": "Failed", "values": _per_day(LoginEvent.objects.filter(success=False), "created_at", days)},
    ]}


def activity_heatmap(days_count=28):
    """Sign-ins by weekday (Mon..Sun) and hour of day (UTC), so you can see when people use the site."""
    since = timezone.now() - timedelta(days=days_count)
    rows = (LoginEvent.objects.filter(success=True, created_at__gte=since).annotate(wd=ExtractWeekDay("created_at"), h=ExtractHour("created_at"))
            .values("wd", "h").annotate(n=Count("id")))
    grid = [[0] * 24 for _ in range(7)]
    for row in rows:
        grid[(row["wd"] + 5) % 7][row["h"]] = row["n"]  # Django: Sunday=1 ... Saturday=7  ->  Monday=0 ... Sunday=6
    return {"days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "grid": grid}


def risk_mix():
    counts = defaultdict(int)
    for score in Parcel.objects.values_list("risk_score", flat=True):
        counts[risk_level(score)] += 1
    return [{"key": k, "label": {"low": "Low risk", "medium": "Moderate risk", "high": "High risk"}[k], "value": counts[k]} for k in ("low", "medium", "high")]


def _shares(rows, key="value"):
    """Add a 'share' (0-100, relative to the biggest row, so the longest bar is full width) to every row."""
    top = max((r[key] for r in rows), default=0) or 1
    for r in rows:
        r["share"] = round(r[key] / top * 100)
    return rows


def persona_mix():
    rows = User.objects.values("persona").annotate(n=Count("id")).order_by("-n")
    return _shares([{"label": PERSONA_LABELS.get(r["persona"], r["persona"]), "value": r["n"]} for r in rows])


# ---------------------------------------------------------------- where users come from, what they look at
def login_geo():
    """Where sign-ins come from: country ranking, city markers and the latest sign-ins."""
    base = LoginEvent.objects.filter(success=True)
    countries = [
        {"code": r["country_code"], "name": r["country"] or r["country_code"], "flag": flag(r["country_code"]), "logins": r["logins"], "users": r["users"]}
        for r in base.exclude(country_code="").values("country_code", "country").annotate(logins=Count("id"), users=Count("user", distinct=True)).order_by("-logins")[:12]
    ]
    _shares(countries, "logins")
    cities = [
        {"city": r["city"], "country": r["country"], "lat": r["lat"], "lng": r["lng"], "logins": r["n"], "users": r["u"]}
        for r in base.exclude(lat=None).exclude(lng=None).values("city", "country", "lat", "lng").annotate(n=Count("id"), u=Count("user", distinct=True)).order_by("-n")[:150]
    ]
    unlocated = base.filter(country_code="").count()
    recent = [
        {"who": (e.user.first_name if e.user_id else "") or e.email or "?", "email": e.email, "where": e.where, "flag": flag(e.country_code), "success": e.success,
         "time": timezone.localtime(e.created_at).strftime("%b %d, %H:%M"), "ip": e.ip or "", "device": _device(e.user_agent)}
        for e in LoginEvent.objects.select_related("user").order_by("-created_at")[:14]
    ]
    return {"countries": countries, "cities": cities, "unlocated": unlocated, "recent": recent}


def _device(agent):
    agent = (agent or "").lower()
    system = "iPhone" if "iphone" in agent else "Android" if "android" in agent else "Mac" if "mac os" in agent else "Windows" if "windows" in agent else "Linux" if "linux" in agent else ""
    browser = "Edge" if "edg/" in agent else "Chrome" if "chrome" in agent else "Safari" if "safari" in agent else "Firefox" if "firefox" in agent else ""
    return " · ".join(part for part in (browser, system) if part) or "Unknown"


def places():
    """Which places get analysed and searched most."""
    analysed = [
        {"name": r["place"], "country": r["country"], "flag": flag(r["country_code"]), "count": r["n"], "avg": round(r["avg"] or 0)}
        for r in Parcel.objects.exclude(place="").values("place", "country", "country_code").annotate(n=Count("id"), avg=Avg("risk_score")).order_by("-n", "place")[:10]
    ]
    countries = [
        {"name": r["country"] or r["country_code"], "flag": flag(r["country_code"]), "count": r["n"]}
        for r in Parcel.objects.exclude(country_code="").values("country_code", "country").annotate(n=Count("id")).order_by("-n")[:8]
    ]
    searched = [
        {"name": r["place"] or r["query"], "flag": flag(r["country_code"]), "count": r["n"], "users": r["u"]}
        for r in SearchEvent.objects.values("place", "query", "country_code").annotate(n=Count("id"), u=Count("user", distinct=True)).order_by("-n")[:10]
    ]
    _shares(countries, "count")
    _shares(analysed, "count")
    _shares(searched, "count")
    points = [{"lat": r["center_lat"], "lng": r["center_lng"], "score": r["risk_score"], "level": risk_level(r["risk_score"]), "name": r["place"] or r["nickname"]}
              for r in Parcel.objects.values("center_lat", "center_lng", "risk_score", "place", "nickname")[:600]]
    return {"analysed": analysed, "countries": countries, "searched": searched, "points": points,
            "unnamed": Parcel.objects.filter(place="").count(), "searches_total": SearchEvent.objects.count()}


# ---------------------------------------------------------------- money, storage, events
def revenue():
    rows = Purchase.objects.values("plan_name").annotate(total=Sum("price"), n=Count("id")).order_by("-total")
    return _shares([{"label": r["plan_name"], "value": float(r["total"] or 0), "count": r["n"]} for r in rows])


def storage():
    agg = Parcel.objects.exclude(report="").aggregate(n=Count("id"), size=Sum("report_size"))
    return {"reports": agg["n"] or 0, "mb": round((agg["size"] or 0) / 1024**2, 2),
            "azure": "azure" in settings.STORAGES["default"]["BACKEND"], "analyses_today": Parcel.objects.filter(created_at__date=timezone.now().date()).count()}


def events(days_count=14):
    days = _days(days_count)
    chart = {"labels": [_label(d) for d in days], "series": [
        {"name": "Errors", "values": _per_day(SystemEvent.objects.filter(level="error"), "created_at", days)},
        {"name": "Warnings", "values": _per_day(SystemEvent.objects.filter(level="warning"), "created_at", days)},
    ]}
    latest = [{"level": e.level, "source": e.source, "message": e.message, "time": timezone.localtime(e.created_at).strftime("%b %d, %H:%M")}
              for e in SystemEvent.objects.all()[:10]]
    return {"chart": chart, "latest": latest}


# ---------------------------------------------------------------- the whole page
def build():
    from django.urls import reverse

    return {
        "kpis": kpis(), "growth": growth(), "analyses": analyses_by_day(), "logins": logins_by_day(), "heatmap": activity_heatmap(),
        "risk_mix": risk_mix(), "personas": persona_mix(), "geo": login_geo(), "places": places(), "revenue": revenue(),
        "storage": storage(), "events": events(), "liveUrl": reverse("admin:terra-live"),
        "mode": {"data": "Demo data" if settings.USE_FAKE_DATA else "Live satellite data", "services": settings.SERVICES_MODE,
                 "advice": "Gemini" if settings.GEMINI_API_KEY else "Templates", "payments": "Demo (no real charges)" if settings.PAYMENTS_DEMO else "Live"},
    }


# ---------------------------------------------------------------- live (polled)
def system_metrics():
    """CPU and memory of the machine running Django."""
    data = {"cpu": None, "mem_used_gb": None, "mem_total_gb": None, "mem_pct": None, "uptime": _uptime()}
    try:
        import psutil

        data["cpu"] = round(psutil.cpu_percent(interval=0.2), 1)
        vm = psutil.virtual_memory()
        data.update(mem_used_gb=round(vm.used / 1024**3, 2), mem_total_gb=round(vm.total / 1024**3, 2), mem_pct=round(vm.percent, 1))
    except Exception:
        pass
    return data


def live():
    from . import services

    try:
        connection.ensure_connection()
        db = {"ok": True, "vendor": connection.vendor}
    except Exception as exc:
        db = {"ok": False, "vendor": str(exc)[:80]}
    with ThreadPoolExecutor(max_workers=8) as pool:
        names = ("analysis", "satellite", "risk", "advisory", "report", "billing", "geocode", "chatbot")
        from tr_common import registry

        health = list(pool.map(registry.health, names))
    return {"system": system_metrics(), "database": db, "services": health, "mode": services.mode()}
