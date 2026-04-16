from rest_framework import serializers

from .models import FareRule


class FareRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FareRule
        fields = "__all__"
