from django.contrib import admin

from .models import Address


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "city", "pincode", "is_default", "created_at")
    list_filter = ("city", "is_default", "is_deleted")
    search_fields = ("user__phone", "line1", "line2", "landmark", "pincode")
