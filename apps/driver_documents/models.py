from django.db import models

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class DriverDocument(TimeStampedUUIDModel, SoftDeleteModel):
    class DocumentType(models.TextChoices):
        LICENSE = "license", "License"
        RC = "rc", "Registration Certificate"
        INSURANCE = "insurance", "Insurance"
        PAN = "pan", "PAN"
        AADHAAR = "aadhaar", "Aadhaar"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    driver = models.ForeignKey("drivers.DriverProfile", on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=24, choices=DocumentType.choices, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    file_key = models.CharField(max_length=255)
    reviewed_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        unique_together = ("driver", "document_type")
