from django.contrib import admin

from .models import Incentive


@admin.register(Incentive)
class IncentiveAdmin(admin.ModelAdmin):
    list_display = ("driver", "name", "amount", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("driver__user__phone", "name")
