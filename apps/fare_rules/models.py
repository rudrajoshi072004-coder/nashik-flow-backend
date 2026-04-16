from django.db import models

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class FareRule(TimeStampedUUIDModel, SoftDeleteModel):
    class RuleType(models.TextChoices):
        EXTRA_STOP = "extra_stop", "Extra Stop"
        HELPER = "helper", "Helper"
        TAX = "tax", "Tax"
        COUPON = "coupon", "Coupon"
        WAITING = "waiting", "Waiting"

    pricing_rule = models.ForeignKey("pricing.PricingRule", on_delete=models.CASCADE, related_name="fare_rules")
    rule_type = models.CharField(max_length=32, choices=RuleType.choices, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    metadata = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["rule_type", "active"])]
