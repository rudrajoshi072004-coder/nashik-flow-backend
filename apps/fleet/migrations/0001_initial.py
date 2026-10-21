import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("drivers", "0004_driverprofile_training_completed"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FleetOwnerProfile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("business_name", models.CharField(blank=True, default="", max_length=160)),
                ("owner_full_name", models.CharField(blank=True, default="", max_length=128)),
                ("gstin", models.CharField(blank=True, default="", max_length=32)),
                ("pan", models.CharField(blank=True, default="", max_length=16)),
                ("city", models.CharField(blank=True, default="Nashik", max_length=64)),
                ("address", models.CharField(blank=True, default="", max_length=255)),
                ("operating_cities", models.CharField(blank=True, default="", max_length=255)),
                ("vehicle_count", models.PositiveIntegerField(default=0)),
                ("bank_account_name", models.CharField(blank=True, default="", max_length=128)),
                ("bank_account_number", models.CharField(blank=True, default="", max_length=32)),
                ("bank_ifsc", models.CharField(blank=True, default="", max_length=16)),
                ("upi_id", models.CharField(blank=True, default="", max_length=80)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fleet_owner_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"abstract": False},
        ),
        migrations.CreateModel(
            name="FleetDriverMembership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("invited", "Invited"),
                            ("active", "Active"),
                            ("suspended", "Suspended"),
                            ("removed", "Removed"),
                        ],
                        db_index=True,
                        default="active",
                        max_length=16,
                    ),
                ),
                ("driver_display_name", models.CharField(blank=True, default="", max_length=128)),
                ("vehicle_number", models.CharField(blank=True, default="", max_length=32)),
                ("vehicle_type", models.CharField(blank=True, default="", max_length=32)),
                ("notes", models.CharField(blank=True, default="", max_length=255)),
                (
                    "driver",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fleet_memberships",
                        to="drivers.driverprofile",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="fleet.fleetownerprofile",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="fleetdrivermembership",
            index=models.Index(fields=["owner", "status"], name="fleet_fleet_owner_i_7c1a2b_idx"),
        ),
        migrations.AddConstraint(
            model_name="fleetdrivermembership",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_deleted", False)),
                fields=("owner", "driver"),
                name="uniq_active_fleet_owner_driver",
            ),
        ),
    ]
