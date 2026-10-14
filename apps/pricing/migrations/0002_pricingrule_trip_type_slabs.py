from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pricing", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="pricingrule",
            name="trip_type",
            field=models.CharField(
                choices=[("within_city", "Within City"), ("outstation", "Outstation")],
                db_index=True,
                default="within_city",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="pricingrule",
            name="min_distance_km",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="pricingrule",
            name="max_distance_km",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
