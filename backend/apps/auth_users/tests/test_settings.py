"""
Settings module core — business config, business-wide preferences, and
staff management (Phase 2 design §7).

Covers the three endpoint groups plus their permission and lockout
guards. Fixtures (branch, owner_user, manager_user, cashier_user) come
from this app's conftest.
"""
import pytest
from rest_framework.test import APIClient

from apps.auth_users.models import BledgerUser, BusinessSettings


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ---------------------------------------------------------------------------
# BusinessSettings singleton
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_business_settings_load_is_a_singleton():
    a = BusinessSettings.load()
    b = BusinessSettings.load()
    assert a.pk == b.pk == 1
    assert BusinessSettings.objects.count() == 1


@pytest.mark.django_db
def test_business_settings_save_always_pins_pk():
    """Creating a second row is impossible — save() forces pk=1."""
    s = BusinessSettings(default_credit_limit=5000)
    s.save()
    s2 = BusinessSettings(default_credit_limit=9999)
    s2.save()  # overwrites row 1 rather than creating a second
    assert BusinessSettings.objects.count() == 1
    assert BusinessSettings.load().default_credit_limit == 9999


# ---------------------------------------------------------------------------
# GET/PATCH /settings/business/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_can_read_business_settings(owner_user):
    resp = client_for(owner_user).get("/api/v1/settings/business/")
    assert resp.status_code == 200
    assert resp.data["business_name"] == "Tabi Provisions"
    assert resp.data["code"] == "BUE"


@pytest.mark.django_db
def test_owner_can_edit_business_details(owner_user, branch):
    resp = client_for(owner_user).patch(
        "/api/v1/settings/business/",
        {"business_name": "Tabi Superstore", "receipt_footer": "Come again!"},
        format="json",
    )
    assert resp.status_code == 200
    branch.refresh_from_db()
    assert branch.business_name == "Tabi Superstore"
    assert branch.receipt_footer == "Come again!"


@pytest.mark.django_db
def test_business_code_is_immutable(owner_user, branch):
    """code is baked into every existing sale reference — read-only."""
    resp = client_for(owner_user).patch(
        "/api/v1/settings/business/", {"code": "XXX"}, format="json"
    )
    assert resp.status_code == 200
    branch.refresh_from_db()
    assert branch.code == "BUE"  # unchanged


@pytest.mark.django_db
def test_blank_business_name_rejected(owner_user):
    resp = client_for(owner_user).patch(
        "/api/v1/settings/business/", {"business_name": "   "}, format="json"
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_manager_cannot_edit_business(manager_user):
    resp = client_for(manager_user).patch(
        "/api/v1/settings/business/", {"business_name": "Nope"}, format="json"
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET/PATCH /settings/preferences/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_reads_default_preferences(owner_user):
    resp = client_for(owner_user).get("/api/v1/settings/preferences/")
    assert resp.status_code == 200
    # Documented defaults.
    assert resp.data["price_deviation_alert_pct"] == 20
    assert resp.data["default_credit_limit"] == 0


@pytest.mark.django_db
def test_owner_edits_preferences(owner_user):
    resp = client_for(owner_user).patch(
        "/api/v1/settings/preferences/",
        {"default_credit_limit": 50000, "default_discount_floor_pct": 10},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["default_credit_limit"] == 50000
    assert BusinessSettings.load().default_discount_floor_pct == 10


@pytest.mark.django_db
def test_discount_over_100_rejected(owner_user):
    resp = client_for(owner_user).patch(
        "/api/v1/settings/preferences/", {"default_discount_floor_pct": 150}, format="json"
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_manager_cannot_edit_preferences(manager_user):
    resp = client_for(manager_user).patch(
        "/api/v1/settings/preferences/", {"default_credit_limit": 1}, format="json"
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Staff management
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_lists_staff(owner_user, manager_user, cashier_user):
    resp = client_for(owner_user).get("/api/v1/users/")
    assert resp.status_code == 200
    usernames = {u["username"] for u in resp.data}
    assert usernames == {"ayuk", "manyi", "ambe"}
    # PIN never leaks — only whether one is set.
    ambe = next(u for u in resp.data if u["username"] == "ambe")
    assert ambe["has_pin"] is True
    assert "pin" not in ambe and "pin_hash" not in ambe


@pytest.mark.django_db
def test_owner_edits_staff_name_and_role(owner_user, cashier_user):
    resp = client_for(owner_user).patch(
        f"/api/v1/users/{cashier_user.id}/",
        {"name": "Ambe Junior", "role": "manager"},
        format="json",
    )
    assert resp.status_code == 200
    cashier_user.refresh_from_db()
    assert cashier_user.name == "Ambe Junior"
    assert cashier_user.role == "manager"


@pytest.mark.django_db
def test_owner_deactivates_staff(owner_user, cashier_user):
    resp = client_for(owner_user).patch(
        f"/api/v1/users/{cashier_user.id}/", {"is_active": False}, format="json"
    )
    assert resp.status_code == 200
    cashier_user.refresh_from_db()
    assert cashier_user.is_active is False


@pytest.mark.django_db
def test_owner_cannot_deactivate_self(owner_user):
    resp = client_for(owner_user).patch(
        f"/api/v1/users/{owner_user.id}/", {"is_active": False}, format="json"
    )
    assert resp.status_code == 409
    owner_user.refresh_from_db()
    assert owner_user.is_active is True


@pytest.mark.django_db
def test_owner_cannot_demote_self(owner_user):
    resp = client_for(owner_user).patch(
        f"/api/v1/users/{owner_user.id}/", {"role": "manager"}, format="json"
    )
    assert resp.status_code == 409
    owner_user.refresh_from_db()
    assert owner_user.role == "owner"


@pytest.mark.django_db
def test_cannot_assign_owner_role(owner_user, cashier_user):
    resp = client_for(owner_user).patch(
        f"/api/v1/users/{cashier_user.id}/", {"role": "owner"}, format="json"
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_owner_resets_cashier_pin(owner_user, cashier_user):
    resp = client_for(owner_user).post(
        f"/api/v1/users/{cashier_user.id}/reset-pin/", {"pin": "9999"}, format="json"
    )
    assert resp.status_code == 200
    cashier_user.refresh_from_db()
    assert cashier_user.check_pin("9999")
    assert not cashier_user.check_pin("1234")


@pytest.mark.django_db
def test_reset_pin_rejects_non_digits(owner_user, cashier_user):
    resp = client_for(owner_user).post(
        f"/api/v1/users/{cashier_user.id}/reset-pin/", {"pin": "12ab"}, format="json"
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_manager_cannot_manage_staff(manager_user, cashier_user):
    assert client_for(manager_user).get("/api/v1/users/").status_code == 403
    assert (
        client_for(manager_user)
        .patch(f"/api/v1/users/{cashier_user.id}/", {"name": "x"}, format="json")
        .status_code
        == 403
    )


@pytest.mark.django_db
def test_cannot_reach_another_branchs_staff(owner_user):
    """Staff detail is scoped to the caller's own branch (feasibility §6)."""
    from apps.auth_users.models import Branch

    other = Branch.objects.create(
        business_name="Rival Shop",
        branch_name="Limbe",
        phone="600",
        deployment_mode=Branch.DEPLOYMENT_STANDALONE,
        setup_complete=True,
        code="LIM",
    )
    outsider = BledgerUser.objects.create_user(
        username="rival", branch=other, role="cashier", pin="0000", name="Rival"
    )
    resp = client_for(owner_user).patch(
        f"/api/v1/users/{outsider.id}/", {"name": "hijacked"}, format="json"
    )
    assert resp.status_code == 404
