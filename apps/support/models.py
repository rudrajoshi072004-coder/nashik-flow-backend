from django.db import models

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class SupportTicket(TimeStampedUUIDModel, SoftDeleteModel):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    created_by = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="created_tickets")
    assigned_to = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_tickets")
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.SET_NULL, related_name="support_tickets")
    subject = models.CharField(max_length=160)
    description = models.TextField()
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.MEDIUM, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["status", "priority", "created_at"])]
