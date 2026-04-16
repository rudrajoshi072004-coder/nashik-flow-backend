from django.db import models

from apps.common.models import TimeStampedUUIDModel


class Wallet(TimeStampedUUIDModel):
    driver = models.OneToOneField("drivers.DriverProfile", on_delete=models.PROTECT, related_name="wallet")
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pending_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    withdrawable_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_credited = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_debited = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_reconciled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["current_balance", "updated_at"])]
