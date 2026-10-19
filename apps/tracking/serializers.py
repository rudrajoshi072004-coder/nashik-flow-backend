from rest_framework import serializers

from .models import DriverLiveLocation


class DriverLiveLocationSerializer(serializers.ModelSerializer):
    driver_id = serializers.UUIDField(source="driver.id", read_only=True)
    driver_name = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    vehicle_number = serializers.SerializerMethodField()
    vehicle_category = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()
    speed_kmh = serializers.DecimalField(source="speed_kmph", max_digits=6, decimal_places=2, read_only=True)

    class Meta:
        model = DriverLiveLocation
        fields = [
            "id",
            "driver",
            "driver_id",
            "driver_name",
            "phone",
            "vehicle_number",
            "vehicle_category",
            "city",
            "latitude",
            "longitude",
            "lat",
            "lng",
            "booking",
            "heading",
            "speed_kmph",
            "speed_kmh",
            "accuracy_m",
            "source_timestamp",
            "created_at",
            "updated_at",
        ]

    def get_driver_name(self, obj) -> str:
        if obj.driver:
            return obj.driver.public_display_name()
        return "Driver"

    def get_phone(self, obj) -> str:
        if not obj.driver:
            return ""
        if obj.driver.driver_phone:
            return str(obj.driver.driver_phone)
        user = getattr(obj.driver, "user", None)
        if user and getattr(user, "phone", None):
            return str(user.phone)
        return ""

    def get_vehicle_number(self, obj) -> str:
        if not obj.driver:
            return ""
        if obj.driver.vehicle_number:
            return str(obj.driver.vehicle_number)
        veh = getattr(obj.driver, "vehicles", None)
        if veh:
            active_veh = veh.filter(status="active").first()
            if active_veh:
                return active_veh.registration_number
        return ""

    def get_vehicle_category(self, obj) -> str:
        if not obj.driver:
            return "Tata Ace"
        if obj.driver.vehicle_type:
            return str(obj.driver.vehicle_type)
        veh = getattr(obj.driver, "vehicles", None)
        if veh:
            active_veh = veh.filter(status="active").select_related("category").first()
            if active_veh and active_veh.category:
                return active_veh.category.name
        return "Tata Ace"

    def get_city(self, obj) -> str:
        if not obj.driver:
            return "Nashik"
        if obj.driver.operation_city:
            return str(obj.driver.operation_city)
        user = getattr(obj.driver, "user", None)
        if user and getattr(user, "city", None):
            return str(user.city)
        return "Nashik"

    def get_latitude(self, obj) -> float | None:
        if obj.location:
            return float(obj.location.y)
        return None

    def get_longitude(self, obj) -> float | None:
        if obj.location:
            return float(obj.location.x)
        return None

    def get_lat(self, obj) -> float | None:
        return self.get_latitude(obj)

    def get_lng(self, obj) -> float | None:
        return self.get_longitude(obj)

