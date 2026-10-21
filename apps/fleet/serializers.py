from rest_framework import serializers

from apps.authn.phone_utils import normalize_phone_e164

from .models import FleetDriverMembership, FleetOwnerProfile


class FleetOwnerProfileSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source="user.phone", read_only=True)
    onboarding_complete = serializers.BooleanField(read_only=True)

    class Meta:
        model = FleetOwnerProfile
        fields = (
            "id",
            "phone",
            "business_name",
            "owner_full_name",
            "gstin",
            "pan",
            "city",
            "address",
            "operating_cities",
            "vehicle_count",
            "bank_account_name",
            "bank_account_number",
            "bank_ifsc",
            "upi_id",
            "onboarding_complete",
        )


class AddFleetDriverSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    driver_name = serializers.CharField(max_length=128, required=False, allow_blank=True)
    vehicle_number = serializers.CharField(max_length=32, required=False, allow_blank=True)
    vehicle_type = serializers.CharField(max_length=32, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_phone(self, value: str) -> str:
        phone = normalize_phone_e164(value)
        if not phone:
            raise serializers.ValidationError("Enter a valid driver mobile number.")
        return phone


class UpdateMembershipSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[FleetDriverMembership.Status.ACTIVE, FleetDriverMembership.Status.SUSPENDED, FleetDriverMembership.Status.REMOVED],
        required=False,
    )
    driver_display_name = serializers.CharField(max_length=128, required=False, allow_blank=True)
    vehicle_number = serializers.CharField(max_length=32, required=False, allow_blank=True)
    vehicle_type = serializers.CharField(max_length=32, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True)
