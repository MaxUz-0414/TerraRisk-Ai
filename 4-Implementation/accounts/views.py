from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView

from .forms import ProfileForm, SignUpForm
from .models import User
from .personas import persona_info, persona_json


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("platform")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("platform")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        """/accounts/signup/?persona=farmer pre-selects the persona (landing page cards use this)."""
        initial = super().get_initial()
        persona = self.request.GET.get("persona")
        if persona in User.Persona.values:
            initial["persona"] = persona
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        chosen = self.request.POST.get("persona") or self.get_initial().get("persona") or "farmer"
        if chosen not in User.Persona.values:
            chosen = "farmer"
        ctx["free_searches"] = settings.FREE_SEARCHES
        ctx["persona_data"] = persona_json()
        ctx["selected"] = persona_json()[chosen]
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response


class ProfileView(LoginRequiredMixin, UpdateView):
    form_class = ProfileForm
    template_name = "profile.html"
    success_url = reverse_lazy("profile")

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["purchases"] = self.request.user.purchases.all()[:10]
        ctx["persona"] = persona_info(self.request.user.persona)
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Profile updated. New analyses will use your persona.")
        return super().form_valid(form)
