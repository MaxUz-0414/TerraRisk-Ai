import logging
import uuid

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core import services

from .events import log_event
from .geo import area_ha
from .models import Parcel, risk_level
from .serializers import AnalyzeSerializer
from .snapshot import ensure_place, ensure_snapshot, report_data

logger = logging.getLogger(__name__)

REPORT_VERSION = 2  # bump when the PDF layout changes: older stored PDFs are rebuilt the next time they are downloaded

LAYERS = {"truecolor": "True color", "ndvi": "Vegetation", "heat": "Heat", "water": "Water"}  # same keys as the satellite service
# Which satellite picture each kind of user sees first.
LAYER_ORDER = {
    "farmer": ["truecolor", "ndvi", "water", "heat"],
    "homebuyer": ["truecolor", "heat", "ndvi", "water"],
    "investor": ["truecolor", "water", "ndvi", "heat"],
}
UNAVAILABLE_MESSAGE = "One of our services is not answering right now. Please try again in a minute."


class AnalyzeView(APIView):
    """POST /api/analyze/  {geometry, buffer_km, nickname} -> {id, redirect, free_searches, place}

    Order of events: reserve one search at billing -> ask the analysis service -> save the parcel.
    If anything after the reservation fails the search is given back (same idempotency key), so a failed analysis costs nothing.
    """

    def post(self, request):
        serializer = AnalyzeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user
        key = f"analysis:{uuid.uuid4().hex}"

        try:
            services.consume_search(user, key)
        except services.Rejected as exc:
            if exc.status == 402:
                return Response({"detail": "You have no searches left. Choose a plan to keep going.", "upgrade_url": reverse("pricing")},
                                status=status.HTTP_403_FORBIDDEN)
            log_event("error", "billing", str(exc))
            return Response({"detail": UNAVAILABLE_MESSAGE}, status=status.HTTP_502_BAD_GATEWAY)
        except services.Unavailable as exc:
            log_event("error", "billing", str(exc))
            return Response({"detail": "We could not check your searches right now, so nothing was charged. Please try again in a minute."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            result = services.analyze(data["geometry"], data["buffer_km"], user.persona)
        except services.Rejected as exc:
            services.refund_search(user, key)
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except services.Unavailable as exc:  # satellite/risk down, Earth Engine has nothing for this place, ...
            logger.error("Analysis failed: %s", exc)
            log_event("error", "analysis", str(exc))
            services.refund_search(user, key)
            return Response({"detail": "We could not read satellite data for this area right now. Try again, or draw a different area."},
                            status=status.HTTP_502_BAD_GATEWAY)

        for item in result.get("degraded", []):  # optional steps that failed (place name, written advice): the analysis still worked
            log_event("warning", item["service"], item["effect"])

        place = result.get("place") or {}
        lat, lng = result["center"]["lat"], result["center"]["lng"]
        try:
            parcel = Parcel.objects.create(
                owner=user,
                nickname=data["nickname"] or place.get("name") or f"Parcel {user.parcels.count() + 1}",
                persona=user.persona, geometry=data["geometry"], center_lat=lat, center_lng=lng,
                area_ha=area_ha(data["geometry"]), buffer_km=data["buffer_km"], risk_score=result["risk_score"],
                features=result["features"], hazards=result["hazards"], advisory=result["advisory"],
                place=(place.get("name") or "")[:160], country=(place.get("country") or "")[:80],
                country_code=(place.get("country_code") or "")[:2], data_mode=result.get("mode", ""),
                snapshot={"headline": result["headline"], "view": result["view"], "scenarios": result.get("scenarios", []),
                          "advisory_source": result.get("advisory_source", ""), "advisory_note": result.get("advisory_note", "")},
            )
        except Exception:
            logger.exception("Could not save the parcel")
            log_event("error", "analysis", "Saving the parcel failed")
            services.refund_search(user, key)
            return Response({"detail": "We could not save your analysis. Nothing was charged, please try again."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            {"id": parcel.pk, "redirect": reverse("dashboard", args=[parcel.pk]), "free_searches": user.free_searches,
             "unlimited": user.has_unlimited, "place": parcel.place_display},
            status=status.HTTP_201_CREATED,
        )


class DashboardView(LoginRequiredMixin, DetailView):
    template_name = "dashboard.html"
    context_object_name = "parcel"

    def get_queryset(self):
        return Parcel.objects.filter(owner=self.request.user)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        ensure_place(self.object)
        try:
            self.snap = ensure_snapshot(self.object)
        except (services.Unavailable, services.Rejected) as exc:
            log_event("error", "risk", str(exc))
            messages.error(request, UNAVAILABLE_MESSAGE)
            return redirect("saved")
        return self.render_to_response(self.get_context_data(object=self.object))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p, pv = self.object, self.snap["view"]
        ctx["headline"] = self.snap["headline"]
        ctx["pv"] = pv  # (not "view": Django already uses that name for the view object)
        ctx["layers"] = [{"key": key, "label": LAYERS[key], "url": reverse("satellite", args=[p.pk, key])} for key in LAYER_ORDER[pv["group"]]]
        if pv["group"] == "investor":
            ctx["scenarios"] = self.snap.get("scenarios") or []
            ctx["others"] = Parcel.objects.filter(owner=self.request.user).exclude(pk=p.pk)[:4]
        ctx["demo_data"] = p.data_mode == "demo"
        source = self.snap.get("advisory_source")
        ctx["snap_source"] = {"gemini": "AI-written", "template": "built-in advice"}.get(source, "")
        ctx["chart_data"] = {
            "score": p.risk_score, "level": risk_level(p.risk_score), "charts": pv["charts"],
            "ndvi": p.features.get("ndvi_series", {}), "lst": p.features.get("lst_series", {}), "rain": p.features.get("rain_series") or {},
        }
        return ctx


PLACEHOLDER_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000"><rect width="1600" height="1000" fill="#0f1b2d"/>'
    '<text x="800" y="490" text-anchor="middle" font-family="sans-serif" font-size="44" fill="#94a3b8">Satellite picture unavailable</text>'
    '<text x="800" y="550" text-anchor="middle" font-family="sans-serif" font-size="28" fill="#64748b">Try again in a minute</text></svg>'
)


class SatelliteLayerView(LoginRequiredMixin, View):
    """A satellite picture of the parcel, made (and cached) by the satellite service."""

    def get(self, request, pk, layer):
        if layer not in LAYERS:
            raise Http404("Unknown layer")
        parcel = get_object_or_404(Parcel, pk=pk, owner=request.user)
        try:
            data = services.satellite_layer(parcel.geometry, layer, parcel.features)
        except (services.Unavailable, services.Rejected) as exc:  # Earth Engine down, no clear images for this place, service restarting...
            logger.warning("Satellite layer failed: %s", exc)
            log_event("warning", "satellite", f"{layer}: {exc}")
            response = HttpResponse(PLACEHOLDER_SVG, content_type="image/svg+xml")
            response["Cache-Control"] = "no-store"
            return response
        response = HttpResponse(data, content_type="image/jpeg")
        response["Cache-Control"] = "private, max-age=3600"
        return response


class SavedParcelsView(LoginRequiredMixin, ListView):
    template_name = "saved.html"
    context_object_name = "parcels"

    def get_queryset(self):
        return Parcel.objects.filter(owner=self.request.user)


class ParcelDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        parcel = get_object_or_404(Parcel, pk=pk, owner=request.user)
        if parcel.report:
            parcel.report.delete(save=False)  # also removes the PDF from Azure Blob / disk
        name = parcel.display_name
        parcel.delete()
        messages.success(request, f"Deleted {name}.")
        return redirect("saved")


class ReportView(LoginRequiredMixin, View):
    """Asks the report service for the PDF once, stores it (Azure Blob when configured) and streams it to the user."""

    def get(self, request, pk):
        parcel = get_object_or_404(Parcel, pk=pk, owner=request.user)
        ensure_place(parcel)
        if not parcel.report or parcel.report_version < REPORT_VERSION:
            try:
                pdf = services.render_report(report_data(parcel))
            except (services.Unavailable, services.Rejected) as exc:
                logger.error("PDF report failed: %s", exc)
                log_event("error", "report", str(exc))
                messages.error(request, "We could not create the PDF report. Please try again.")
                return redirect("dashboard", pk=parcel.pk)
            if parcel.report:
                parcel.report.delete(save=False)
            parcel.report.save(f"{parcel.public_id}.pdf", ContentFile(pdf), save=False)
            parcel.report_size = len(pdf)
            parcel.report_version = REPORT_VERSION
            parcel.save(update_fields=["report", "report_size", "report_version"])
        return FileResponse(parcel.report.open("rb"), as_attachment=True, filename=f"TerraRisk-{parcel.public_id}.pdf", content_type="application/pdf")
