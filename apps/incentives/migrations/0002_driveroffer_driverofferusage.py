import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("incentives", "0001_initial"),
        ("vehicle_categories", "0007_vehiclecategory_commission_percent"),
        ("drivers", "0004_driverprofile_training_completed"),
        ("bookings", "0004_booking_trip_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="DriverOffer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("title", models.CharField(help_text="Headline for the offer e.g. First 3 Rides 0% Commission", max_length=140)),
                ("description", models.TextField(blank=True, default="", help_text="Promotional description / rules for the driver")),
                ("rides_count", models.PositiveIntegerField(default=3, help_text="Number of commission-free rides (e.g. 3)")),
                ("commission_rate", models.DecimalField(decimal_places=2, default=0.00, help_text="Commission % charged during these rides (0.00% = 100% earnings to driver)", max_digits=5)),
                ("valid_days", models.PositiveIntegerField(default=7, help_text="Validity period in days (e.g. 7)")),
                ("start_date", models.DateField(db_index=True, help_text="Start date of the offer period")),
                ("end_date", models.DateField(db_index=True, help_text="End date of the offer period")),
                ("banner_url", models.TextField(help_text="Mandatory image banner URL or Cloudflare R2 / media path")),
                ("banner_image", models.BinaryField(blank=True, null=True)),
                ("banner_content_type", models.CharField(blank=True, default="image/jpeg", max_length=64)),
                ("active", models.BooleanField(db_index=True, default=True)),
                ("priority", models.PositiveIntegerField(default=10)),
                ("vehicle_categories", models.ManyToManyField(blank=True, help_text="If empty, applies to all vehicle categories.", related_name="driver_offers", to="vehicle_categories.vehiclecategory")),
            ],
            options={
                "ordering": ["-priority", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="driveroffer",
            index=models.Index(fields=["active", "start_date", "end_date"], name="driveroffer_active_dates_idx"),
        ),
        migrations.CreateModel(
            name="DriverOfferUsage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("ride_number", models.PositiveIntegerField(help_text="Ride sequence under this offer (e.g. 1, 2, 3)")),
                ("original_commission_percent", models.DecimalField(decimal_places=2, max_digits=5)),
                ("applied_commission_percent", models.DecimalField(decimal_places=2, default=0.00, max_digits=5)),
                ("saved_commission_amount", models.DecimalField(decimal_places=2, default=0.00, max_digits=10)),
                ("booking", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="offer_usages", to="bookings.booking")),
                ("driver", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="offer_usages", to="drivers.driverprofile")),
                ("offer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="usages", to="incentives.driveroffer")),
            ],
            options={
                "unique_together": {("offer", "booking")},
            },
        ),
        migrations.AddIndex(
            model_name="driverofferusage",
            index=models.Index(fields=["offer", "driver"], name="driverofferusage_offer_driver_idx"),
        ),
        migrations.AddIndex(
            model_name="driverofferusage",
            index=models.Index(fields=["driver", "created_at"], name="driverofferusage_driver_created_idx"),
        ),
    ]
