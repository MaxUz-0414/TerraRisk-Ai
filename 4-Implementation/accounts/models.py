from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Username is the email address; persona decides which advice the user gets."""

    class Persona(models.TextChoices):
        FARMER = "farmer", "Farmer"
        HOMEBUYER = "homebuyer", "Homebuyer"
        INVESTOR = "investor", "Land Investor"
        DEVELOPER = "developer", "Property Developer"
        ANALYST = "analyst", "Risk Analyst"

    persona = models.CharField(max_length=20, choices=Persona.choices, default=Persona.FARMER)
    free_searches = models.PositiveSmallIntegerField(default=5)   # remaining analysis credits
    unlimited_until = models.DateTimeField(null=True, blank=True)  # set by the Unlimited plan
    plan_key = models.CharField(max_length=20, default="free")     # last plan bought

    def __str__(self):
        return self.email or self.username

    @property
    def has_unlimited(self):
        return bool(self.unlimited_until and self.unlimited_until > timezone.now())


class Purchase(models.Model):
    """One row per plan bought. Search credits are added to User.free_searches."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="purchases")
    plan_key = models.CharField(max_length=20)
    plan_name = models.CharField(max_length=40)
    searches = models.PositiveIntegerField(default=0)  # 0 means "unlimited for 30 days"
    price = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} bought {self.plan_name}"


class LoginEvent(models.Model):
    """One sign-in (or failed attempt). The location comes from the visitor's IP address (geocode service), city level at best."""

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="login_events")
    email = models.CharField(max_length=254, blank=True)
    success = models.BooleanField(default=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    country = models.CharField(max_length=80, blank=True)
    country_code = models.CharField(max_length=2, blank=True, db_index=True)
    city = models.CharField(max_length=80, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    user_agent = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{'login' if self.success else 'failed login'} {self.email or self.user_id} from {self.city or self.country or self.ip}"

    @property
    def where(self):
        if self.country or self.city:
            return ", ".join(part for part in (self.city, self.country) if part)
        return "Local / unknown"
