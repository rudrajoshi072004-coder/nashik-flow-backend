from __future__ import annotations

import logging
import time
from decimal import Decimal
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.common.api.responses import success_response
from apps.common.permissions.rbac import IsAdminRole
from apps.common.r2 import generate_presigned_url, get_public_url, is_r2_configured, upload_bytes_to_r2
from apps.drivers.models import DriverProfile
from .models import DriverOffer, DriverOfferUsage, Incentive
from .serializers import (
    DriverActiveOfferSerializer,
    DriverOfferSerializer,
    DriverOfferUsageSerializer,
    IncentiveSerializer,
)

logger = logging.getLogger(__name__)


class DriverOfferViewSet(viewsets.ModelViewSet):
    queryset = DriverOffer.objects.filter(is_deleted=False)
    serializer_class = DriverOfferSerializer
    filterset_fields = ("active",)
    search_fields = ("title", "description")
    ordering_fields = ("priority", "start_date", "end_date", "created_at")

    def get_permissions(self):
        if self.action in {"list", "retrieve", "current", "banner"}:
            return [AllowAny()]
        return [IsAdminRole()]

    @action(detail=False, methods=["get"], url_path="current")
    def current(self, request):
        """
        Returns the currently active promotional driver offer for the current driver.
        Calculates remaining commission-free rides for the requesting driver.
        """
        today = timezone.localdate()
        offer = (
            DriverOffer.objects.filter(
                active=True,
                start_date__lte=today,
                end_date__gte=today,
                is_deleted=False,
            )
            .order_by("-priority", "-created_at")
            .first()
        )

        if not offer:
            return success_response(
                {"active": False, "offer": None},
                message="No active driver offer at this time.",
            )

        # Check driver profile if authenticated
        driver_profile = None
        if request.user and request.user.is_authenticated:
            driver_profile = DriverProfile.objects.filter(user=request.user).first()

        completed_free_rides = 0
        if driver_profile:
            completed_free_rides = DriverOfferUsage.objects.filter(
                offer=offer,
                driver=driver_profile,
            ).count()

        remaining_free_rides = max(0, offer.rides_count - completed_free_rides)
        is_exhausted = completed_free_rides >= offer.rides_count

        # Resolve banner URL (relative vs absolute)
        banner_url = offer.banner_url
        if banner_url and banner_url.startswith("/"):
            banner_url = request.build_absolute_uri(banner_url)

        offer_payload = {
            "id": offer.id,
            "title": offer.title,
            "description": offer.description,
            "rides_count": offer.rides_count,
            "commission_rate": offer.commission_rate,
            "valid_days": offer.valid_days,
            "start_date": offer.start_date,
            "end_date": offer.end_date,
            "banner_url": banner_url,
            "remaining_free_rides": remaining_free_rides,
            "completed_free_rides": completed_free_rides,
            "is_exhausted": is_exhausted,
        }

        serializer = DriverActiveOfferSerializer(offer_payload)
        return success_response(
            {"active": True, "offer": serializer.data},
            message="Active driver offer retrieved.",
        )

    @action(detail=True, methods=["post"], url_path="upload-banner")
    def upload_banner(self, request, pk=None):
        """
        Admin endpoint to upload an image banner for an offer.
        Uploads to Cloudflare R2 if configured, or saves binary image to the database.
        """
        offer = self.get_object()
        upload = request.FILES.get("file") or request.FILES.get("banner") or request.FILES.get("image")
        if not upload:
            return Response(
                {"detail": "No image attached. Upload as 'file' or 'banner'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_type = getattr(upload, "content_type", "") or "image/jpeg"
        content_type = content_type.split(";")[0].strip().lower()
        if not content_type.startswith("image/"):
            return Response(
                {"detail": "File must be an image (JPEG, PNG, WebP)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file_bytes = upload.read()
        if len(file_bytes) > 8 * 1024 * 1024:
            return Response(
                {"detail": "Banner image exceeds 8 MB limit."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ext = "png" if "png" in content_type else ("webp" if "webp" in content_type else "jpg")
        r2_key = f"promotions/driver_offers/{offer.id}/banner_{int(time.time())}.{ext}"

        banner_url = ""
        if is_r2_configured():
            uploaded = upload_bytes_to_r2(file_bytes, r2_key, content_type)
            if uploaded:
                pub_url = get_public_url(r2_key)
                banner_url = pub_url or generate_presigned_url(r2_key, expires_in=86400 * 30)

        if not banner_url:
            offer.banner_image = file_bytes
            offer.banner_content_type = content_type
            banner_url = f"/api/v1/driver-offers/{offer.id}/banner/"

        offer.banner_url = banner_url
        offer.save(update_fields=["banner_url", "banner_image", "banner_content_type", "updated_at"])

        return success_response(
            DriverOfferSerializer(offer, context={"request": request}).data,
            message="Banner uploaded successfully.",
        )

    @action(detail=True, methods=["get"], url_path="banner")
    def banner(self, request, pk=None):
        """
        Public endpoint serving the banner image.
        """
        offer = self.get_object()
        if offer.banner_image:
            return HttpResponse(offer.banner_image, content_type=offer.banner_content_type or "image/jpeg")
        if offer.banner_url:
            return HttpResponseRedirect(offer.banner_url)
        return Response({"detail": "No banner available for this offer."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["get"], url_path="usages")
    def usages(self, request, pk=None):
        """
        Returns all redemptions/usages of this offer.
        """
        offer = self.get_object()
        usages_qs = offer.usages.select_related("driver__user", "booking").order_by("-created_at")
        serializer = DriverOfferUsageSerializer(usages_qs, many=True)
        return success_response(serializer.data, message=f"Retrieved {usages_qs.count()} redemptions.")
