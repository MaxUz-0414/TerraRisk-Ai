from django.urls import path

from . import views

urlpatterns = [
    path("", views.LandingView.as_view(), name="landing"),
    path("platform/", views.PlatformView.as_view(), name="platform"),
    path("pricing/", views.PricingView.as_view(), name="pricing"),
    path("pricing/checkout/<slug:key>/", views.CheckoutView.as_view(), name="checkout"),
    path("support/", views.SupportView.as_view(), name="support"),
    path("terms/", views.TermsView.as_view(), name="terms"),
    path("privacy/", views.PrivacyView.as_view(), name="privacy"),
    path("chat/", views.ChatView.as_view(), name="chat"),
    path("console/", views.ConsoleRedirectView.as_view(), name="console"),
    path("healthz/", views.HealthView.as_view(), name="health"),
]
