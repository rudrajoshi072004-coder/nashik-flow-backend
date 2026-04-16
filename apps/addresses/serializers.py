from rest_framework import serializers

from .models import Address
from django.contrib.gis.geos import Point


class AddressSerializer(serializers.ModelSerializer):
    lat = serializers.FloatField(write_only=True)
    lng = serializers.FloatField(write_only=True)

    class Meta:
        model = Address
        fields = (
            "id",
            "label",
            "line1",
            "line2",
            "landmark",
            "city",
            "pincode",
            "location",
            "is_default",
            "lat",
            "lng",
        )
        read_only_fields = ("id", "location")

    def create(self, validated_data):
        lat = validated_data.pop("lat")
        lng = validated_data.pop("lng")
        validated_data["location"] = Point(float(lng), float(lat), srid=4326)
        return super().create(validated_data)
