from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from apps.addresses.models import Address
from apps.addresses.serializers import AddressSerializer
from apps.bookings.models import Booking
from apps.bookings.serializers import BookingSerializer
from apps.common.api.responses import success_response
from apps.common.permissions.rbac import IsCustomerOrAdmin
from apps.users.serializers import UserSerializer


class CustomerViewSet(viewsets.ViewSet):
    """Own-profile customer APIs. Admins allowed so shared test accounts (super_admin) work in the customer app."""

    permission_classes = [IsAuthenticated, IsCustomerOrAdmin]

    def get_permissions(self):
        if getattr(self, "action", None) == "bookings":
            return [IsAuthenticated()]
        return super().get_permissions()

    def list(self, request):
        return success_response(UserSerializer(request.user).data)

    @action(detail=False, methods=["patch"], url_path="profile")
    def update_profile(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data, message="Profile updated")

    @action(detail=False, methods=["get", "post"], url_path="addresses")
    def addresses(self, request):
        if request.method.lower() == "get":
            queryset = Address.objects.filter(user=request.user, is_deleted=False).order_by("-is_default", "-created_at")
            return success_response(AddressSerializer(queryset, many=True).data)
        serializer = AddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return success_response(serializer.data, message="Address created", status_code=201)

    @action(detail=False, methods=["get"], url_path="bookings")
    def bookings(self, request):
        queryset = Booking.objects.filter(customer=request.user, is_deleted=False).order_by("-created_at")
        return success_response(BookingSerializer(queryset, many=True).data)
