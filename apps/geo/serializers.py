from rest_framework import serializers

from .models import GeoPointSnapshot


class GeoPointSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeoPointSnapshot
        fields = "__all__"
