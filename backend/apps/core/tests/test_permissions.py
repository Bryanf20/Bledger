"""
Tests for apps.core.permissions.

These don't depend on auth_users existing yet — they use a minimal stand-in
for `request.user` with a `.role` attribute, mirroring what BledgerUser
will provide.
"""
from types import SimpleNamespace

import pytest

from apps.core.permissions import IsCashierOrAbove, IsManagerOrOwner, IsOwner


def _request(role=None, authenticated=True):
    user = SimpleNamespace(is_authenticated=authenticated, role=role)
    return SimpleNamespace(user=user)


@pytest.mark.parametrize(
    "permission_class,role,expected",
    [
        (IsCashierOrAbove, "cashier", True),
        (IsCashierOrAbove, "manager", True),
        (IsCashierOrAbove, "owner", True),
        (IsCashierOrAbove, None, False),
        (IsManagerOrOwner, "cashier", False),
        (IsManagerOrOwner, "manager", True),
        (IsManagerOrOwner, "owner", True),
        (IsOwner, "manager", False),
        (IsOwner, "owner", True),
    ],
)
def test_role_permission_thresholds(permission_class, role, expected):
    request = _request(role=role)
    assert permission_class().has_permission(request, view=None) is expected


def test_unauthenticated_user_always_denied():
    request = _request(role="owner", authenticated=False)
    assert IsCashierOrAbove().has_permission(request, view=None) is False


def test_unknown_role_denied():
    request = _request(role="warehouse-intern")
    assert IsCashierOrAbove().has_permission(request, view=None) is False
