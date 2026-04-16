from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.common.permissions.rbac import IsAdminRole
from .models import User
from .serializers import UserSerializer


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(is_deleted=False)
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    filterset_fields = ("role", "city", "is_active")
    search_fields = ("phone", "email", "first_name", "last_name")
    ordering_fields = ("created_at",)
