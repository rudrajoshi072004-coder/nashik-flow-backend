from django.contrib import admin

from .models import SupportTicket


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "created_by", "assigned_to", "priority", "status", "created_at")
    list_filter = ("priority", "status", "is_deleted")
    search_fields = ("id", "subject", "created_by__phone", "assigned_to__phone")
