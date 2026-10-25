from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vehicle_categories", "0006_outstation_deadhead_and_layers"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehiclecategory",
            name="commission_percent",
            field=models.DecimalField(
                decimal_places=2,
                default=15.00,
                help_text="Platform commission percentage for this vehicle category (0-100%).",
                max_digits=5,
            ),
        ),
    ]
