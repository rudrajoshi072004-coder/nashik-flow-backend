from rest_framework import serializers


class OTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value


class OTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    otp = serializers.CharField(max_length=6, min_length=6)

    def validate_phone(self, value: str) -> str:
        return (value or "").strip()


class PasswordLoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_phone(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value


class FirebaseLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField(trim_whitespace=True)
    role = serializers.ChoiceField(choices=["customer", "driver"], required=False, default="customer")
    city = serializers.CharField(max_length=64, required=False, default="Nashik")

    def validate_id_token(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value


class AuthUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    phone = serializers.CharField()
    role = serializers.CharField()
    city = serializers.CharField()
