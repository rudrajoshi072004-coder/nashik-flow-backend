from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookingParcelPhoto",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("kind", models.CharField(choices=[("pickup", "Pickup"), ("drop", "Drop")], max_length=16)),
                ("content_type", models.CharField(default="image/jpeg", max_length=64)),
                ("byte_size", models.PositiveIntegerField(default=0)),
                ("image", models.BinaryField()),
                (
                    "booking",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="parcel_photos",
                        to="bookings.booking",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("booking", "kind"), name="uniq_booking_parcel_photo_kind")
                ],
            },
        ),
    ]
