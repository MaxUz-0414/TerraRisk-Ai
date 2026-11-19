"""TerraRisk AI settings. Everything configurable comes from environment variables (.env)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# The shared service library (tr_common). Services themselves run as separate containers (SERVICES_MODE=http);
# with SERVICES_MODE=inprocess they are imported from services/<name> on demand (laptops and unit tests).
sys.path.insert(0, str(BASE_DIR / "services" / "common"))
os.environ.setdefault("SERVICES_MODE", "inprocess")
os.environ.setdefault("INTERNAL_TOKEN", "dev-internal-token")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes")


def env_list(name, default=""):
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "core.admin_apps.TerraAdminConfig",  # Django admin with the TerraRisk dashboard as its home page (replaces django.contrib.admin)
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
    "analysis",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
            ],
        },
    },
]

# Database: SQLite locally, PostgreSQL when POSTGRES_DB is set (Docker/Azure).
if os.environ.get("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ.get("POSTGRES_USER", "terrarisk"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "db"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.environ.get("SQLITE_PATH") or BASE_DIR / "db.sqlite3"}}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "landing"
LOGOUT_REDIRECT_URL = "landing"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# Azure Blob Storage for reports (Member C): set AZURE_* in .env and it switches on.
if os.environ.get("AZURE_ACCOUNT_NAME"):
    STORAGES["default"] = {
        "BACKEND": "storages.backends.azure_storage.AzureStorage",
        "OPTIONS": {
            "account_name": os.environ["AZURE_ACCOUNT_NAME"],
            "account_key": os.environ.get("AZURE_ACCOUNT_KEY", ""),
            "azure_container": os.environ.get("AZURE_CONTAINER", "reports"),
        },
    }

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

# ---- TerraRisk settings -------------------------------------------------
# Satellite/AI work happens in the microservices (see ARCHITECTURE.md). The web app only needs these for display:
USE_FAKE_DATA = env_bool("USE_FAKE_DATA", True)          # shown in the admin dashboard / chatbot; the satellite service reads the same variable
FREE_SEARCHES = int(os.environ.get("FREE_SEARCHES", "5"))  # searches a new account starts with (billing service uses it for accounts it creates)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")      # only to show "Gemini / templates" in the admin dashboard
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

# ---- Microservices ----
SERVICES_MODE = os.environ["SERVICES_MODE"]  # "http" (Docker/production) or "inprocess" (laptop, tests)

# ---- Map ----
# Optional Google Maps tiles (Map Tiles API). Without a key the map uses Esri satellite + Esri place-name labels.
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
# Header that carries the visitor's real IP (used for the "where do users log in from" chart). Cloudflare sends CF-Connecting-IP.
CLIENT_IP_HEADERS = env_list("CLIENT_IP_HEADERS", "CF-Connecting-IP,X-Real-IP")
# Look up the country of a login in the background so signing in never waits for it. Tests switch this off.
LOGIN_GEO_ASYNC = env_bool("LOGIN_GEO_ASYNC", "test" not in sys.argv)

# ---- HTTPS (set USE_HTTPS=True when a proxy such as Cloudflare terminates TLS) ----
USE_HTTPS = env_bool("USE_HTTPS", False)
if USE_HTTPS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600

# ---- Logging: everything to the console, so `docker compose logs web` shows errors ----
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# ---- Contact details shown in the footer, support page and chatbot (set real ones in .env) ----
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@terrarisk.ai")
INSTAGRAM_URL = os.environ.get("INSTAGRAM_URL", "https://www.instagram.com/")
TWITTER_URL = os.environ.get("TWITTER_URL", "https://x.com/")
GITHUB_URL = os.environ.get("GITHUB_URL", "https://github.com/")

# ---- Billing: True = checkout only simulates payment (no card is charged) ----
PAYMENTS_DEMO = env_bool("PAYMENTS_DEMO", True)

# ---- Styling: False = use the compiled static/css/tailwind.css (fast). True = Tailwind CDN (no build step, for development) ----
TAILWIND_CDN = env_bool("TAILWIND_CDN", False)
