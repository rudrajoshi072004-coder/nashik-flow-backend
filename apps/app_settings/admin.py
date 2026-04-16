from django.contrib import admin

from .models import AppSetting


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value_type", "is_public", "updated_at")
    list_filter = ("value_type", "is_public")
    search_fields = ("key", "description")
