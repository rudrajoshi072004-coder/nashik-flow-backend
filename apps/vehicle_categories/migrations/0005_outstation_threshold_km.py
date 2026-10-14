from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vehicle_categories", "0004_outstation_step_discount"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehiclecategory",
            name="outstation_threshold_km",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Distance in km after which a trip is considered outstation for this vehicle. If 0, uses service zone radius.",
                max_digits=10,
            ),
        ),
    ]
