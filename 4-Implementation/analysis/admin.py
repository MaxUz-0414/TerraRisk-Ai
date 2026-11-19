from django.contrib import admin

from accounts.admin import ReadOnlyLog

from .models import Parcel, SearchEvent, SystemEvent


@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = ("public_id", "nickname", "place", "country", "owner", "risk_score", "created_at")
    list_filter = ("persona", "country", "data_mode")
    search_fields = ("nickname", "place", "country", "owner__email")
    readonly_fields = ("created_at",)


@admin.register(SystemEvent)
class SystemEventAdmin(ReadOnlyLog):
    list_display = ("created_at", "level", "source", "message")
    list_filter = ("level", "source")


@admin.register(SearchEvent)
class SearchEventAdmin(ReadOnlyLog):
    list_display = ("created_at", "query", "place", "country", "user")
    list_filter = ("country",)
    search_fields = ("query", "place")
    date_hierarchy = "created_at"
