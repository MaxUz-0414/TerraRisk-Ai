"""The real Django admin, with the TerraRisk dashboard as its home page.

/admin/ keeps working exactly as Django's admin does (users, parcels, purchases... one click away), and the page you land on shows
the dashboard: users, sign-in locations, most searched places, revenue, service health and system events.
"""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path

from . import dashboard


class TerraAdminSite(admin.AdminSite):
    site_header = "TerraRisk AI"
    site_title = "TerraRisk admin"
    index_title = "Dashboard"
    index_template = "admin/terra_index.html"

    def get_urls(self):
        extra = [path("dashboard/live/", self.admin_view(self.live_view), name="terra-live")]
        return extra + super().get_urls()

    def live_view(self, request):
        return JsonResponse(dashboard.live())

    def index(self, request, extra_context=None):
        context = {"terra": dashboard.build(), "flag": dashboard.flag}
        context.update(extra_context or {})
        return super().index(request, context)
