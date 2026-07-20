# Admin Portal API (additive patch)

Mount these routes **without changing** existing customer/driver/mobile endpoints.

## 1. Register app

In Django `INSTALLED_APPS`:

```python
"apps.admin_portal",
```

## 2. Include URLs

In root `urls.py` (alongside existing admin ops routes):

```python
path("api/v1/admin/portal/", include("apps.admin_portal.urls")),
```

## 3. Create an admin user

```bash
python manage.py shell -c "
from apps.users.models import User
u, _ = User.objects.get_or_create(phone='+919999999999', defaults={'role': 'admin'})
u.set_password('YourAdminPass123')
u.role = 'admin'
u.is_staff = True
u.save()
print('Admin ready:', u.phone)
"
```

Or promote existing user:

```python
u = User.objects.get(phone='+919175504996')
u.role = 'admin'
u.is_staff = True
u.save()
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/admin/portal/overview/` | Dashboard KPIs |
| GET | `/api/v1/admin/portal/drivers/` | Driver list |
| GET | `/api/v1/admin/portal/customers/` | Customer list |
| GET/PATCH | `/api/v1/admin/portal/settings/` | Platform settings |
| GET | `/api/v1/admin/portal/audit-logs/` | Audit trail |

All require JWT + admin role (`admin`, `ops_admin`, `super_admin`, staff, or superuser).

Existing `/vehicle-categories/`, `/pricing-rules/`, `/bookings/` remain unchanged for mobile apps.
