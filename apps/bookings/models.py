from django.contrib.gis.db import models
from django.core.validators import MinValueValidator
from django.db.models import Q

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class Booking(TimeStampedUUIDModel, SoftDeleteModel):
    class BookingState(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_QUOTE = "pending_quote", "Pending Quote"
        SEARCHING_DRIVER = "searching_driver", "Searching Driver"
        DRIVER_ASSIGNED = "driver_assigned", "Driver Assigned"
        DRIVER_ACCEPTED = "driver_accepted", "Driver Accepted"
        DRIVER_ARRIVING = "driver_arriving", "Driver Arriving"
        DRIVER_ARRIVED = "driver_arrived", "Driver Arrived"
        PICKUP_OTP_PENDING = "pickup_otp_pending", "Pickup OTP Pending"
        TRIP_STARTED = "trip_started", "Trip Started"
        IN_TRANSIT = "in_transit", "In Transit"
        NEARING_DROP = "nearing_drop", "Nearing Drop"
        COMPLETED = "completed", "Completed"
        CANCELLED_BY_CUSTOMER = "cancelled_by_customer", "Cancelled By Customer"
        CANCELLED_BY_DRIVER = "cancelled_by_driver", "Cancelled By Driver"
        CANCELLED_BY_ADMIN = "cancelled_by_admin", "Cancelled By Admin"
        PAYMENT_PENDING = "payment_pending", "Payment Pending"
        REFUNDED = "refunded", "Refunded"
        FAILED = "failed", "Failed"

    class BookingType(models.TextChoices):
        INSTANT = "instant", "Instant"
        SCHEDULED = "scheduled", "Scheduled"

    customer = models.ForeignKey("users.User", related_name="customer_bookings", on_delete=models.PROTECT)
    driver = models.ForeignKey("drivers.DriverProfile", related_name="bookings", on_delete=models.PROTECT, null=True, blank=True)
    vehicle_category = models.ForeignKey("vehicle_categories.VehicleCategory", on_delete=models.PROTECT)
    booking_type = models.CharField(max_length=32, choices=BookingType.choices, default=BookingType.INSTANT)
    state = models.CharField(max_length=64, choices=BookingState.choices, default=BookingState.DRAFT, db_index=True)
    pickup_location = models.PointField(srid=4326, geography=True)
    drop_location = models.PointField(srid=4326, geography=True)
    pickup_address_text = models.CharField(max_length=255, blank=True)
    drop_address_text = models.CharField(max_length=255, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    service_zone = models.ForeignKey("service_zones.ServiceZone", null=True, blank=True, on_delete=models.SET_NULL)
    estimated_distance_km = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    estimated_duration_min = models.PositiveIntegerField(default=0)
    pricing_breakdown = models.JSONField(default=dict, blank=True)
    estimated_fare = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    final_fare = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    cancellation_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    requires_helper = models.BooleanField(default=False)
    otp_code = models.CharField(max_length=8, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["state", "created_at"]),
            models.Index(fields=["booking_type", "scheduled_at"]),
            models.Index(fields=["customer", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(check=Q(estimated_fare__gte=0), name="booking_estimated_fare_gte_zero"),
            models.CheckConstraint(check=Q(final_fare__gte=0), name="booking_final_fare_gte_zero"),
        ]


class BookingStop(TimeStampedUUIDModel, SoftDeleteModel):
    class StopType(models.TextChoices):
        PICKUP = "pickup", "Pickup"
        WAYPOINT = "waypoint", "Waypoint"
        DROP = "drop", "Drop"

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="stops")
    sequence = models.PositiveIntegerField()
    stop_type = models.CharField(max_length=16, choices=StopType.choices, db_index=True)
    address_text = models.CharField(max_length=255, blank=True)
    location = models.PointField(srid=4326, geography=True)
    contact_name = models.CharField(max_length=120, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["sequence"]
        unique_together = ("booking", "sequence")
