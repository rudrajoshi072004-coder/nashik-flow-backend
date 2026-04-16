from django.contrib import admin

from .models import Refund


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("payment", "booking", "amount", "status", "processed_reference", "created_at")
    list_filter = ("status",)
    search_fields = ("payment__transaction_ref", "booking__id", "processed_reference")
