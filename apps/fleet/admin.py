from django.contrib import admin

from .models import FleetDriverMembership, FleetOwnerProfile


@admin.register(FleetOwnerProfile)
class FleetOwnerProfileAdmin(admin.ModelAdmin):
    list_display = ("business_name", "owner_full_name", "city", "user")
    search_fields = ("business_name", "owner_full_name", "user__phone")


@admin.register(FleetDriverMembership)
class FleetDriverMembershipAdmin(admin.ModelAdmin):
    list_display = ("owner", "driver", "status", "vehicle_number")
    list_filter = ("status",)
