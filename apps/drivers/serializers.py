from rest_framework import serializers

from .models import DriverProfile


class DriverProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverProfile
        fields = "__all__"
        read_only_fields = ("user", "kyc_status", "rating_avg", "total_trips")


class DriverAvailabilitySerializer(serializers.Serializer):
    is_online = serializers.BooleanField()
