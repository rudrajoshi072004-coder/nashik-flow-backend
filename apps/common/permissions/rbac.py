from rest_framework.permissions import BasePermission


class HasRole(BasePermission):
    allowed_roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return request.user.role in self.allowed_roles


class IsAdminRole(HasRole):
    allowed_roles = (
        "super_admin",
        "city_manager",
        "support_agent",
        "finance_admin",
        "admin",
        "ops_admin",
    )


class IsCustomerRole(HasRole):
    allowed_roles = ("customer",)


class IsDriverRole(HasRole):
    allowed_roles = ("driver", "fleet_driver")


class IsCustomerOrAdmin(HasRole):
    allowed_roles = ("customer", "super_admin", "city_manager", "support_agent", "finance_admin")


class IsDriverOrAdmin(HasRole):
    allowed_roles = ("driver", "fleet_driver", "super_admin", "city_manager", "support_agent", "finance_admin")


class HasActionPermission(BasePermission):
    required_permission: str | None = None

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True

        permission_code = getattr(view, "required_permission", None) or self.required_permission
        if not permission_code:
            return True

        return request.user.user_roles.filter(
            role__role_permissions__permission__code=permission_code
        ).exists()
