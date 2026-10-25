from django.contrib import admin

from .models import FleetDriverMembership, FleetOwnerDocument, FleetOwnerProfile


@admin.register(FleetOwnerProfile)
class FleetOwnerProfileAdmin(admin.ModelAdmin):
    list_display = ("business_name", "owner_full_name", "city", "user", "kyc_status", "kyc_submitted_at")
    list_filter = ("kyc_status", "city")
    search_fields = ("business_name", "owner_full_name", "user__phone", "gstin", "pan")


@admin.register(FleetOwnerDocument)
class FleetOwnerDocumentAdmin(admin.ModelAdmin):
    list_display = ("owner", "document_type", "status", "document_number", "reviewed_at")
    list_filter = ("document_type", "status")
    search_fields = ("owner__business_name", "owner__user__phone", "document_number")


@admin.register(FleetDriverMembership)
class FleetDriverMembershipAdmin(admin.ModelAdmin):
    list_display = ("owner", "driver", "status", "vehicle_number")
    list_filter = ("status",)
    search_fields = ("owner__business_name", "driver_display_name", "vehicle_number")
