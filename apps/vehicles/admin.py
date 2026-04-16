from django.contrib import admin

from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "category", "driver", "status", "created_at")
    list_filter = ("status", "category", "is_deleted")
    search_fields = ("registration_number", "brand", "model_name", "driver__user__phone")
