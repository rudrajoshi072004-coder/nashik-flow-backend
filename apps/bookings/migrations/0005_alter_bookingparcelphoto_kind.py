# Generated migration for BookingParcelPhoto kind choices extension
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0004_booking_trip_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bookingparcelphoto",
            name="kind",
            field=models.CharField(
                choices=[
                    ("pickup", "Pickup"),
                    ("drop", "Drop"),
                    ("toll_receipt", "Toll Receipt"),
                ],
                max_length=16,
            ),
        ),
    ]
