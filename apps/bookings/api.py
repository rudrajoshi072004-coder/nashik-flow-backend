import logging

from django.db.models import Exists, OuterRef
from django.http import HttpResponse
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from apps.common.api.responses import success_response
from apps.common.permissions.rbac import IsAdminRole, IsCustomerOrAdmin, IsDriverOrAdmin
from apps.trip_events.models import TripEvent
from apps.vehicle_categories.models import VehicleCategory
from apps.dispatch.tasks import dispatch_booking

from .models import Booking, BookingParcelPhoto
from .querysets import bookings_queryset_for_request_user
from .serializers import BookingSerializer, FareEstimateSerializer
from .services import release_customer_previous_active_trips, save_booking_parcel_photo, transition_booking_state

logger = logging.getLogger(__name__)


def _user_can_driver_transition(user, booking: Booking, target_state: str) -> bool:
    """Allow assigned drivers (including users who are also the customer) to progress trips."""
    from apps.drivers.models import DriverProfile

    profile = DriverProfile.objects.filter(user=user, is_deleted=False).first()
    if profile is None:
        return False

    driver_targets = {
        Booking.BookingState.DRIVER_ACCEPTED,
        Booking.BookingState.DRIVER_ARRIVING,
        Booking.BookingState.DRIVER_ARRIVED,
        Booking.BookingState.PICKUP_OTP_PENDING,
        Booking.BookingState.TRIP_STARTED,
        Booking.BookingState.IN_TRANSIT,
        Booking.BookingState.NEARING_DROP,
        Booking.BookingState.COMPLETED,
        Booking.BookingState.CANCELLED_BY_DRIVER,
        Booking.BookingState.PAYMENT_PENDING,
    }
    if target_state not in driver_targets:
        return False

    if booking.state == Booking.BookingState.SEARCHING_DRIVER and target_state == Booking.BookingState.DRIVER_ACCEPTED:
        return True

    return booking.driver_id == profile.id


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
    filterset_fields = ("state", "booking_type", "trip_type", "vehicle_category", "service_zone", "driver")
    search_fields = ("id", "customer__phone", "driver__user__phone", "pickup_address_text", "drop_address_text")
    ordering_fields = ("created_at", "scheduled_at", "estimated_fare")

    def get_permissions(self):
        action = getattr(self, "action", None)
        if action in {"fare_estimate"}:
            return [AllowAny()]
        if action in {"create"}:
            # Drivers (and other roles) may book deliveries on the customer app with the same phone.
            return [IsAuthenticated()]
        if action in {"list", "retrieve", "timeline", "parcel_photo", "update_destination"}:
            return [IsAuthenticated()]
        if action in {"state_transition"}:
            return [IsAuthenticated()]
        if action in {"admin_update_state"}:
            return [IsAdminRole()]
        return [IsCustomerOrAdmin()]

    def get_queryset(self):
        queryset = bookings_queryset_for_request_user(self.request.user, super().get_queryset())
        return queryset.annotate(
            has_pickup_parcel_photo=Exists(
                BookingParcelPhoto.objects.filter(booking_id=OuterRef("pk"), kind=BookingParcelPhoto.Kind.PICKUP)
            ),
            has_drop_parcel_photo=Exists(
                BookingParcelPhoto.objects.filter(booking_id=OuterRef("pk"), kind=BookingParcelPhoto.Kind.DROP)
            ),
        )

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
        try:
            category = VehicleCategory.objects.get(id=data["vehicle_category_id"], is_deleted=False, active=True)
        except VehicleCategory.DoesNotExist:
            raise DRFValidationError({"vehicle_category_id": "Vehicle category not found or inactive."})
        from apps.pricing.trip_pricing import compute_fare_quote

        city = data.get("city") or "Nashik"
        requires_helper = bool(data.get("requires_helper"))
        requested_trip_type = (data.get("trip_type") or "").strip() or None
        quote = compute_fare_quote(
            category=category,
            pickup_lat=data["pickup_lat"],
            pickup_lng=data["pickup_lng"],
            drop_lat=data["drop_lat"],
            drop_lng=data["drop_lng"],
            city=city,
            requested_trip_type=requested_trip_type,
            requires_helper=requires_helper,
        )
        return success_response(
            {
                "vehicle_category_id": str(category.id),
                "distance_km": str(quote.distance_km),
                "distance_source": quote.distance_source,
                "estimated_duration_min": quote.estimated_duration_min,
                "estimated_fare": str(quote.estimated_fare),
                "trip_type": quote.trip_type,
                "resolved_trip_type": quote.resolved_trip_type,
                "service_radius_km": str(quote.service_radius_km),
                "breakdown": quote.breakdown,
            }
        )

    @action(detail=True, methods=["post"], url_path="state-transition")
    def state_transition(self, request, pk=None):
        booking = self.get_object()
        serializer = BookingTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_state = serializer.validated_data["to_state"]
        is_booking_customer = booking.customer_id == request.user.id
        can_driver_transition = _user_can_driver_transition(request.user, booking, target_state)
        if is_booking_customer and not can_driver_transition:
            if target_state not in {Booking.BookingState.CANCELLED_BY_CUSTOMER}:
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

    @action(detail=True, methods=["get", "post"], url_path="parcel-photo")
    def parcel_photo(self, request, pk=None):
        booking = self.get_object()
        kind = (request.data.get("kind") if request.method == "POST" else request.query_params.get("kind") or "").strip()
        if kind not in {BookingParcelPhoto.Kind.PICKUP, BookingParcelPhoto.Kind.DROP}:
            return success_response(
                {"detail": "kind must be pickup or drop."},
                message="Invalid photo",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if request.method == "GET":
            photo = BookingParcelPhoto.objects.filter(booking=booking, kind=kind).first()
            if photo is None:
                return success_response(
                    {"detail": "Parcel photo not found."},
                    message="Not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            if photo.image_url and photo.image_url.startswith("http"):
                from django.http import HttpResponseRedirect
                return HttpResponseRedirect(photo.image_url)
            if photo.file_key:
                from apps.common.r2 import generate_presigned_url
                signed_url = generate_presigned_url(photo.file_key, expires_in=1800)
                if signed_url:
                    from django.http import HttpResponseRedirect
                    return HttpResponseRedirect(signed_url)
            if photo.image:
                return HttpResponse(bytes(photo.image), content_type=photo.content_type or "image/jpeg")
            return success_response(
                {"detail": "Parcel photo content not available."},
                message="Not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if not _user_can_driver_transition(request.user, booking, Booking.BookingState.TRIP_STARTED):
            return success_response(
                {"detail": "Only the assigned driver can upload a parcel photo."},
                message="Forbidden",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        upload = request.FILES.get("photo")
        if upload is None:
            return success_response(
                {"detail": "Attach the parcel photo as photo."},
                message="Invalid photo",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            photo = save_booking_parcel_photo(
                booking=booking,
                kind=kind,
                image_bytes=upload.read(),
                content_type=getattr(upload, "content_type", "") or "image/jpeg",
            )
        except ValueError as exc:
            return success_response(
                {"detail": str(exc)},
                message="Invalid photo",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return success_response(
            {
                "booking_id": str(booking.id),
                "kind": photo.kind,
                "byte_size": photo.byte_size,
                "file_key": photo.file_key,
                "image_url": photo.image_url,
            },
            message="Parcel photo saved",
        )

    @action(detail=True, methods=["post"], url_path="admin-update-state", permission_classes=[IsAdminRole])
    def admin_update_state(self, request, pk=None):
        return self.state_transition(request, pk)

    @action(detail=True, methods=["get"], url_path="timeline")
    def timeline(self, request, pk=None):
        booking = self.get_object()
        events = booking.trip_events.all()
        return success_response(TripEventSerializer(events, many=True).data)

    @action(detail=True, methods=["patch", "post"], url_path="update-destination")
    def update_destination(self, request, pk=None):
        booking = self.get_object()
        terminal_states = {
            Booking.BookingState.COMPLETED,
            Booking.BookingState.CANCELLED_BY_CUSTOMER,
            Booking.BookingState.CANCELLED_BY_DRIVER,
            Booking.BookingState.CANCELLED_BY_ADMIN,
            Booking.BookingState.FAILED,
            Booking.BookingState.REFUNDED,
        }
        if booking.state in terminal_states:
            return success_response(
                {"detail": "Cannot update destination on a finished or cancelled booking."},
                message="Bad Request",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        drop_lat = request.data.get("drop_lat")
        drop_lng = request.data.get("drop_lng")
        drop_address = request.data.get("drop_address_text")

        pickup_lat = request.data.get("pickup_lat")
        pickup_lng = request.data.get("pickup_lng")
        pickup_address = request.data.get("pickup_address_text")

        # In-transit guard: if trip is already in transit, pickup cannot be moved
        in_transit_states = {
            Booking.BookingState.TRIP_STARTED,
            Booking.BookingState.IN_TRANSIT,
            Booking.BookingState.NEARING_DROP,
        }
        if (pickup_lat is not None or pickup_lng is not None) and booking.state in in_transit_states:
            return success_response(
                {"detail": "Parcel is already picked up. Only drop location can be modified in transit."},
                message="Bad Request",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        from django.contrib.gis.geos import Point
        from apps.pricing.trip_pricing import compute_fare_quote
        from apps.trip_events.services import broadcast_event

        cur_pickup_lat = float(pickup_lat) if pickup_lat is not None else booking.pickup_location.y
        cur_pickup_lng = float(pickup_lng) if pickup_lng is not None else booking.pickup_location.x
        cur_drop_lat = float(drop_lat) if drop_lat is not None else booking.drop_location.y
        cur_drop_lng = float(drop_lng) if drop_lng is not None else booking.drop_location.x

        quote = compute_fare_quote(
            category=booking.vehicle_category,
            pickup_lat=cur_pickup_lat,
            pickup_lng=cur_pickup_lng,
            drop_lat=cur_drop_lat,
            drop_lng=cur_drop_lng,
            city="Nashik",
            requested_trip_type=booking.trip_type,
            requires_helper=booking.requires_helper,
        )

        booking.estimated_distance_km = quote.distance_km
        booking.estimated_duration_min = quote.estimated_duration_min
        booking.estimated_fare = quote.estimated_fare
        booking.pricing_breakdown = quote.breakdown

        if drop_lat is not None and drop_lng is not None:
            booking.drop_location = Point(float(drop_lng), float(drop_lat), srid=4326)
            if drop_address:
                booking.drop_address_text = str(drop_address).strip()

        if pickup_lat is not None and pickup_lng is not None:
            booking.pickup_location = Point(float(pickup_lng), float(pickup_lat), srid=4326)
            if pickup_address:
                booking.pickup_address_text = str(pickup_address).strip()

        booking.save()

        update_payload = {
            "booking_id": str(booking.id),
            "drop_lat": booking.drop_location.y,
            "drop_lng": booking.drop_location.x,
            "drop_address_text": booking.drop_address_text,
            "pickup_lat": booking.pickup_location.y,
            "pickup_lng": booking.pickup_location.x,
            "pickup_address_text": booking.pickup_address_text,
            "estimated_fare": str(booking.estimated_fare),
            "estimated_distance_km": str(booking.estimated_distance_km),
            "message": "Trip route updated by customer",
        }

        broadcast_event(f"booking_{booking.id}", "booking_route_updated", update_payload)
        broadcast_event(f"user_{booking.customer_id}", "booking_route_updated", update_payload)
        if booking.driver_id:
            broadcast_event(f"driver_{booking.driver_id}", "booking_route_updated", update_payload)
            broadcast_event(f"user_{booking.driver.user_id}", "booking_route_updated", update_payload)

        return success_response(update_payload, message="Destination updated successfully")

