from decimal import Decimal
import logging

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from apps.common.api.responses import success_response
from apps.common.permissions.rbac import IsAdminRole, IsCustomerOrAdmin, IsDriverOrAdmin
from apps.trip_events.models import TripEvent
from apps.vehicle_categories.models import VehicleCategory
from apps.dispatch.tasks import dispatch_booking

from .models import Booking
from .querysets import bookings_queryset_for_driver_user
from .serializers import BookingSerializer, FareEstimateSerializer
from .services import release_customer_previous_active_trips, transition_booking_state

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
        action = getattr(self, "action", None)
        if action in {"fare_estimate"}:
            return [AllowAny()]
        if action in {"create"}:
            # Drivers (and other roles) may book deliveries on the customer app with the same phone.
            return [IsAuthenticated()]
        if action in {"list", "retrieve", "timeline"}:
            return [IsAuthenticated()]
        if action in {"state_transition"}:
            return [IsAuthenticated()]
        if action in {"admin_update_state"}:
            return [IsAdminRole()]
        return [IsCustomerOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not getattr(user, "is_authenticated", False):
            return qs.none()
        role = getattr(user, "role", None)
        if role is None:
            return qs.none()
        own_as_customer = qs.filter(customer=user, is_deleted=False)
        if role == "customer":
            return own_as_customer
        if role in {"driver", "fleet_driver"}:
            return (own_as_customer | bookings_queryset_for_driver_user(user)).distinct()
        return qs.filter(is_deleted=False)

    def perform_create(self, serializer):
        booking = serializer.save(customer=self.request.user, state=Booking.BookingState.PENDING_QUOTE)
        bid = str(booking.id)
        try:
            release_customer_previous_active_trips(customer=self.request.user, new_booking_id=bid)
        except Exception:
            logger.exception("release_customer_previous_active_trips failed", extra={"booking_id": bid})
        # Run dispatch in-process so drivers get WebSocket offers even when REDIS_URL is set but no Celery
        # worker dequeues `.delay(...)` tasks (common single-dyno Render setups).
        try:
            dispatch_booking.run(bid)
        except Exception:
            logger.exception("In-process dispatch failed; enqueueing Celery fallback", extra={"booking_id": bid})
            try:
                dispatch_booking.delay(bid)
            except Exception:
                logger.exception("Celery enqueue also failed; booking created without dispatch", extra={"booking_id": bid})

    # No JWT parsing: callers may still attach an expired Bearer; AllowAny alone does not skip auth.
    @action(
        detail=False,
        methods=["post"],
        url_path="fare-estimate",
        permission_classes=[AllowAny],
        authentication_classes=[],
    )
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
        target_state = serializer.validated_data["to_state"]
        is_booking_customer = booking.customer_id == request.user.id
        if is_booking_customer and target_state not in {Booking.BookingState.CANCELLED_BY_CUSTOMER}:
            return success_response(
                {"detail": "Customers can only cancel their bookings."},
                message="Forbidden",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        try:
            result = transition_booking_state(
                booking=booking,
                to_state=target_state,
                actor=request.user,
                payload=serializer.validated_data.get("payload", {}),
            )
        except ValueError as exc:
            return success_response(
                {"detail": str(exc)},
                message="Invalid transition",
                status_code=status.HTTP_400_BAD_REQUEST,
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
