from decimal import Decimal

from django.db import migrations, models


def copy_first_slab_into_category(apps, schema_editor):
    VehicleCategory = apps.get_model("vehicle_categories", "VehicleCategory")
    PricingRule = apps.get_model("pricing", "PricingRule")
    for category in VehicleCategory.objects.filter(is_deleted=False):
        slab = (
            PricingRule.objects.filter(
                is_deleted=False,
                active=True,
                vehicle_category_id=category.id,
                trip_type="outstation",
            )
            .order_by("min_distance_km", "-updated_at")
            .first()
        )
        if slab is not None:
            category.outstation_base_fare = slab.base_fare or Decimal("0")
            category.outstation_per_km_rate = slab.per_km_rate or Decimal("0")
            category.outstation_minimum_fare = slab.minimum_fare or Decimal("0")
        elif not category.outstation_per_km_rate:
            category.outstation_per_km_rate = category.per_km_rate
        category.save(
            update_fields=[
                "outstation_base_fare",
                "outstation_per_km_rate",
                "outstation_minimum_fare",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("vehicle_categories", "0001_initial"),
        ("pricing", "0002_pricingrule_trip_type_slabs"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehiclecategory",
            name="outstation_base_fare",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="vehiclecategory",
            name="outstation_minimum_fare",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="vehiclecategory",
            name="outstation_per_km_rate",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.RunPython(copy_first_slab_into_category, migrations.RunPython.noop),
    ]
