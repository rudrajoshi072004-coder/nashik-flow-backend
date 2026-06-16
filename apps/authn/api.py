from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .serializers import OTPRequestSerializer, OTPVerifySerializer, PasswordLoginSerializer
from .services import request_otp, verify_otp_and_issue_tokens


def _coerce_otp_payload(data) -> dict:
    """Ensure JSON sends strings (some clients send phone as a number)."""
    if data is None:
        return {}
    try:
        out = data.dict() if hasattr(data, "dict") else dict(data)
    except (TypeError, ValueError):
        return {}
    p = out.get("phone")
    if p is not None and not isinstance(p, str):
        out["phone"] = str(p).strip()
    o = out.get("otp")
    if o is not None and not isinstance(o, str):
        out["otp"] = str(o).strip()
    return out


class OTPRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = OTPRequestSerializer(data=_coerce_otp_payload(request.data))
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        otp = request_otp(phone)
        return Response(
            {
                "message": "OTP generated",
                "phone": phone,
                "otp_dev_only": otp,
                "expires_in_seconds": 300,
            },
            status=status.HTTP_200_OK,
        )


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = OTPVerifySerializer(data=_coerce_otp_payload(request.data))
        serializer.is_valid(raise_exception=True)
        try:
            payload = verify_otp_and_issue_tokens(
                serializer.validated_data["phone"],
                serializer.validated_data["otp"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        user = payload["user"]
        return Response(
            {
                "access": payload["access"],
                "refresh": payload["refresh"],
                "user": {
                    "id": str(user.id),
                    "phone": user.phone,
                    "role": user.role,
                    "city": user.city,
                },
            },
            status=status.HTTP_200_OK,
        )


class JWTRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code != status.HTTP_200_OK:
            return response
        access = response.data.get("access") if isinstance(response.data, dict) else None
        if not access:
            return response
        payload = {"access": access}
        refresh = response.data.get("refresh") if isinstance(response.data, dict) else None
        if refresh:
            payload["refresh"] = refresh
        return Response(payload, status=status.HTTP_200_OK)


class PasswordLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PasswordLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        password = serializer.validated_data["password"]
        user = authenticate(request, username=phone, password=password)
        if user is None:
            return Response({"detail": "Invalid phone or password."}, status=status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            return Response({"detail": "Account disabled."}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": str(user.id),
                    "phone": user.phone,
                    "role": user.role,
                    "city": user.city,
                },
            },
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "id": str(user.id),
                "phone": user.phone,
                "role": user.role,
                "city": user.city,
                "name": f"{user.first_name} {user.last_name}".strip(),
            },
            status=status.HTTP_200_OK,
        )
