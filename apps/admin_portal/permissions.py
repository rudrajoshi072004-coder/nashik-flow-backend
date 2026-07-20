from apps.common.permissions.rbac import IsAdminRole

# Reuse existing admin RBAC — no separate portal permission model.
IsPortalAdmin = IsAdminRole
