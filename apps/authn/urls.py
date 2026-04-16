from django.urls import path
from .api import JWTRefreshView, MeView, OTPRequestView, OTPVerifyView


urlpatterns = [
    path("otp/request", OTPRequestView.as_view(), name="otp-request"),
    path("otp/verify", OTPVerifyView.as_view(), name="otp-verify"),
    path("jwt/refresh", JWTRefreshView.as_view(), name="jwt-refresh"),
    path("me", MeView.as_view(), name="auth-me"),
]
