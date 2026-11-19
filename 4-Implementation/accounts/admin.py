from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import LoginEvent, Purchase, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("TerraRisk", {"fields": ("persona", "free_searches", "unlimited_until", "plan_key")}),
    )
    list_display = ("email", "first_name", "persona", "free_searches", "plan_key", "is_staff")
    list_filter = DjangoUserAdmin.list_filter + ("persona", "plan_key")


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "plan_name", "searches", "price")
    list_filter = ("plan_key",)


class ReadOnlyLog(admin.ModelAdmin):
    """Logs are written by the website itself; nobody should add or edit rows by hand (deleting old rows is still allowed)."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LoginEvent)
class LoginEventAdmin(ReadOnlyLog):
    list_display = ("created_at", "email", "success", "where", "ip")
    list_filter = ("success", "country")
    search_fields = ("email", "ip", "city", "country")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)
