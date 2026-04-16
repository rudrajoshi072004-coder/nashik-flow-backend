from django.test import TestCase
from rest_framework.test import APIClient


class OTPAuthTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_request_and_verify_otp(self):
        req = self.client.post("/api/v1/auth/otp/request", {"phone": "+919199999999"}, format="json")
        self.assertEqual(req.status_code, 200)
        otp = req.data["otp_dev_only"]

        verify = self.client.post(
            "/api/v1/auth/otp/verify",
            {"phone": "+919199999999", "otp": otp},
            format="json",
        )
        self.assertEqual(verify.status_code, 200)
        self.assertIn("access", verify.data)
        self.assertIn("refresh", verify.data)
