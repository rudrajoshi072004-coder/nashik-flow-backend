from django.contrib import admin

from .models import AdminLog


@admin.register(AdminLog)
class AdminLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "module", "action", "target_type", "target_id", "request_id")
    list_filter = ("module", "action")
    search_fields = ("request_id", "target_id", "actor__phone")
