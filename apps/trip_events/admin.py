from django.contrib import admin

from .models import TripEvent


@admin.register(TripEvent)
class TripEventAdmin(admin.ModelAdmin):
    list_display = ("booking", "event_type", "from_state", "to_state", "sequence", "created_at")
    list_filter = ("event_type", "from_state", "to_state")
    search_fields = ("booking__id", "event_type")
