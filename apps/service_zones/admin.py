from django.contrib import admin

from .models import ServiceZone


@admin.register(ServiceZone)
class ServiceZoneAdmin(admin.ModelAdmin):
    list_display = ("city_name", "zone_name", "active", "dispatch_radius_km", "created_at")
    list_filter = ("city_name", "active", "is_deleted")
    search_fields = ("city_name", "zone_name")
