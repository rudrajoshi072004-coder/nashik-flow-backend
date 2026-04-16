from django.contrib import admin

from .models import Coupon


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "discount_type", "discount_value", "active", "valid_from", "valid_until")
    list_filter = ("discount_type", "active", "is_deleted")
    search_fields = ("code",)
