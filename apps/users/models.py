from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedUUIDModel, SoftDeleteModel


class User(TimeStampedUUIDModel, SoftDeleteModel, AbstractUser):
    class Role(models.TextChoices):
        GUEST = "guest", "Guest"
        CUSTOMER = "customer", "Customer"
        DRIVER = "driver", "Driver"
        FLEET_DRIVER = "fleet_driver", "Fleet Driver"
        CITY_MANAGER = "city_manager", "City Manager"
        SUPPORT_AGENT = "support_agent", "Support Agent"
        FINANCE_ADMIN = "finance_admin", "Finance Admin"
        SUPER_ADMIN = "super_admin", "Super Admin"

    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, unique=True, db_index=True)
    email = models.EmailField(blank=True, null=True, db_index=True)
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.GUEST, db_index=True)
    role_ref = models.ForeignKey(
        "rbac.Role",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    city = models.CharField(max_length=64, default="Nashik", db_index=True)
    is_phone_verified = models.BooleanField(default=False)

    REQUIRED_FIELDS = []
    EMAIL_FIELD = "email"
    USERNAME_FIELD = "phone"

    class Meta:
        indexes = [
            models.Index(fields=["role", "city", "is_active"]),
            models.Index(fields=["is_deleted", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["email"],
                condition=Q(email__isnull=False),
                name="uniq_user_non_null_email",
            )
        ]

    def __str__(self) -> str:
        return f"{self.phone} ({self.role})"
