from django.contrib import admin

from .models import DriverOffer, DriverOfferUsage, Incentive


@admin.register(Incentive)
class IncentiveAdmin(admin.ModelAdmin):
    list_display = ("driver", "name", "amount", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("driver__user__phone", "name")


@admin.register(DriverOffer)
class DriverOfferAdmin(admin.ModelAdmin):
    list_display = ("title", "rides_count", "commission_rate", "valid_days", "start_date", "end_date", "active", "priority", "created_at")
    list_filter = ("active", "start_date", "end_date")
    search_fields = ("title", "description")


@admin.register(DriverOfferUsage)
class DriverOfferUsageAdmin(admin.ModelAdmin):
    list_display = ("offer", "driver", "ride_number", "saved_commission_amount", "created_at")
    list_filter = ("offer", "created_at")
    search_fields = ("driver__user__phone", "offer__title")
