from django.db import models
from apps.common.models import TimeStampedUUIDModel


class Role(TimeStampedUUIDModel):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class Permission(TimeStampedUUIDModel):
    code = models.CharField(max_length=128, unique=True)
    module = models.CharField(max_length=64, db_index=True)
    action = models.CharField(max_length=64)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["module", "action", "code"]

    def __str__(self) -> str:
        return self.code


class RolePermission(TimeStampedUUIDModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="permission_roles")

    class Meta:
        unique_together = ("role", "permission")


class UserRole(TimeStampedUUIDModel):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_users")

    class Meta:
        unique_together = ("user", "role")
