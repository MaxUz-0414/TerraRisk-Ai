from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

from .models import User

INPUT_CLASSES = (
    "w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-slate-900 "
    "placeholder-slate-400 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
)


class StyledFormMixin:
    def style_fields(self):
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASSES


class SignUpForm(StyledFormMixin, forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["first_name", "email", "persona"]
        labels = {"first_name": "Full name", "email": "Work email", "persona": "Select your persona"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["email"].required = True
        self.style_fields()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("An account with this email already exists. Sign in instead.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "Passwords do not match.")
            else:
                try:
                    validate_password(p1)
                except forms.ValidationError as exc:
                    self.add_error("password1", exc)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email
        user.free_searches = settings.FREE_SEARCHES
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class EmailAuthenticationForm(StyledFormMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email"
        self.style_fields()

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


DARK_INPUT_CLASSES = (
    "w-full rounded-lg border border-white/15 bg-white/5 px-3 py-2.5 text-white placeholder-slate-400 "
    "[color-scheme:dark] focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-400/30"
)


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "persona"]
        labels = {"first_name": "Full name", "persona": "Your persona"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        for field in self.fields.values():
            field.widget.attrs["class"] = DARK_INPUT_CLASSES
