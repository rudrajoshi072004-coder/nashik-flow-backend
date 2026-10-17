from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("drivers", "0003_driverprofile_accepts_outstation"),
    ]

    operations = [
        migrations.AddField(
            model_name="driverprofile",
            name="training_completed",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Whether driver has completed mandatory orientation training modules.",
            ),
        ),
    ]
