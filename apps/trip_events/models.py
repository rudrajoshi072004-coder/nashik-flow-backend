from django.db import models

from apps.common.models import TimeStampedUUIDModel


class TripEvent(TimeStampedUUIDModel):
    booking = models.ForeignKey("bookings.Booking", on_delete=models.CASCADE, related_name="trip_events")
    actor_user = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL)
    actor_driver = models.ForeignKey("drivers.DriverProfile", null=True, blank=True, on_delete=models.SET_NULL)
    event_type = models.CharField(max_length=64, db_index=True)
    from_state = models.CharField(max_length=64, blank=True)
    to_state = models.CharField(max_length=64, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["sequence", "created_at"]
        unique_together = ("booking", "sequence")
        indexes = [models.Index(fields=["booking", "event_type", "created_at"])]
