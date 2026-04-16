from django.db import models

from apps.common.models import TimeStampedUUIDModel


class Rating(TimeStampedUUIDModel):
    booking = models.OneToOneField("bookings.Booking", on_delete=models.CASCADE, related_name="rating")
    customer = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="given_ratings")
    driver = models.ForeignKey("drivers.DriverProfile", on_delete=models.CASCADE, related_name="received_ratings")
    score = models.PositiveSmallIntegerField()
    tags = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(score__gte=1) & models.Q(score__lte=5), name="rating_between_1_5")
        ]
