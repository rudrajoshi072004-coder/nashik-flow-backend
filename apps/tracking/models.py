from django.contrib.gis.db import models

from apps.common.models import TimeStampedUUIDModel


class DriverLiveLocation(TimeStampedUUIDModel):
    driver = models.OneToOneField("drivers.DriverProfile", on_delete=models.CASCADE, related_name="live_location")
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.SET_NULL, related_name="driver_location_updates")
    location = models.PointField(srid=4326, geography=True)
    heading = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    speed_kmph = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    accuracy_m = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    source_timestamp = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["booking", "created_at"]),
        ]
