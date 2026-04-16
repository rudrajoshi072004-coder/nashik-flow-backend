from django.contrib.gis.db import models
from apps.common.models import TimeStampedUUIDModel


class GeoPointSnapshot(TimeStampedUUIDModel):
    """
    Foundation geo model to validate PostGIS integration and provide
    reusable shape for future tracking/location modules.
    """

    source = models.CharField(max_length=64, db_index=True)
    location = models.PointField(srid=4326, geography=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["source", "created_at"])]
