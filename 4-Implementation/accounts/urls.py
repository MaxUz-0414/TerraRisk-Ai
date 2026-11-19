from django.contrib.auth import views as auth_views
from django.urls import path

from .forms import EmailAuthenticationForm
from .views import ProfileView, SignUpView

urlpatterns = [
    path("signup/", SignUpView.as_view(), name="signup"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=EmailAuthenticationForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
