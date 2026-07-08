from django.db import models

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class DriverDocument(TimeStampedUUIDModel, SoftDeleteModel):
    class DocumentType(models.TextChoices):
        LICENSE = "license", "License"
        LICENSE_FRONT = "license_front", "License Front"
        LICENSE_BACK = "license_back", "License Back"
        RC = "rc", "Registration Certificate"
        INSURANCE = "insurance", "Insurance"
        PAN = "pan", "PAN"
        PAN_FRONT = "pan_front", "PAN Front"
        PAN_BACK = "pan_back", "PAN Back"
        AADHAAR = "aadhaar", "Aadhaar"
        AADHAAR_FRONT = "aadhaar_front", "Aadhaar Front"
        AADHAAR_BACK = "aadhaar_back", "Aadhaar Back"
        OWNER_SELFIE = "owner_selfie", "Owner Selfie"

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
