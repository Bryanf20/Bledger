"""
Shared role-based permission classes, used across every app's views.

Roles come from BledgerUser.role (apps.auth_users, not yet scaffolded):
"owner" | "manager" | "cashier". Until that app exists, request.user
won't have a `.role` attribute on the default Django User — these
classes degrade safely (deny) rather than raising AttributeError, so
this module is usable standalone in `core` and only becomes meaningful
once auth_users is built.

Role hierarchy (per design doc Part D §6, §9.1):
    owner    > manager > cashier
    Owner:   full access, including financials and user management.
    Manager: everything except financials reserved for the owner
             (e.g. branch price overrides, viewing other branches).
    Cashier: sales/POS only, read-only on inventory.
"""
from rest_framework.permissions import BasePermission

ROLE_OWNER = "owner"
ROLE_MANAGER = "manager"
ROLE_CASHIER = "cashier"

_ROLE_RANK = {ROLE_CASHIER: 1, ROLE_MANAGER: 2, ROLE_OWNER: 3}


def _user_role(request):
    """Returns the authenticated user's role, or None if absent/unset."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return None
    return getattr(user, "role", None)


def _has_min_role(request, minimum):
    role = _user_role(request)
    if role not in _ROLE_RANK:
        return False
    return _ROLE_RANK[role] >= _ROLE_RANK[minimum]


class IsOwner(BasePermission):
    """Owner-only endpoints: user management, financial reports, etc."""

    message = "This action requires the owner role."

    def has_permission(self, request, view):
        return _has_min_role(request, ROLE_OWNER)


class IsManagerOrOwner(BasePermission):
    """Manager+ endpoints: price overrides, void sales, stock adjustments."""

    message = "This action requires the manager or owner role."

    def has_permission(self, request, view):
        return _has_min_role(request, ROLE_MANAGER)


class IsCashierOrAbove(BasePermission):
    """Any authenticated staff member — the baseline for POS-facing endpoints."""

    message = "This action requires an authenticated staff account."

    def has_permission(self, request, view):
        return _has_min_role(request, ROLE_CASHIER)
