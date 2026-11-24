from django.contrib.admin.apps import AdminConfig


class TerraAdminConfig(AdminConfig):
    """Swap Django's default admin site for ours (same admin, our dashboard on top). Listed in INSTALLED_APPS instead of django.contrib.admin."""

    default_site = "core.admin_site.TerraAdminSite"
