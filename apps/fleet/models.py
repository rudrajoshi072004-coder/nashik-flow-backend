from django.db import models

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class FleetOwnerProfile(TimeStampedUUIDModel, SoftDeleteModel):
    class KYCStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        UNDER_REVIEW = "under_review", "Under Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.OneToOneField("users.User", on_delete=models.CASCADE, related_name="fleet_owner_profile")
    business_name = models.CharField(max_length=160, blank=True, default="")
    owner_full_name = models.CharField(max_length=128, blank=True, default="")
    gstin = models.CharField(max_length=32, blank=True, default="")
    pan = models.CharField(max_length=16, blank=True, default="")
    city = models.CharField(max_length=64, blank=True, default="Nashik")
    address = models.CharField(max_length=255, blank=True, default="")
    operating_cities = models.CharField(max_length=255, blank=True, default="")
    vehicle_count = models.PositiveIntegerField(default=0)
    bank_account_name = models.CharField(max_length=128, blank=True, default="")
    bank_account_number = models.CharField(max_length=32, blank=True, default="")
    bank_ifsc = models.CharField(max_length=16, blank=True, default="")
    upi_id = models.CharField(max_length=80, blank=True, default="")

    kyc_status = models.CharField(max_length=16, choices=KYCStatus.choices, default=KYCStatus.PENDING, db_index=True)
    kyc_submitted_at = models.DateTimeField(null=True, blank=True)
    kyc_verified_at = models.DateTimeField(null=True, blank=True)
    kyc_rejection_reason = models.TextField(blank=True, default="")

    @property
    def onboarding_complete(self) -> bool:
        return bool(self.business_name.strip() and self.owner_full_name.strip() and self.city.strip())

    def __str__(self) -> str:
        return self.business_name or self.user.phone


class FleetOwnerDocument(TimeStampedUUIDModel, SoftDeleteModel):
    class DocumentType(models.TextChoices):
        PAN_CARD = "pan_card", "PAN Card"
        AADHAAR_FRONT = "aadhaar_front", "Aadhaar Front"
        AADHAAR_BACK = "aadhaar_back", "Aadhaar Back"
        BUSINESS_REGISTRATION = "business_reg", "GSTIN / MSME / Trade License"
        BANK_CHEQUE = "bank_cheque", "Cancelled Cheque / Passbook"
        TRANSPORT_PERMIT = "transport_permit", "Transport Operator Permit"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    owner = models.ForeignKey(FleetOwnerProfile, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=32, choices=DocumentType.choices, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    file_key = models.CharField(max_length=255, blank=True, default="")
    file_url = models.URLField(max_length=500, blank=True, default="")
    image = models.BinaryField(null=True, blank=True)
    content_type = models.CharField(max_length=64, default="image/jpeg", blank=True)
    document_number = models.CharField(max_length=64, blank=True, default="")
    reviewed_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")

    class Meta:
        unique_together = ("owner", "document_type")
        indexes = [
            models.Index(fields=["owner", "document_type"]),
            models.Index(fields=["owner", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.owner.business_name} - {self.get_document_type_display()} ({self.status})"


class FleetDriverMembership(TimeStampedUUIDModel, SoftDeleteModel):
    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        REMOVED = "removed", "Removed"

    owner = models.ForeignKey(FleetOwnerProfile, on_delete=models.CASCADE, related_name="memberships")
    driver = models.ForeignKey("drivers.DriverProfile", on_delete=models.CASCADE, related_name="fleet_memberships")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    driver_display_name = models.CharField(max_length=128, blank=True, default="")
    vehicle_number = models.CharField(max_length=32, blank=True, default="")
    vehicle_type = models.CharField(max_length=32, blank=True, default="")
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "driver"],
                condition=models.Q(is_deleted=False),
                name="uniq_active_fleet_owner_driver",
            )
        ]
        indexes = [
            models.Index(fields=["owner", "status"]),
        ]
