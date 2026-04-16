from django.contrib import admin

from .models import Payout


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("driver", "amount", "status", "processed_reference", "created_at")
    list_filter = ("status",)
    search_fields = ("driver__user__phone", "processed_reference")
