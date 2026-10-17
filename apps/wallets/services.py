from decimal import Decimal
import logging
from django.conf import settings
from django.db import transaction

from apps.wallets.models import Wallet
from apps.wallet_transactions.models import WalletTransaction

logger = logging.getLogger(__name__)


def get_or_create_driver_wallet(driver_profile) -> Wallet:
    wallet, _ = Wallet.objects.get_or_create(driver=driver_profile)
    return wallet


def record_trip_wallet_settlement(*, booking, payment_method: str = "online") -> WalletTransaction | None:
    """
    Settles driver wallet upon trip completion or payment:
    - If payment_method is online/upi/upi_qr/card:
      100% of money was collected into Carryoo's account.
      Carryoo deducts platform commission (e.g. 15%).
      Net driver earning (85%) is credited to driver's wallet.
    - If payment_method is cash (COD):
      Driver collected 100% physical cash from customer directly.
      Carryoo's commission (15%) is debited from driver's wallet balance.
    """
    if not booking.driver_id:
        return None

    wallet = get_or_create_driver_wallet(booking.driver)
    total_fare = Decimal(str(booking.final_fare if booking.final_fare > 0 else booking.estimated_fare))
    if total_fare <= Decimal("0"):
        return None

    commission_pct = Decimal(str(getattr(settings, "PLATFORM_COMMISSION_PERCENT", 15.0)))
    commission_amt = (total_fare * (commission_pct / Decimal("100.0"))).quantize(Decimal("0.01"))
    driver_earning = (total_fare - commission_amt).quantize(Decimal("0.01"))

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
                "commission_amount": str(commission_amt),
                "driver_earning": str(driver_earning),
                "payment_method": payment_method,
            },
        )
        logger.info(
            "Settled driver wallet %s for trip %s: %s %s (new balance %s)",
            wallet.id,
            booking.id,
            tx_type,
            amount,
            balance_after,
        )
        return tx
