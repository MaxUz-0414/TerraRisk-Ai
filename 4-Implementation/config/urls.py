from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),  # the real Django admin; its home page is the TerraRisk dashboard (core/admin_site.py)
    path("accounts/", include("accounts.urls")),
    path("", include("core.urls")),
    path("", include("analysis.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
