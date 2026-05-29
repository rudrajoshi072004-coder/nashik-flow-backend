from rest_framework import serializers

from .models import DriverProfile


class DriverProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverProfile
        fields = "__all__"
        read_only_fields = ("user", "kyc_status", "rating_avg", "total_trips")


class DriverAvailabilitySerializer(serializers.Serializer):
    is_online = serializers.BooleanField()
    lat = serializers.FloatField(required=False)
    lng = serializers.FloatField(required=False)
    heading = serializers.FloatField(required=False, default=0)
    speed_kmph = serializers.FloatField(required=False, default=0)
    accuracy_m = serializers.FloatField(required=False, default=0)


class DriverLocationSerializer(serializers.Serializer):
    lat = serializers.FloatField()
    lng = serializers.FloatField()
    heading = serializers.FloatField(required=False, default=0)
    speed_kmph = serializers.FloatField(required=False, default=0)
    accuracy_m = serializers.FloatField(required=False, default=0)
    booking_id = serializers.UUIDField(required=False, allow_null=True)
