from rest_framework import serializers

from .models import Payout


class PayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = "__all__"
        read_only_fields = ("wallet", "driver", "processed_by", "processed_reference")
