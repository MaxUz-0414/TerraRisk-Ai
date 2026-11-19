from django.conf import settings
from django.db import models

from accounts.models import User



def risk_level(score):
    """0-100 score -> 'low' / 'medium' / 'high' (same thresholds as the risk service)."""
    return "low" if score < 40 else "medium" if score < 65 else "high"


class Parcel(models.Model):
    """One saved analysis: the drawn shape, the satellite features, the score and the advice."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="parcels")
    nickname = models.CharField(max_length=80)
    persona = models.CharField(max_length=20, choices=User.Persona.choices)
    geometry = models.JSONField()            # GeoJSON Point or Polygon
    center_lat = models.FloatField()
    center_lng = models.FloatField()
    area_ha = models.FloatField(null=True, blank=True)
    buffer_km = models.FloatField(default=5)
    risk_score = models.PositiveSmallIntegerField()
    place = models.CharField(max_length=160, blank=True)        # "Yunusabad, Tashkent" (from the geocode service; may be empty)
    country = models.CharField(max_length=80, blank=True)
    country_code = models.CharField(max_length=2, blank=True, db_index=True)
    data_mode = models.CharField(max_length=10, blank=True)     # "demo" or "live": what kind of data this analysis used
    features = models.JSONField(default=dict)   # satellite measurements, see services/satellite/tr_satellite/gee.py
    snapshot = models.JSONField(default=dict, blank=True)  # headline + persona view + scenarios exactly as the user first saw them
    hazards = models.JSONField(default=list)    # cards on the dashboard
    advisory = models.JSONField(default=list)   # [{"label": ..., "text": ...}]
    report = models.FileField(upload_to="reports/%Y/%m/", blank=True)  # PDF; goes to Azure Blob when configured
    report_size = models.PositiveIntegerField(default=0)
    report_version = models.PositiveSmallIntegerField(default=0)  # which PDF layout `report` was made with; older ones are rebuilt on download
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.nickname} ({self.risk_score}%)"

    @property
    def display_name(self):
        """The nickname; else the place name; else coordinates (also when the nickname is empty or repeated characters like "IIIII")."""
        name = (self.nickname or "").strip()
        if len(set(name.lower())) < 2:
            return self.place or f"Parcel at {self.center_lat:.3f}, {self.center_lng:.3f}"
        return name

    @property
    def place_display(self):
        """'Yunusabad, Tashkent, Uzbekistan' when known."""
        parts = [part for part in (self.place, self.country) if part]
        return ", ".join(dict.fromkeys(parts))

    @property
    def public_id(self):
        return f"TR-{self.pk:05d}"

    @property
    def risk_level(self):
        return risk_level(self.risk_score)

    @property
    def coords_display(self):
        ns = "N" if self.center_lat >= 0 else "S"
        ew = "E" if self.center_lng >= 0 else "W"
        return f"{abs(self.center_lat):.4f}°{ns}, {abs(self.center_lng):.4f}°{ew}"


class SystemEvent(models.Model):
    """Errors and warnings from the pipeline (GEE, Gemini, PDF...). Shown in the admin console."""

    LEVELS = [("error", "Error"), ("warning", "Warning"), ("info", "Info")]

    level = models.CharField(max_length=10, choices=LEVELS, default="error")
    source = models.CharField(max_length=40)
    message = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.level}] {self.source}: {self.message[:60]}"


class SearchEvent(models.Model):
    """A place somebody searched for in the map's search box (only when they pressed Enter / Go). Feeds "most searched places"."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="search_events")
    query = models.CharField(max_length=120)
    place = models.CharField(max_length=160, blank=True)       # what the best match was called
    country = models.CharField(max_length=80, blank=True)
    country_code = models.CharField(max_length=2, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.query} -> {self.place or 'no match'}"
