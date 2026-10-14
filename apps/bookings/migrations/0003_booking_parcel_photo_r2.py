from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0002_booking_parcel_photo"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookingparcelphoto",
            name="file_key",
            field=models.CharField(blank=True, db_index=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="bookingparcelphoto",
            name="image_url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
        migrations.AlterField(
            model_name="bookingparcelphoto",
            name="image",
            field=models.BinaryField(blank=True, null=True),
        ),
    ]
