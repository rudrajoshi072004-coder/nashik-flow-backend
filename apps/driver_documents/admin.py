from django.contrib import admin

from .models import DriverDocument


@admin.register(DriverDocument)
class DriverDocumentAdmin(admin.ModelAdmin):
    list_display = ("driver", "document_type", "status", "reviewed_by", "reviewed_at")
    list_filter = ("document_type", "status", "is_deleted")
    search_fields = ("driver__user__phone", "file_key")
