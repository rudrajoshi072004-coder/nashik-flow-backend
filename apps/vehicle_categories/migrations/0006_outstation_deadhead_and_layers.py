from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vehicle_categories", "0005_outstation_threshold_km"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehiclecategory",
            name="outstation_step_discount_percent",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Percentage reduced from per-km rate on each extra distance block (0-100).",
                max_digits=5,
            ),
        ),
        migrations.AddField(
            model_name="vehiclecategory",
            name="outstation_deadhead_multiplier",
            field=models.DecimalField(
                decimal_places=2,
                default=1.00,
                help_text="Multiplier applied to outstation distance charge to compensate for deadhead/empty return (e.g. 1.30 to 1.40).",
                max_digits=5,
            ),
        ),
        migrations.AddField(
            model_name="vehiclecategory",
            name="outstation_min_per_km_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Hard floor per-km rate below which outstation rate will never drop.",
                max_digits=10,
            ),
        ),
    ]
