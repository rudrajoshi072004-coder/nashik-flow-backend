from rest_framework import serializers

from .models import PricingRule, RouteTollCache


class PricingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingRule
        fields = "__all__"


class RouteTollCacheSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="vehicle_category.name", read_only=True, default="")

    class Meta:
        model = RouteTollCache
        fields = [
            "id",
            "origin_geohash",
            "destination_geohash",
            "origin_name",
            "destination_name",
            "vehicle_category",
            "vehicle_category_slug",
            "category_name",
            "toll_amount",
            "currency",
            "has_tolls",
            "toll_details",
            "source",
            "is_active",
            "expires_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

