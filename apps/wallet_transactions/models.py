from django.db import models

from apps.common.models import TimeStampedUUIDModel


class WalletTransaction(TimeStampedUUIDModel):
    class TransactionType(models.TextChoices):
        TRIP_EARNING = "trip_earning", "Trip Earning"
        BONUS = "bonus", "Bonus"
        INCENTIVE = "incentive", "Incentive"
        PENALTY = "penalty", "Penalty"
        MANUAL_CREDIT = "manual_credit", "Manual Credit"
        MANUAL_DEBIT = "manual_debit", "Manual Debit"
        PAYOUT_REQUEST = "payout_request", "Payout Request"
        PAYOUT_PROCESSED = "payout_processed", "Payout Processed"
        PAYOUT_REVERSED = "payout_reversed", "Payout Reversed"
        REFUND_ADJUSTMENT = "refund_adjustment", "Refund Adjustment"

    wallet = models.ForeignKey("wallets.Wallet", on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=32, choices=TransactionType.choices, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_before = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reference_id = models.CharField(max_length=128, unique=True)
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.SET_NULL)
    initiated_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["wallet", "created_at"]),
            models.Index(fields=["transaction_type", "created_at"]),
            models.Index(fields=["reference_id"]),
        ]
