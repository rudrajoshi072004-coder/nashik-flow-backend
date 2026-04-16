from django.db import models

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class Coupon(TimeStampedUUIDModel, SoftDeleteModel):
    class DiscountType(models.TextChoices):
        FLAT = "flat", "Flat"
        PERCENTAGE = "percentage", "Percentage"

    code = models.CharField(max_length=40, unique=True)
    discount_type = models.CharField(max_length=16, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_booking_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    max_uses = models.PositiveIntegerField(default=1)
    used_count = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["code", "active"]), models.Index(fields=["valid_from", "valid_until"])]
