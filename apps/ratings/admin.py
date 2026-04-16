from django.contrib import admin

from .models import Rating


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("booking", "customer", "driver", "score", "created_at")
    list_filter = ("score",)
    search_fields = ("booking__id", "customer__phone", "driver__user__phone")
