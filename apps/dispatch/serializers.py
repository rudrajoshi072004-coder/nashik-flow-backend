from rest_framework import serializers


class DispatchTriggerSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField()


class DispatchReassignSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField()
    timeout_seconds = serializers.IntegerField(min_value=5, max_value=180, required=False, default=30)
