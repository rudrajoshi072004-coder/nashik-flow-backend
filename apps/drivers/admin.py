from django.contrib import admin

from .models import DriverProfile


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "kyc_status", "is_online", "onboarding_completed", "total_trips")
    list_filter = ("kyc_status", "is_online", "onboarding_completed", "is_deleted")
    search_fields = ("user__phone", "user__first_name", "user__last_name")
