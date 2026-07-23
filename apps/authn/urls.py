from django.urls import path
from .api import (
    AdminLoginView,
    FirebaseLoginView,
    JWTRefreshView,
    MeView,
    OTPRequestView,
    OTPVerifyView,
    PasswordLoginView,
)


urlpatterns = [
    path("login/password", PasswordLoginView.as_view(), name="auth-password-login"),
    path("login/admin", AdminLoginView.as_view(), name="auth-admin-login"),
    path("firebase/verify", FirebaseLoginView.as_view(), name="auth-firebase-verify"),
    path("otp/request", OTPRequestView.as_view(), name="otp-request"),
    path("otp/verify", OTPVerifyView.as_view(), name="otp-verify"),
    path("jwt/refresh", JWTRefreshView.as_view(), name="jwt-refresh"),
    path("me", MeView.as_view(), name="auth-me"),
]
