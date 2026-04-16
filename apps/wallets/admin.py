from django.contrib import admin

from .models import Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("driver", "current_balance", "pending_balance", "withdrawable_balance", "updated_at")
    search_fields = ("driver__user__phone",)
