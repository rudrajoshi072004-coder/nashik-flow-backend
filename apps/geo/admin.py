from django.contrib import admin

from .models import GeoPointSnapshot


@admin.register(GeoPointSnapshot)
class GeoPointSnapshotAdmin(admin.ModelAdmin):
    list_display = ("source", "created_at")
    list_filter = ("source",)
    search_fields = ("source",)
