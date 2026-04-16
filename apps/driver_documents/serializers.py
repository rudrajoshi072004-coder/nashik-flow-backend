from rest_framework import serializers

from .models import DriverDocument


class DriverDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverDocument
        fields = "__all__"
