from django.contrib.gis.db import models

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class Address(TimeStampedUUIDModel, SoftDeleteModel):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=64)
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    landmark = models.CharField(max_length=128, blank=True)
    city = models.CharField(max_length=64, default="Nashik", db_index=True)
    pincode = models.CharField(max_length=12, blank=True, db_index=True)
    location = models.PointField(srid=4326, geography=True)
    is_default = models.BooleanField(default=False, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["user", "is_default"]), models.Index(fields=["city", "pincode"])]
