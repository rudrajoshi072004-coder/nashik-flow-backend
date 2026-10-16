from rest_framework import serializers


class DriverOnboardingDocumentSerializer(serializers.Serializer):
    owner_aadhaar_front = serializers.CharField(required=False, allow_blank=True)
    owner_aadhaar_back = serializers.CharField(required=False, allow_blank=True)
    owner_pan_front = serializers.CharField(required=False, allow_blank=True)
    owner_pan_back = serializers.CharField(required=False, allow_blank=True)
    owner_selfie = serializers.CharField(required=False, allow_blank=True)
    vehicle_rc = serializers.CharField(required=False, allow_blank=True)
    license_front = serializers.CharField(required=False, allow_blank=True)
    license_back = serializers.CharField(required=False, allow_blank=True)


class DriverOnboardingSubmitSerializer(serializers.Serializer):
    owner_name = serializers.CharField(max_length=128)
    will_drive_vehicle = serializers.ChoiceField(choices=("yes", "no"))
    driver_name = serializers.CharField(max_length=128)
    driver_phone = serializers.CharField(max_length=20)
    vehicle_number = serializers.CharField(max_length=32)
    vehicle_type = serializers.ChoiceField(choices=("truck", "3w", "2w", "part_load"))
    vehicle_body_type = serializers.CharField(required=False, allow_blank=True, max_length=32)
    truck_body_detail = serializers.CharField(required=False, allow_blank=True, max_length=32)
    three_wheeler_body_type = serializers.CharField(required=False, allow_blank=True, max_length=32)
    fuel_type = serializers.CharField(required=False, allow_blank=True, max_length=16)
    operation_city = serializers.CharField(max_length=64)
    accepts_outstation = serializers.BooleanField(required=False, default=True)
    documents = DriverOnboardingDocumentSerializer(required=False)

    def validate_driver_phone(self, value: str) -> str:
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) != 10:
            raise serializers.ValidationError("Enter a valid 10-digit phone number.")
        return digits

    def validate(self, attrs):
        vehicle_type = attrs.get("vehicle_type")
        if vehicle_type == "2w":
            if not (attrs.get("vehicle_body_type") or "").strip():
                raise serializers.ValidationError({"vehicle_body_type": "Required for 2W."})
            if not (attrs.get("fuel_type") or "").strip():
                raise serializers.ValidationError({"fuel_type": "Required for 2W."})
        if vehicle_type == "truck" and not (attrs.get("truck_body_detail") or "").strip():
            raise serializers.ValidationError({"truck_body_detail": "Required for truck."})
        if vehicle_type == "3w" and not (attrs.get("three_wheeler_body_type") or "").strip():
            raise serializers.ValidationError({"three_wheeler_body_type": "Required for 3W."})
        documents = attrs.get("documents") or {}
        if not (documents.get("license_front") or "").strip():
            raise serializers.ValidationError({"documents": "Driving license (front) is required."})
        if not (documents.get("vehicle_rc") or "").strip():
            raise serializers.ValidationError({"documents": "Vehicle RC is required."})
        return attrs
