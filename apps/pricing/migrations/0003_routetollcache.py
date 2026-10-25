import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0002_pricingrule_trip_type_slabs'),
        ('vehicle_categories', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RouteTollCache',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('origin_geohash', models.CharField(db_index=True, max_length=12)),
                ('destination_geohash', models.CharField(db_index=True, max_length=12)),
                ('origin_name', models.CharField(blank=True, default='', max_length=120)),
                ('destination_name', models.CharField(blank=True, default='', max_length=120)),
                ('vehicle_category_slug', models.CharField(blank=True, db_index=True, default='', max_length=64)),
                ('toll_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('currency', models.CharField(default='INR', max_length=10)),
                ('has_tolls', models.BooleanField(default=True)),
                ('toll_details', models.JSONField(blank=True, default=list)),
                ('source', models.CharField(choices=[('google_routes', 'Google Routes API'), ('manual_override', 'Manual Admin Override'), ('mappls', 'Mappls API'), ('fallback', 'Fallback Default')], default='google_routes', max_length=32)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('vehicle_category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='route_tolls', to='vehicle_categories.vehiclecategory')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['origin_geohash', 'destination_geohash', 'vehicle_category_slug', 'is_active'], name='pricing_rou_origin__9f9293_idx'),
                    models.Index(fields=['expires_at', 'is_active'], name='pricing_rou_expires_e29124_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(fields=('origin_geohash', 'destination_geohash', 'vehicle_category_slug'), name='uniq_route_toll_corridor_category'),
                ],
            },
        ),
    ]
