import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fleet", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="fleetownerprofile",
            name="kyc_rejection_reason",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="fleetownerprofile",
            name="kyc_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("under_review", "Under Review"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                db_index=True,
                default="pending",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="fleetownerprofile",
            name="kyc_submitted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="fleetownerprofile",
            name="kyc_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="FleetOwnerDocument",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                (
                    "document_type",
                    models.CharField(
                        choices=[
                            ("pan_card", "PAN Card"),
                            ("aadhaar_front", "Aadhaar Front"),
                            ("aadhaar_back", "Aadhaar Back"),
                            ("business_reg", "GSTIN / MSME / Trade License"),
                            ("bank_cheque", "Cancelled Cheque / Passbook"),
                            ("transport_permit", "Transport Operator Permit"),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("file_key", models.CharField(blank=True, default="", max_length=255)),
                ("file_url", models.URLField(blank=True, default="", max_length=500)),
                ("image", models.BinaryField(blank=True, null=True)),
                ("content_type", models.CharField(blank=True, default="image/jpeg", max_length=64)),
                ("document_number", models.CharField(blank=True, default="", max_length=64)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("rejection_reason", models.TextField(blank=True, default="")),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="fleet.fleetownerprofile",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["owner", "document_type"], name="fleet_doc_owner_type_idx"),
                    models.Index(fields=["owner", "status"], name="fleet_doc_owner_status_idx"),
                ],
                "unique_together": {("owner", "document_type")},
            },
        ),
    ]
