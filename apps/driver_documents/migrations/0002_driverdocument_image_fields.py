from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("driver_documents", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="driverdocument",
            name="file_key",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="driverdocument",
            name="image",
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="driverdocument",
            name="content_type",
            field=models.CharField(blank=True, default="image/jpeg", max_length=64),
        ),
        migrations.AddField(
            model_name="driverdocument",
            name="document_number",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
