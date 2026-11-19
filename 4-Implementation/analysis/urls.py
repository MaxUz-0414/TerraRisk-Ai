from django.urls import path

from .places import MapConfigView, PlaceReverseView, PlaceSearchView
from .views import AnalyzeView, DashboardView, ParcelDeleteView, ReportView, SatelliteLayerView, SavedParcelsView

urlpatterns = [
    path("api/analyze/", AnalyzeView.as_view(), name="api-analyze"),
    path("api/places/search/", PlaceSearchView.as_view(), name="api-place-search"),
    path("api/places/reverse/", PlaceReverseView.as_view(), name="api-place-reverse"),
    path("api/map/config/", MapConfigView.as_view(), name="api-map-config"),
    path("dashboard/<int:pk>/", DashboardView.as_view(), name="dashboard"),
    path("parcels/<int:pk>/satellite/<slug:layer>/", SatelliteLayerView.as_view(), name="satellite"),
    path("parcels/", SavedParcelsView.as_view(), name="saved"),
    path("parcels/<int:pk>/report/", ReportView.as_view(), name="report"),
    path("parcels/<int:pk>/delete/", ParcelDeleteView.as_view(), name="parcel-delete"),
]
