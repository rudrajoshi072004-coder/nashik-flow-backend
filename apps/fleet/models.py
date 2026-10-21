from django.db import models

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class FleetOwnerProfile(TimeStampedUUIDModel, SoftDeleteModel):
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

    @property
    def onboarding_complete(self) -> bool:
        return bool(self.business_name.strip() and self.owner_full_name.strip() and self.city.strip())

    def __str__(self) -> str:
        return self.business_name or self.user.phone


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
