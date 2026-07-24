"""
Permissions for the device-facing sync endpoints (Phase 2 design §2.4).

Sync runs with no user logged in; the authenticated principal is a Branch
carried on request.auth by DeviceSyncTokenAuthentication. IsEnrolledDevice
gates push/pull on that, rather than on a user role.
"""
from rest_framework.permissions import BasePermission

from apps.auth_users.models import Branch


class IsEnrolledDevice(BasePermission):
    message = "A valid device sync token is required."

    def has_permission(self, request, view):
        branch = getattr(request, "auth", None)
        return isinstance(branch, Branch) and branch.is_active
