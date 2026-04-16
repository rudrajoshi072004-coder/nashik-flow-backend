from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.wallets.models import Wallet, WalletTransaction, ledger_apply


class WalletLedgerTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.driver = user_model.objects.create(phone="+919100000012", role=user_model.Role.DRIVER)
        self.wallet = Wallet.objects.create(driver=self.driver)

    def test_credit_transaction_updates_pending(self):
        tx = ledger_apply(
            wallet=self.wallet,
            tx_type=WalletTransaction.Type.TRIP_EARNING,
            amount=Decimal("250.00"),
            reference_id="trip-1001",
            metadata={"booking_id": "b1"},
        )
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.pending_balance, Decimal("250.00"))
        self.assertEqual(tx.tx_type, WalletTransaction.Type.TRIP_EARNING)
