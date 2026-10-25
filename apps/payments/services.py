import base64
import json
import logging
import os
import time
import urllib.parse
import urllib.request
import uuid
from decimal import Decimal

from django.conf import settings
from apps.bookings.models import Booking
from apps.payments.models import Payment
from apps.trip_events.services import broadcast_event

logger = logging.getLogger(__name__)


def create_razorpay_order_service(
    *,
    amount_paise: int,
    currency: str = "INR",
    receipt: str = "",
    notes: dict | None = None,
) -> dict:
    key_id = getattr(settings, "RAZORPAY_KEY_ID", "").strip()
    key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "").strip()

    if key_id and key_secret:
        try:
            url = "https://api.razorpay.com/v1/orders"
            payload = {
                "amount": int(amount_paise),
                "currency": currency,
                "receipt": receipt or f"rcpt_{amount_paise}_{uuid.uuid4().hex[:6]}",
                "notes": notes or {},
            }
            auth_header = "Basic " + base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": auth_header},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "order_id": data.get("id"),
                    "amount": data.get("amount"),
                    "currency": data.get("currency", "INR"),
                    "key_id": key_id,
                }
        except Exception as e:
            logger.warning("Razorpay order API call failed: %s; falling back to generated order reference", e)

    # Clean fallback for development/sandbox mode
    mock_order_id = f"order_cry_{uuid.uuid4().hex[:14]}"
    return {
        "order_id": mock_order_id,
        "amount": amount_paise,
        "currency": currency,
        "key_id": key_id,
    }


def generate_trip_payment_qr_service(booking: Booking) -> dict:
    key_id = getattr(settings, "RAZORPAY_KEY_ID", "").strip()
    key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "").strip()

    fare = booking.final_fare if booking.final_fare > 0 else booking.estimated_fare
    fare_decimal = Decimal(str(fare))
    amount_paise = max(100, int(fare_decimal * 100))

    # 1. Attempt Razorpay single-use dynamic UPI QR code
    if key_id and key_secret:
        try:
            url = "https://api.razorpay.com/v1/payments/qr_codes"
            payload = {
                "type": "upi_qr",
                "name": f"Carryoo Trip #{str(booking.id)[:8]}",
                "usage": "single_use",
                "fixed_amount": True,
                "payment_amount": amount_paise,
                "description": f"Carryoo trip delivery #{str(booking.id)[:8]}",
                "close_by": int(time.time() + 7200),
                "notes": {
                    "booking_id": str(booking.id),
                    "driver_id": str(booking.driver_id or ""),
                    "amount": str(fare_decimal),
                },
            }
            auth_header = "Basic " + base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": auth_header},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                qr_id = data.get("id") or f"qr_{str(booking.id)[:8]}"
                qr_image_url = data.get("image_url")
                upi_string = data.get("payload_url") or ""
                return {
                    "qr_id": qr_id,
                    "qr_image_url": qr_image_url,
                    "upi_string": upi_string,
                    "amount": float(fare_decimal),
                    "booking_id": str(booking.id),
                    "source": "razorpay_dynamic",
                }
        except Exception as e:
            logger.warning("Razorpay dynamic QR creation failed: %s; using standard UPI intent fallback", e)

    # 2. Standard Bharat UPI Intent QR fallback (accepted by all UPI apps: PhonePe, GPay, Paytm, CRED)
    company_upi = os.getenv("COMPANY_UPI_ID", "carryoo.logistics@icici").strip()
    company_name = "Carryoo Logistics"
    ref = f"CRY{str(booking.id).replace('-', '')[:10]}"
    upi_string = (
        f"upi://pay?pa={company_upi}&pn={urllib.parse.quote(company_name)}"
        f"&am={float(fare_decimal):.2f}&tr={ref}&tn=Delivery%20Payment%20{ref}&cu=INR"
    )
    # Fast, high-uptime vector QR generator
    qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=320x320&data={urllib.parse.quote(upi_string)}"

    return {
        "qr_id": f"qr_upi_{str(booking.id)[:8]}",
        "qr_image_url": qr_image_url,
        "upi_string": upi_string,
        "amount": float(fare_decimal),
        "booking_id": str(booking.id),
        "source": "upi_intent",
    }


def record_successful_booking_payment(
    *,
    booking: Booking,
    amount: Decimal,
    method: str = "upi",
    transaction_ref: str = "",
    gateway_payload: dict | None = None,
) -> Payment:
    gateway_payload = gateway_payload or {}
    tx_ref = transaction_ref or f"tx_{booking.id}_{uuid.uuid4().hex[:8]}"

    payment, created = Payment.objects.update_or_create(
        transaction_ref=tx_ref,
        defaults={
            "booking": booking,
            "customer": booking.customer,
            "method": method,
            "status": Payment.Status.SUCCESS,
            "amount": amount,
            "gateway_payload": gateway_payload,
        },
    )

    # Broadcast instant confirmation to both customer and driver
    confirm_payload = {
        "booking_id": str(booking.id),
        "amount": float(amount),
        "method": method,
        "transaction_ref": tx_ref,
        "status": "success",
        "message": f"Payment of ₹{float(amount):.2f} confirmed successfully!",
    }
    broadcast_event(f"booking_{booking.id}", "payment_received", confirm_payload)
    broadcast_event(f"user_{booking.customer_id}", "payment_received", confirm_payload)
    if booking.driver_id:
        broadcast_event(f"driver_{booking.driver_id}", "payment_received", confirm_payload)
        broadcast_event(f"user_{booking.driver.user_id}", "payment_received", confirm_payload)

    # Trigger driver wallet settlement
    try:
        from apps.wallets.services import record_trip_wallet_settlement
        record_trip_wallet_settlement(booking=booking, payment_method=method)
    except Exception as e:
        logger.warning("Wallet settlement error during payment recording: %s", e)

    return payment
