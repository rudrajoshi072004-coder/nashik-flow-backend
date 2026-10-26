from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers

from apps.vehicle_categories.models import VehicleCategory
from .models import DriverOffer, DriverOfferUsage, Incentive


class IncentiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incentive
        fields = "__all__"


class DriverOfferUsageSerializer(serializers.ModelSerializer):
    driver_name = serializers.SerializerMethodField()
    booking_id = serializers.UUIDField(source="booking.id", read_only=True)

    class Meta:
        model = DriverOfferUsage
        fields = (
            "id",
            "offer",
            "driver",
            "driver_name",
            "booking_id",
            "ride_number",
            "original_commission_percent",
            "applied_commission_percent",
            "saved_commission_amount",
            "created_at",
        )

    def get_driver_name(self, obj) -> str:
        if obj.driver and obj.driver.user:
            return obj.driver.user.get_full_name() or obj.driver.user.phone or "Driver"
        return "Driver"


class DriverOfferSerializer(serializers.ModelSerializer):
    banner_url = serializers.CharField(required=False, allow_blank=True, default="")
    usages_count = serializers.SerializerMethodField()
    drivers_benefited_count = serializers.SerializerMethodField()
    total_commission_saved = serializers.SerializerMethodField()
    is_active_now = serializers.SerializerMethodField()
    vehicle_category_names = serializers.SerializerMethodField()

    class Meta:
        model = DriverOffer
        fields = (
            "id",
            "title",
            "description",
            "rides_count",
            "commission_rate",
            "valid_days",
            "start_date",
            "end_date",
            "banner_url",
            "vehicle_categories",
            "vehicle_category_names",
            "active",
            "priority",
            "usages_count",
            "drivers_benefited_count",
            "total_commission_saved",
            "is_active_now",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        title = (attrs.get("title") or (self.instance.title if self.instance else "")).strip()
        if not title:
            raise serializers.ValidationError({"title": "Offer title is mandatory."})

        request = self.context.get("request")
        has_file = bool(
            request
            and getattr(request, "FILES", None)
            and (request.FILES.get("file") or request.FILES.get("banner") or request.FILES.get("image"))
        )

        banner_url = (attrs.get("banner_url") or (self.instance.banner_url if self.instance else "")).strip()
        if not banner_url:
            if has_file:
                attrs["banner_url"] = "/api/v1/driver-offers/pending-banner/"
            elif not self.instance:
                raise serializers.ValidationError({"banner_url": "Banner image is mandatory. Please upload an image or provide a valid banner URL."})

        start_date = attrs.get("start_date") or (self.instance.start_date if self.instance else None)
        end_date = attrs.get("end_date") or (self.instance.end_date if self.instance else None)
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "End date must be on or after start date."})

        valid_days = attrs.get("valid_days") or (self.instance.valid_days if self.instance else 7)
        if valid_days is not None and valid_days < 1:
            raise serializers.ValidationError({"valid_days": "Validity days must be at least 1 day."})

        rides_count = attrs.get("rides_count") or (self.instance.rides_count if self.instance else 3)
        if rides_count is not None and rides_count < 1:
            raise serializers.ValidationError({"rides_count": "Rides count must be at least 1 ride."})

        commission_rate = attrs.get("commission_rate")
        if commission_rate is not None and (commission_rate < Decimal("0.00") or commission_rate > Decimal("100.00")):
            raise serializers.ValidationError({"commission_rate": "Commission rate must be between 0% and 100%."})

        return attrs

    def get_usages_count(self, obj) -> int:
        return obj.usages.count()

    def get_drivers_benefited_count(self, obj) -> int:
        return obj.usages.values("driver_id").distinct().count()

    def get_total_commission_saved(self, obj) -> str:
        from django.db.models import Sum
        val = obj.usages.aggregate(total=Sum("saved_commission_amount"))["total"] or Decimal("0.00")
        return str(val)

    def get_is_active_now(self, obj) -> bool:
        today = timezone.localdate()
        return bool(obj.active and obj.start_date <= today <= obj.end_date)

    def get_vehicle_category_names(self, obj) -> list[str]:
        return list(obj.vehicle_categories.values_list("name", flat=True))


class DriverActiveOfferSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    description = serializers.CharField()
    rides_count = serializers.IntegerField()
    commission_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    valid_days = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    banner_url = serializers.CharField()
    remaining_free_rides = serializers.IntegerField()
    completed_free_rides = serializers.IntegerField()
    is_exhausted = serializers.BooleanField()
