from decimal import Decimal
import math

from django.contrib.gis.geos import Point
from rest_framework import serializers

from .models import Booking, BookingStop


def _haversine_km(lat1, lon1, lat2, lon2) -> Decimal:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return Decimal(str(round(r * c, 2)))


class BookingStopSerializer(serializers.ModelSerializer):
    lat = serializers.FloatField(write_only=True)
    lng = serializers.FloatField(write_only=True)

    class Meta:
        model = BookingStop
        fields = [
            "id",
            "sequence",
            "stop_type",
            "address_text",
            "contact_name",
            "contact_phone",
            "notes",
            "location",
            "lat",
            "lng",
        ]
        read_only_fields = ["location", "id"]

    def create(self, validated_data):
        lat = validated_data.pop("lat")
        lng = validated_data.pop("lng")
        validated_data["location"] = Point(float(lng), float(lat), srid=4326)
        return super().create(validated_data)


class BookingSerializer(serializers.ModelSerializer):
    stops = BookingStopSerializer(many=True, required=False)
    pickup_lat = serializers.FloatField(write_only=True, required=False)
    pickup_lng = serializers.FloatField(write_only=True, required=False)
    drop_lat = serializers.FloatField(write_only=True, required=False)
    drop_lng = serializers.FloatField(write_only=True, required=False)

    class Meta:
        model = Booking
        fields = "__all__"
        read_only_fields = ("customer", "estimated_distance_km", "estimated_duration_min", "estimated_fare")
        extra_kwargs = {
            # Mobile sends pickup/drop as lat/lng; these are derived in create()
            "pickup_location": {"required": False},
            "drop_location": {"required": False},
        }

    def validate(self, attrs):
        booking_type = attrs.get("booking_type", getattr(self.instance, "booking_type", None))
        scheduled_at = attrs.get("scheduled_at", getattr(self.instance, "scheduled_at", None))
        if booking_type == Booking.BookingType.SCHEDULED and not scheduled_at:
            raise serializers.ValidationError({"scheduled_at": "Scheduled booking requires scheduled_at."})
        return attrs

    def create(self, validated_data):
        stops_data = validated_data.pop("stops", [])
        pickup_lat = validated_data.pop("pickup_lat")
        pickup_lng = validated_data.pop("pickup_lng")
        drop_lat = validated_data.pop("drop_lat")
        drop_lng = validated_data.pop("drop_lng")

        validated_data["pickup_location"] = Point(float(pickup_lng), float(pickup_lat), srid=4326)
        validated_data["drop_location"] = Point(float(drop_lng), float(drop_lat), srid=4326)

        distance_km = _haversine_km(pickup_lat, pickup_lng, drop_lat, drop_lng)
        category = validated_data["vehicle_category"]
        estimated_fare = max(category.minimum_fare, category.base_fare + (category.per_km_rate * distance_km))

        validated_data["estimated_distance_km"] = distance_km
        validated_data["estimated_duration_min"] = int(max(10, float(distance_km) * 4))
        validated_data["estimated_fare"] = estimated_fare
        validated_data["pricing_breakdown"] = {
            "base_fare": str(category.base_fare),
            "distance_km": str(distance_km),
            "per_km_rate": str(category.per_km_rate),
            "minimum_fare": str(category.minimum_fare),
            "estimated_fare": str(estimated_fare),
        }

        booking = super().create(validated_data)
        for stop in stops_data:
            lat = stop.pop("lat")
            lng = stop.pop("lng")
            BookingStop.objects.create(
                booking=booking,
                location=Point(float(lng), float(lat), srid=4326),
                **stop,
            )
        return booking


class FareEstimateSerializer(serializers.Serializer):
    vehicle_category_id = serializers.UUIDField()
    pickup_lat = serializers.FloatField()
    pickup_lng = serializers.FloatField()
    drop_lat = serializers.FloatField()
    drop_lng = serializers.FloatField()
    requires_helper = serializers.BooleanField(default=False)
