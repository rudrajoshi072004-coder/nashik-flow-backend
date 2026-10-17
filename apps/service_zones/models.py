from django.contrib.gis.db import models

from apps.common.models import SoftDeleteModel, TimeStampedUUIDModel


class ServiceZone(TimeStampedUUIDModel, SoftDeleteModel):
    city_name = models.CharField(max_length=64, db_index=True, default="Nashik")
    zone_name = models.CharField(max_length=128)
    polygon = models.PolygonField(srid=4326, geography=True)
    active = models.BooleanField(default=True, db_index=True)
    dispatch_radius_km = models.DecimalField(max_digits=6, decimal_places=2, default=5)
    service_radius_km = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=50,
        help_text="Max distance (km) for within-city trips from service center.",
    )
    directional_sections = models.JSONField(
        default=dict,
        blank=True,
        help_text="4 directional sections (north, south, east, west) with polygons, quotas, and configurations.",
    )

    class Meta:
        unique_together = ("city_name", "zone_name")
        indexes = [models.Index(fields=["city_name", "active"])]

    def __str__(self) -> str:
        return f"{self.city_name} - {self.zone_name}"
