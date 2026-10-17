import hmac
import hashlib
import json
import logging
from decimal import Decimal

from django.conf import settings
from django.http import HttpResponse
from rest_framework import permissions, status, views, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.bookings.models import Booking
from apps.common.api.responses import success_response
from apps.payments.models import Payment
from apps.payments.serializers import PaymentSerializer
from apps.payments.services import (
    create_razorpay_order_service,
    generate_trip_payment_qr_service,
    record_successful_booking_payment,
)

logger = logging.getLogger(__name__)


class RazorpayOrdersView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        amount_paise = request.data.get("amount")
        if not amount_paise:
            return Response({"detail": "amount is required in paise"}, status=status.HTTP_400_BAD_REQUEST)

        currency = request.data.get("currency", "INR")
        receipt = request.data.get("receipt", "")
        notes = request.data.get("notes", {})

        order_data = create_razorpay_order_service(
            amount_paise=amount_paise,
            currency=currency,
            receipt=receipt,
            notes=notes,
        )
        return Response(order_data, status=status.HTTP_200_OK)


class RazorpayWebhookView(views.APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        body = request.body
        webhook_secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", "").strip()

        # If webhook secret is set, verify HMAC SHA256 signature
        if webhook_secret:
            received_signature = request.headers.get("X-Razorpay-Signature", "")
            expected_signature = hmac.new(
                webhook_secret.encode("utf-8"),
                body,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(received_signature, expected_signature):
                logger.warning("Invalid Razorpay webhook signature")
                return HttpResponse("Invalid signature", status=400)

        try:
            event_payload = json.loads(body.decode("utf-8"))
        except Exception:
            return HttpResponse("Invalid JSON", status=400)

        event = event_payload.get("event", "")
        logger.info("Received Razorpay webhook event: %s", event)

        # Handle successful payments
        if event in {"payment.captured", "order.paid", "qr_code.credited"}:
            payment_entity = event_payload.get("payload", {}).get("payment", {}).get("entity", {})
            amount_paise = payment_entity.get("amount", 0)
            amount_inr = Decimal(str(amount_paise / 100)) if amount_paise else Decimal("0")
            notes = payment_entity.get("notes", {})
            booking_id = notes.get("booking_id")
            payment_id = payment_entity.get("id", "")
            method = payment_entity.get("method", "upi")

            if booking_id:
                try:
                    booking = Booking.objects.get(id=booking_id)
                    record_successful_booking_payment(
                        booking=booking,
                        amount=amount_inr or booking.estimated_fare,
                        method=method,
                        transaction_ref=payment_id,
                        gateway_payload=event_payload,
                    )
                    logger.info("Successfully recorded webhook payment for booking %s", booking_id)
                except Booking.DoesNotExist:
                    logger.warning("Webhook booking %s not found", booking_id)

        return HttpResponse("OK", status=200)


class BookingPaymentQrView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response({"detail": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)

        qr_data = generate_trip_payment_qr_service(booking)
        return success_response(qr_data)

    def post(self, request, booking_id):
        # Support POST to trigger QR generation or mark payment received manually by driver
        return self.get(request, booking_id)


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Payment.objects.select_related("booking", "customer").all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ("status", "method", "booking")
    search_fields = ("transaction_ref", "booking__id")
    ordering_fields = ("created_at", "amount")
