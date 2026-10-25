from decimal import Decimal
import logging
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.incentives.models import DriverOffer, DriverOfferUsage
from apps.wallets.models import Wallet
from apps.wallet_transactions.models import WalletTransaction

logger = logging.getLogger(__name__)


def get_or_create_driver_wallet(driver_profile) -> Wallet:
    wallet, _ = Wallet.objects.get_or_create(driver=driver_profile)
    return wallet


def record_trip_wallet_settlement(*, booking, payment_method: str = "online") -> WalletTransaction | None:
    """
    Settles driver wallet upon trip completion or payment:
    1. Checks vehicle category platform commission % (defaulting to PLATFORM_COMMISSION_PERCENT).
    2. Checks if an active promotional DriverOffer applies (e.g. 1st 3 rides commission-free).
       - If within offer ride count limit, commission is set to offer's rate (0.00% = 0 commission).
       - Records DriverOfferUsage so the driver can track their used / remaining free rides.
    3. Settles according to payment method:
       - If payment_method is online/upi/upi_qr/card:
         100% of money was collected into Carryoo's account.
         Carryoo deducts platform commission (or 0% during offer).
         Net driver earning (total_fare - commission) is credited to driver's wallet.
       - If payment_method is cash (COD):
         Driver collected 100% physical cash from customer directly.
         Platform commission is debited from driver's wallet balance.
         If commission is 0% (during offer), 0 is debited so driver keeps 100% cash.
    """
    if not booking.driver_id:
        return None

    wallet = get_or_create_driver_wallet(booking.driver)
    total_fare = Decimal(str(booking.final_fare if booking.final_fare > 0 else booking.estimated_fare))
    if total_fare <= Decimal("0"):
        return None

    # 1. Base commission from vehicle category
    base_commission_pct = Decimal(str(getattr(settings, "PLATFORM_COMMISSION_PERCENT", 15.0)))
    if getattr(booking, "vehicle_category", None) and getattr(booking.vehicle_category, "commission_percent", None) is not None:
        base_commission_pct = Decimal(str(booking.vehicle_category.commission_percent))

    # 2. Check for active DriverOffer
    today = timezone.localdate()
    active_offer = (
        DriverOffer.objects.filter(
            active=True,
            start_date__lte=today,
            end_date__gte=today,
            is_deleted=False,
        )
        .order_by("-priority", "-created_at")
        .first()
    )

    applied_offer = None
    offer_ride_number = None
    commission_pct = base_commission_pct

    if active_offer and booking.driver:
        # Check vehicle category applicability
        category_eligible = True
        if active_offer.vehicle_categories.exists():
            category_eligible = bool(
                booking.vehicle_category
                and active_offer.vehicle_categories.filter(id=booking.vehicle_category.id).exists()
            )

        if category_eligible:
            prior_usages = DriverOfferUsage.objects.filter(
                offer=active_offer,
                driver=booking.driver,
            ).count()

            if prior_usages < active_offer.rides_count:
                applied_offer = active_offer
                offer_ride_number = prior_usages + 1
                commission_pct = Decimal(str(active_offer.commission_rate))
                logger.info(
                    "Applying DriverOffer '%s' (Ride %s/%s) to booking %s for driver %s. Commission: %s%%",
                    active_offer.title,
                    offer_ride_number,
                    active_offer.rides_count,
                    booking.id,
                    booking.driver_id,
                    commission_pct,
                )

    breakdown = booking.pricing_breakdown or {}
    toll_charges = Decimal(str(breakdown.get("toll_charges") or "0.00"))
    if toll_charges < Decimal("0.00"):
        toll_charges = Decimal("0.00")

    fare_eligible_for_commission = max(Decimal("0.00"), total_fare - toll_charges)
    commission_amt = (fare_eligible_for_commission * (commission_pct / Decimal("100.0"))).quantize(Decimal("0.01"))
    driver_earning = (total_fare - commission_amt).quantize(Decimal("0.01"))

    saved_commission_amt = Decimal("0.00")
    if applied_offer:
        orig_commission_amt = (fare_eligible_for_commission * (base_commission_pct / Decimal("100.0"))).quantize(Decimal("0.01"))
        saved_commission_amt = max(Decimal("0.00"), orig_commission_amt - commission_amt)

    is_online = payment_method.lower() in {"online", "upi", "upi_qr", "card", "razorpay"}

    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(id=wallet.id)
        balance_before = wallet.current_balance

        if is_online:
            ref_id = f"trip_credit_{booking.id}"
            if WalletTransaction.objects.filter(reference_id=ref_id).exists():
                logger.info("Trip %s already credited to driver wallet", booking.id)
                return None

            tx_type = WalletTransaction.TransactionType.TRIP_EARNING
            amount = driver_earning
            balance_after = balance_before + amount

            wallet.current_balance = balance_after
            wallet.withdrawable_balance = wallet.withdrawable_balance + amount
            wallet.total_credited = wallet.total_credited + amount
            wallet.save(update_fields=["current_balance", "withdrawable_balance", "total_credited", "updated_at"])
        else:
            ref_id = f"trip_cod_commission_{booking.id}"
            if WalletTransaction.objects.filter(reference_id=ref_id).exists():
                logger.info("Trip %s commission already debited from driver wallet", booking.id)
                return None

            tx_type = WalletTransaction.TransactionType.MANUAL_DEBIT
            amount = commission_amt
            balance_after = balance_before - amount

            if amount > Decimal("0.00"):
                wallet.current_balance = balance_after
                wallet.total_debited = wallet.total_debited + amount
                wallet.save(update_fields=["current_balance", "total_debited", "updated_at"])

        tx = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type=tx_type,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            reference_id=ref_id,
            booking=booking,
            metadata={
                "total_fare": str(total_fare),
                "commission_pct": str(commission_pct),
                "base_commission_pct": str(base_commission_pct),
                "commission_amount": str(commission_amt),
                "driver_earning": str(driver_earning),
                "payment_method": payment_method,
                "offer_applied": applied_offer.title if applied_offer else None,
                "offer_ride_number": offer_ride_number,
                "commission_saved": str(saved_commission_amt),
            },
        )

        # Record offer redemption
        if applied_offer and offer_ride_number:
            DriverOfferUsage.objects.get_or_create(
                offer=applied_offer,
                booking=booking,
                defaults={
                    "driver": booking.driver,
                    "ride_number": offer_ride_number,
                    "original_commission_percent": base_commission_pct,
                    "applied_commission_percent": commission_pct,
                    "saved_commission_amount": saved_commission_amt,
                },
            )

        logger.info(
            "Settled driver wallet %s for trip %s: %s %s (new balance %s, offer=%s)",
            wallet.id,
            booking.id,
            tx_type,
            amount,
            balance_after,
            applied_offer.title if applied_offer else "None",
        )
        return tx
