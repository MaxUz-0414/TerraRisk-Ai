"""Who is making this request? (for the login map in the admin dashboard; never used for access control)"""
from django.conf import settings


def client_ip(request):
    for header in settings.CLIENT_IP_HEADERS:
        value = request.META.get("HTTP_" + header.upper().replace("-", "_"), "").split(",")[0].strip()
        if value:
            return value
    return request.META.get("REMOTE_ADDR", "")


def short_agent(request):
    return request.META.get("HTTP_USER_AGENT", "")[:200]
