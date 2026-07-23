from django.contrib.auth import authenticate, get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.common.permissions.rbac import IsAdminRole

from .firebase_auth import FirebaseAuthError, issue_tokens_for_firebase
from .phone_utils import find_user_by_phone
from .serializers import (
    FirebaseLoginSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PasswordLoginSerializer,
)
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
                role=serializer.validated_data.get("role", "customer"),
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


def _authenticate_phone_password(request, phone: str, password: str):
    user = authenticate(request, username=phone, password=password)
    if user is None:
        existing, _ = find_user_by_phone(get_user_model(), phone)
        if existing:
            user = authenticate(request, username=existing.phone, password=password)
    return user


def _login_tokens_response(user):
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


def _user_has_admin_role(user) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    return user.role in IsAdminRole.allowed_roles


class PasswordLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PasswordLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        password = serializer.validated_data["password"]
        user = _authenticate_phone_password(request, phone, password)
        if user is None:
            return Response({"detail": "Invalid phone or password."}, status=status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            return Response({"detail": "Account disabled."}, status=status.HTTP_403_FORBIDDEN)

        from apps.admin_portal.bootstrap import promote_bootstrap_admin_if_needed

        promote_bootstrap_admin_if_needed(user)
        user.refresh_from_db()

        requested_role = serializer.validated_data.get("role")
        user_model = get_user_model()
        if requested_role == user_model.Role.DRIVER and user.role != user_model.Role.DRIVER:
            user.role = user_model.Role.DRIVER
            user.save(update_fields=["role", "updated_at"])
            from apps.drivers.models import DriverProfile

            DriverProfile.objects.get_or_create(user=user)

        return _login_tokens_response(user)


class AdminLoginView(APIView):
    """Admin portal login: promotes bootstrap phones, then requires an admin role."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PasswordLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        password = serializer.validated_data["password"]
        user = _authenticate_phone_password(request, phone, password)
        if user is None:
            return Response({"detail": "Invalid phone or password."}, status=status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            return Response({"detail": "Account disabled."}, status=status.HTTP_403_FORBIDDEN)

        from apps.admin_portal.bootstrap import promote_bootstrap_admin_if_needed

        promote_bootstrap_admin_if_needed(user)
        user.refresh_from_db()

        if not _user_has_admin_role(user):
            return Response(
                {
                    "detail": (
                        "This account is not an admin. Ask your team to run: "
                        "python manage.py promote_admin YOUR_PHONE"
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return _login_tokens_response(user)


class FirebaseLoginView(APIView):
    """Exchange a Firebase ID token (phone OTP / email / Google) for our JWT."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = FirebaseLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = issue_tokens_for_firebase(
                serializer.validated_data["id_token"],
                role=serializer.validated_data.get("role", "customer"),
                city=serializer.validated_data.get("city", "Nashik"),
            )
        except FirebaseAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        user = payload["user"]
        return Response(
            {
                "access": payload["access"],
                "refresh": payload["refresh"],
                "user": {
                    "id": str(user.id),
                    "phone": user.phone,
                    "email": user.email,
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
