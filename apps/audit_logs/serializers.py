from rest_framework import serializers

from .models import AdminLog


class AdminLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminLog
        fields = "__all__"
