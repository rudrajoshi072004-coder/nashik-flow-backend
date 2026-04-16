from django.contrib import admin

from .models import PricingRule


@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "vehicle_category", "base_fare", "per_km_rate", "surge_multiplier", "active")
    list_filter = ("city", "active")
    search_fields = ("name", "city", "vehicle_category__name")
