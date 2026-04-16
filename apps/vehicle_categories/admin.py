from django.contrib import admin

from .models import VehicleCategory


@admin.register(VehicleCategory)
class VehicleCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "payload_type", "base_fare", "per_km_rate", "active", "priority_order")
    list_filter = ("active", "helper_supported", "intra_city_available", "is_deleted")
    search_fields = ("name", "payload_type")
