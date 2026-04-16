from django.contrib import admin

from .models import Booking, BookingStop


class BookingStopInline(admin.TabularInline):
    model = BookingStop
    extra = 0


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "driver", "state", "booking_type", "scheduled_at", "estimated_fare", "final_fare")
    list_filter = ("state", "booking_type", "requires_helper", "is_deleted")
    search_fields = ("id", "customer__phone", "driver__user__phone")
    inlines = [BookingStopInline]


@admin.register(BookingStop)
class BookingStopAdmin(admin.ModelAdmin):
    list_display = ("booking", "sequence", "stop_type", "contact_phone")
    list_filter = ("stop_type", "is_deleted")
    search_fields = ("booking__id", "address_text", "contact_phone")
