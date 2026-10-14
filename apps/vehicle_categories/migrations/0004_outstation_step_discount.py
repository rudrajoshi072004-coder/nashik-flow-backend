from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vehicle_categories", "0003_base_fare_km"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehiclecategory",
            name="outstation_step_km",
            field=models.DecimalField(
                decimal_places=2,
                default=10,
                help_text="After the 50 km outstation minimum, reduce the per-km rate on every extra block of this many kilometres.",
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name="vehiclecategory",
            name="outstation_step_discount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Amount subtracted from the outstation per-km rate on each extra distance block.",
                max_digits=10,
            ),
        ),
    ]
