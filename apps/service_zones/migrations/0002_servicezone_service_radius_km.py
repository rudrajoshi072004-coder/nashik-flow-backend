from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("service_zones", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicezone",
            name="service_radius_km",
            field=models.DecimalField(
                decimal_places=2,
                default=50,
                help_text="Max distance (km) for within-city trips from service center.",
                max_digits=6,
            ),
        ),
    ]
