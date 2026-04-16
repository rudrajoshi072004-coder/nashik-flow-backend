from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("rating", "sentiment_score", "is_flagged", "created_at")
    list_filter = ("is_flagged", "is_deleted")
    search_fields = ("rating__booking__id", "comment")
