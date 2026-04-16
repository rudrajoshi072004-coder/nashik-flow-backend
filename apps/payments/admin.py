from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("booking", "customer", "method", "status", "amount", "transaction_ref")
    list_filter = ("method", "status")
    search_fields = ("booking__id", "customer__phone", "transaction_ref")
