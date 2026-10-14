from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vehicle_categories", "0002_outstation_rates"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehiclecategory",
            name="base_fare_km",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Kilometres covered by the base fare. Per-km rate applies after this distance.",
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name="vehiclecategory",
            name="outstation_base_fare_km",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Kilometres covered by the outstation base fare. Per-km rate applies after this distance.",
                max_digits=10,
            ),
        ),
    ]
