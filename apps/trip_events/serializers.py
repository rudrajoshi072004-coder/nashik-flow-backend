from rest_framework import serializers

from .models import TripEvent


class TripEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripEvent
        fields = "__all__"
