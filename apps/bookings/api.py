from decimal import Decimal
import logging

from django.db.models import Q
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from apps.common.api.responses import success_response
from apps.dispatch.services import RIDE_REQUEST_SENT
from apps.common.permissions.rbac import IsAdminRole, IsCustomerOrAdmin, IsDriverOrAdmin
from apps.trip_events.models import TripEvent
from apps.vehicle_categories.models import VehicleCategory
from apps.dispatch.tasks import dispatch_booking

from .models import Booking
from .serializers import BookingSerializer, FareEstimateSerializer
from .services import transition_booking_state

logger = logging.getLogger(__name__)


class BookingTransitionSerializer(serializers.Serializer):
    to_state = serializers.CharField()
    payload = serializers.JSONField(required=False)


class TripEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripEvent
        fields = "__all__"


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.select_related("customer", "driver", "vehicle_category", "service_zone").all()
    serializer_class = BookingSerializer
    filterset_fields = ("state", "booking_type", "vehicle_category", "service_zone")
    search_fields = ("id", "customer__phone", "driver__user__phone", "pickup_address_text", "drop_address_text")
    ordering_fields = ("created_at", "scheduled_at", "estimated_fare")

    def get_permissions(self):
        if self.action in {"create", "list", "retrieve", "fare_estimate"}:
            return [IsCustomerOrAdmin()]
        if self.action in {"state_transition"}:
            return [IsAuthenticated()]
        if self.action in {"admin_update_state"}:
            return [IsAdminRole()]
        return [IsCustomerOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "customer":
            return qs.filter(customer=user, is_deleted=False)
        if user.role in {"driver", "fleet_driver"}:
            if not hasattr(user, "driver_profile"):
                return qs.filter(is_deleted=False, driver__user=user)
            profile = user.driver_profile
            return (
                qs.filter(is_deleted=False)
                .filter(
                    Q(driver__user=user)
                    | Q(
                        state=Booking.BookingState.SEARCHING_DRIVER,
                        trip_events__event_type=RIDE_REQUEST_SENT,
                        trip_events__actor_driver=profile,
                    )
                )
                .distinct()
            )
        return qs.filter(is_deleted=False)

    def perform_create(self, serializer):
        booking = serializer.save(customer=self.request.user, state=Booking.BookingState.PENDING_QUOTE)
        try:
            dispatch_booking.delay(str(booking.id))
        except Exception:
            logger.exception("Async dispatch enqueue failed, falling back to sync dispatch", extra={"booking_id": str(booking.id)})
            # Keep booking creation resilient even if broker/worker is temporarily unavailable.
            dispatch_booking(str(booking.id))

    @action(detail=False, methods=["post"], url_path="fare-estimate")
    def fare_estimate(self, request):
        serializer = FareEstimateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        category = VehicleCategory.objects.get(id=data["vehicle_category_id"], is_deleted=False, active=True)
        from .serializers import _haversine_km

        distance_km = _haversine_km(data["pickup_lat"], data["pickup_lng"], data["drop_lat"], data["drop_lng"])
        helper_charge = Decimal("40.00") if data.get("requires_helper") else Decimal("0.00")
        estimated_fare = max(
            category.minimum_fare,
            category.base_fare + (category.per_km_rate * distance_km) + helper_charge,
        )
        return success_response(
            {
                "vehicle_category_id": str(category.id),
                "distance_km": str(distance_km),
                "estimated_duration_min": int(max(10, float(distance_km) * 4)),
                "estimated_fare": str(estimated_fare),
                "breakdown": {
                    "base_fare": str(category.base_fare),
                    "per_km_rate": str(category.per_km_rate),
                    "helper_charge": str(helper_charge),
                },
            }
        )

    @action(detail=True, methods=["post"], url_path="state-transition")
    def state_transition(self, request, pk=None):
        booking = self.get_object()
        serializer = BookingTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = request.user.role
        target_state = serializer.validated_data["to_state"]
        if role == "customer" and target_state not in {Booking.BookingState.CANCELLED_BY_CUSTOMER}:
            return success_response(
                {"detail": "Customers can only cancel their bookings."},
                message="Forbidden",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        result = transition_booking_state(
            booking=booking,
            to_state=target_state,
            actor=request.user,
            payload=serializer.validated_data.get("payload", {}),
        )
        return success_response({"booking_id": result.booking_id, "state": result.new_state, "seq": result.seq})

    @action(detail=True, methods=["post"], url_path="admin-update-state", permission_classes=[IsAdminRole])
    def admin_update_state(self, request, pk=None):
        return self.state_transition(request, pk)

    @action(detail=True, methods=["get"], url_path="timeline")
    def timeline(self, request, pk=None):
        booking = self.get_object()
        events = booking.trip_events.all()
        return success_response(TripEventSerializer(events, many=True).data)
