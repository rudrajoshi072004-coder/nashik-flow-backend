from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0003_booking_parcel_photo_r2"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="trip_type",
            field=models.CharField(
                choices=[("within_city", "Within City"), ("outstation", "Outstation")],
                db_index=True,
                default="within_city",
                max_length=32,
            ),
        ),
    ]
