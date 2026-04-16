from django.db import models

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class Review(TimeStampedUUIDModel, SoftDeleteModel):
    rating = models.OneToOneField("ratings.Rating", on_delete=models.CASCADE, related_name="review")
    comment = models.TextField(blank=True)
    sentiment_score = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    is_flagged = models.BooleanField(default=False, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["is_flagged", "created_at"])]
