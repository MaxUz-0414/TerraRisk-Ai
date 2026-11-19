import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db import connection
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.views import View
from django.views.generic import RedirectView, TemplateView

from accounts.personas import persona_cards, persona_info
from analysis.events import log_event
from analysis.models import Parcel

from . import services
from .team import team_members

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- home
class LandingView(TemplateView):
    """Visitors see the marketing page. Signed-in users see their own home: stats, recent parcels, next steps."""

    template_name = "landing.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_authenticated:
            ctx["home"] = self.home(user)
        else:
            ctx["persona_cards"] = persona_cards()
        ctx["team"] = team_members()
        return ctx

    @staticmethod
    def home(user):
        parcels = list(Parcel.objects.filter(owner=user).order_by("-created_at")[:50])
        riskiest = max(parcels, key=lambda p: p.risk_score, default=None)
        safest = min(parcels, key=lambda p: p.risk_score, default=None)
        average = round(sum(p.risk_score for p in parcels) / len(parcels)) if parcels else None
        places = sorted({p.place for p in parcels if p.place})
        return {
            "name": user.first_name or user.email.split("@")[0],
            "persona": persona_info(user.persona), "persona_label": user.get_persona_display(),
            "parcel_count": Parcel.objects.filter(owner=user).count(), "recent": parcels[:4], "last": parcels[0] if parcels else None,
            "riskiest": riskiest if riskiest and len(parcels) > 1 else None, "safest": safest if safest and len(parcels) > 1 else None,
            "average": average, "places": places[:6], "countries": len({p.country_code for p in parcels if p.country_code}),
        }


class PlatformView(LoginRequiredMixin, TemplateView):
    """The map page. All map behaviour lives in static/js/map.js."""

    template_name = "platform.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["platform_config"] = {
            "analyzeUrl": reverse("api-analyze"), "searchUrl": reverse("api-place-search"), "reverseUrl": reverse("api-place-reverse"),
            "mapConfigUrl": reverse("api-map-config"),
        }
        return ctx


# ---------------------------------------------------------------- plans and checkout
class PricingView(TemplateView):
    template_name = "pricing.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        catalogue = services.plans()
        ctx["plans"] = catalogue["plans"]
        ctx["free_searches"] = settings.FREE_SEARCHES
        ctx["unlimited_days"] = catalogue["unlimited_days"]
        return ctx


class CheckoutView(LoginRequiredMixin, TemplateView):
    """Shows the plan summary (GET) and activates it (POST, through the billing service)."""

    template_name = "checkout.html"

    def get_plan(self):
        catalogue = services.plans()
        plan = next((p for p in catalogue["plans"] if p["key"] == self.kwargs["key"]), None)
        if plan is None:
            raise Http404("Unknown plan")
        return plan, catalogue["unlimited_days"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["plan"], ctx["unlimited_days"] = self.get_plan()
        ctx["demo"] = settings.PAYMENTS_DEMO
        return ctx

    def post(self, request, *args, **kwargs):
        plan, _ = self.get_plan()
        if not settings.PAYMENTS_DEMO:
            messages.error(request, "Online payments are not connected yet. Please contact support to buy a plan.")
            return redirect("pricing")
        try:
            account, _purchase = services.checkout(request.user, plan["key"])
        except services.Rejected as exc:
            messages.error(request, str(exc))
            return redirect("pricing")
        except services.Unavailable as exc:
            log_event("error", "billing", str(exc))
            messages.error(request, "We could not reach the billing service, so nothing was charged. Please try again in a minute.")
            return redirect("pricing")
        user = request.user
        if plan["is_unlimited"]:
            messages.success(request, f"Unlimited plan active until {timezone.localtime(user.unlimited_until):%b %d, %Y}.")
        else:
            messages.success(request, f"Added {plan['searches']} searches. You now have {user.free_searches}.")
        return redirect("platform")


# ---------------------------------------------------------------- static-ish pages
def chat_context(user):
    """Everything personal the chatbot service needs (it never sees who the user is)."""
    if user is None or not user.is_authenticated:
        balance = "Sign in to see how many searches you have left."
    elif user.has_unlimited:
        balance = f"You have unlimited searches until {timezone.localtime(user.unlimited_until):%b %d, %Y}."
    else:
        n = user.free_searches
        balance = f"You have {n} search{'' if n == 1 else 'es'} left."
    return {"balance": balance, "support_email": settings.SUPPORT_EMAIL, "free_searches": settings.FREE_SEARCHES,
            "demo_data": settings.USE_FAKE_DATA, "demo_payments": settings.PAYMENTS_DEMO}


class SupportView(TemplateView):
    template_name = "support.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            ctx["faqs"] = services.faq(chat_context(self.request.user))
        except (services.Unavailable, services.Rejected):
            ctx["faqs"] = []
            ctx["faq_down"] = True
        return ctx


class TermsView(TemplateView):
    template_name = "terms.html"


class PrivacyView(TemplateView):
    template_name = "privacy.html"


# ---------------------------------------------------------------- chatbot
CHAT_LIMIT_PER_MINUTE = 20


def _link_urls(links):
    """The chatbot service names pages ("pricing", "landing#team"); only the web app knows their URLs."""
    out = []
    for link in links or []:
        name, _, anchor = link["route"].partition("#")
        try:
            out.append({"label": link["label"], "url": reverse(name) + (f"#{anchor}" if anchor else "")})
        except NoReverseMatch:
            logger.warning("Chatbot link to unknown page %r", link["route"])
    return out


class ChatView(View):
    """POST /chat/  {"message": "..."}  ->  {"reply", "links", "suggestions"}   (BFF in front of the chatbot service)"""

    def post(self, request):
        try:
            message = str(json.loads(request.body).get("message", "")).strip()[:300]
        except (ValueError, AttributeError):
            return JsonResponse({"reply": "Sorry, I could not read that message."}, status=400)
        if not message:
            return JsonResponse({"reply": "Please type a question."}, status=400)

        # simple rate limit per visitor so nobody can hammer the bot (or the optional Gemini fallback)
        key = f"chat:{request.META.get('REMOTE_ADDR', '?')}"
        cache.add(key, 0, 60)
        if cache.incr(key) > CHAT_LIMIT_PER_MINUTE:
            return JsonResponse({"reply": "You're sending messages very fast. Please wait a moment and try again."}, status=429)

        try:
            data = services.chat(message, chat_context(request.user))
        except services.Rejected as exc:
            return JsonResponse({"reply": str(exc)}, status=400)
        except services.Unavailable as exc:
            logger.warning("Chatbot unavailable: %s", exc)
            return JsonResponse({"reply": f"The assistant is taking a short break. You can still email the team at {settings.SUPPORT_EMAIL}.",
                                 "links": [{"label": "Contact support", "url": reverse("support")}], "suggestions": []}, status=503)
        if data.get("unanswered"):
            log_event("info", "chatbot", f"Unanswered question: {message[:200]}")
        return JsonResponse({"reply": data["reply"], "links": _link_urls(data.get("links")), "suggestions": data.get("suggestions", [])})


# ---------------------------------------------------------------- admin entry points
class ConsoleRedirectView(RedirectView):
    """The old /console/ page is now the dashboard on the real Django admin's home page."""

    pattern_name = "admin:index"


class HealthView(View):
    """Public liveness check for load balancers / uptime monitors."""

    def get(self, request):
        try:
            connection.ensure_connection()
            db_ok = True
        except Exception:
            db_ok = False
        return JsonResponse({"status": "ok" if db_ok else "degraded", "database": db_ok}, status=200 if db_ok else 503)
