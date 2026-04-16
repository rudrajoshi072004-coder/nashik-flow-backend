from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "phone", "email", "first_name", "last_name", "role", "city", "is_phone_verified", "is_active")
        read_only_fields = ("id", "role", "is_phone_verified", "is_active")
