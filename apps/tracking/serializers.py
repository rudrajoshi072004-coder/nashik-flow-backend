from rest_framework import serializers

from .models import DriverLiveLocation


class DriverLiveLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverLiveLocation
        fields = "__all__"
