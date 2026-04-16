from django.contrib import admin

from .models import WalletTransaction


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("wallet", "transaction_type", "amount", "balance_before", "balance_after", "reference_id")
    list_filter = ("transaction_type",)
    search_fields = ("wallet__driver__user__phone", "reference_id")
