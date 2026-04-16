from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("phone", "role", "city", "is_active", "is_phone_verified", "created_at")
    list_filter = ("role", "city", "is_active", "is_phone_verified", "is_deleted")
    search_fields = ("phone", "email", "first_name", "last_name")
