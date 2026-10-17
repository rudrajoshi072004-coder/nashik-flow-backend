from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("service_zones", "0002_servicezone_service_radius_km"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicezone",
            name="directional_sections",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="4 directional sections (north, south, east, west) with polygons, quotas, and configurations.",
            ),
        ),
    ]
