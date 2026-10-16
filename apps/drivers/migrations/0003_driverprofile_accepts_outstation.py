from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("drivers", "0002_driver_onboarding_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="driverprofile",
            name="accepts_outstation",
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text="Whether 3W/4W driver is willing to accept outstation trips outside city boundaries.",
            ),
        ),
    ]
