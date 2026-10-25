from rest_framework import serializers

from apps.authn.phone_utils import normalize_phone_e164

from .models import FleetDriverMembership, FleetOwnerDocument, FleetOwnerProfile


class FleetOwnerDocumentSerializer(serializers.ModelSerializer):
    document_type_display = serializers.CharField(source="get_document_type_display", read_only=True)

    class Meta:
        model = FleetOwnerDocument
        fields = (
            "id",
            "document_type",
            "document_type_display",
            "status",
            "file_key",
            "file_url",
            "document_number",
            "rejection_reason",
            "reviewed_at",
            "created_at",
        )


class FleetOwnerProfileSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source="user.phone", read_only=True)
    onboarding_complete = serializers.BooleanField(read_only=True)
    documents = FleetOwnerDocumentSerializer(many=True, read_only=True)

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
            "kyc_status",
            "kyc_submitted_at",
            "kyc_verified_at",
            "kyc_rejection_reason",
            "onboarding_complete",
            "documents",
        )


class AddFleetDriverSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    driver_name = serializers.CharField(max_length=128, required=False, allow_blank=True)
    password = serializers.CharField(max_length=64, required=False, allow_blank=True, write_only=True)
    vehicle_number = serializers.CharField(max_length=32, required=False, allow_blank=True)
    vehicle_type = serializers.CharField(max_length=32, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True)
    documents = serializers.DictField(child=serializers.CharField(allow_blank=True), required=False)

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


class FleetDocumentUploadSerializer(serializers.Serializer):
    target = serializers.ChoiceField(choices=["owner", "driver"], default="owner")
    driver_id = serializers.UUIDField(required=False, allow_null=True)
    document_type = serializers.CharField(max_length=32)
    document_number = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    file = serializers.FileField(required=False, allow_null=True)
    file_url = serializers.URLField(max_length=500, required=False, allow_blank=True, default="")


class OwnerKycSubmitSerializer(serializers.Serializer):
    business_name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    owner_full_name = serializers.CharField(max_length=128, required=False, allow_blank=True)
    city = serializers.CharField(max_length=64, required=False, allow_blank=True)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    gstin = serializers.CharField(max_length=32, required=False, allow_blank=True)
    pan = serializers.CharField(max_length=16, required=False, allow_blank=True)
    vehicle_count = serializers.IntegerField(required=False, min_value=0)
    bank_account_name = serializers.CharField(max_length=128, required=False, allow_blank=True)
    bank_account_number = serializers.CharField(max_length=32, required=False, allow_blank=True)
    bank_ifsc = serializers.CharField(max_length=16, required=False, allow_blank=True)
    upi_id = serializers.CharField(max_length=80, required=False, allow_blank=True)
    documents = serializers.DictField(child=serializers.CharField(allow_blank=True), required=False)


class FleetAnalyticsFilterSerializer(serializers.Serializer):
    period = serializers.ChoiceField(choices=["today", "yesterday", "week", "month", "custom"], default="today")
    category = serializers.CharField(max_length=32, required=False, default="all")
    driver_id = serializers.UUIDField(required=False, allow_null=True)
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
