from rest_framework import serializers

from .models import DriverProfile


class DriverProfileSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source="user.phone", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    city = serializers.CharField(source="operation_city", read_only=True)
    vehicle_registration = serializers.CharField(source="vehicle_number", read_only=True)

    class Meta:
        model = DriverProfile
        fields = "__all__"
        read_only_fields = ("user", "kyc_status", "rating_avg", "total_trips")

    def get_full_name(self, obj: DriverProfile) -> str:
        return (obj.driver_name or obj.owner_name or obj.user.first_name or "").strip()

    def get_display_name(self, obj: DriverProfile) -> str:
        return self.get_full_name(obj)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        # 2-wheelers cannot accept outstation trips
        vehicle_type = attrs.get("vehicle_type") or (getattr(self.instance, "vehicle_type", "") if self.instance else "")
        if (vehicle_type or "").strip().lower() == "2w" and attrs.get("accepts_outstation"):
            attrs["accepts_outstation"] = False
        return attrs


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
