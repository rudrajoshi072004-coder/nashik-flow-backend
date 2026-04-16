from rest_framework import serializers

from .models import WalletTransaction


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = "__all__"
        read_only_fields = ("wallet", "balance_before", "balance_after", "reference_id")
