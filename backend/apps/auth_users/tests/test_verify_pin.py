"""
Manager-approval primitive — POST /auth/verify-pin/ and the approval
token/lockout helpers (Phase 2 design §3.2).

The security-critical properties: only a manager+ PIN approves, failures
are uniform (no username/PIN oracle), the target account locks after
repeated failures, the token is short-lived and purpose-scoped, and the
caller's own session is never touched.
"""
import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.auth_users.approvals import (
    FAILURE_LIMIT,
    PURPOSE_CREDIT_OVERRIDE,
    PURPOSE_PRICE_VARIANCE,
    ApprovalError,
    issue_approval_token,
    verify_approval_token,
)
# from apps.auth_users.models import BledgerUser


@pytest.fixture(autouse=True)
def clear_lockout_cache():
    # The lockout counter lives in the process-wide LocMemCache and would
    # otherwise leak between tests.
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def manager_with_pin(manager_user):
    manager_user.set_pin("4321")
    manager_user.save(update_fields=["pin_hash"])
    return manager_user


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


VERIFY_URL = "/api/v1/auth/verify-pin/"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manager_pin_approves_and_returns_token(cashier_user, manager_with_pin):
    resp = client_for(cashier_user).post(
        VERIFY_URL,
        {"username": "manyi", "pin": "4321", "purpose": PURPOSE_PRICE_VARIANCE},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["approved"] is True
    assert resp.data["approver"]["role"] == "manager"
    # The token verifies for the same purpose and yields the approver id.
    approver_id = verify_approval_token(resp.data["approval_token"], purpose=PURPOSE_PRICE_VARIANCE)
    assert approver_id == str(manager_with_pin.id)


@pytest.mark.django_db
def test_owner_pin_also_approves(cashier_user, owner_user):
    owner_user.set_pin("1111")
    owner_user.save(update_fields=["pin_hash"])
    resp = client_for(cashier_user).post(
        VERIFY_URL,
        {"username": "ayuk", "pin": "1111", "purpose": PURPOSE_CREDIT_OVERRIDE},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["approved"] is True


@pytest.mark.django_db
def test_wrong_pin_is_401(cashier_user, manager_with_pin):
    resp = client_for(cashier_user).post(
        VERIFY_URL,
        {"username": "manyi", "pin": "0000", "purpose": PURPOSE_PRICE_VARIANCE},
        format="json",
    )
    assert resp.status_code == 401
    assert "approved" not in resp.data


@pytest.mark.django_db
def test_cashier_pin_cannot_approve(cashier_user):
    """A cashier's own valid PIN must NOT authorise an approval."""
    resp = client_for(cashier_user).post(
        VERIFY_URL,
        {"username": "ambe", "pin": "1234", "purpose": PURPOSE_PRICE_VARIANCE},
        format="json",
    )
    # Uniform 401 — same as a wrong PIN, so role isn't leaked.
    assert resp.status_code == 401


@pytest.mark.django_db
def test_unknown_username_is_uniform_401(cashier_user):
    resp = client_for(cashier_user).post(
        VERIFY_URL,
        {"username": "nobody", "pin": "4321", "purpose": PURPOSE_PRICE_VARIANCE},
        format="json",
    )
    assert resp.status_code == 401


@pytest.mark.django_db
def test_account_locks_after_repeated_failures(cashier_user, manager_with_pin):
    client = client_for(cashier_user)
    for _ in range(FAILURE_LIMIT):
        r = client.post(
            VERIFY_URL,
            {"username": "manyi", "pin": "0000", "purpose": PURPOSE_PRICE_VARIANCE},
            format="json",
        )
        assert r.status_code == 401

    # Now locked — even the CORRECT PIN is refused with 429, so the PIN
    # space can't be exhausted by guessing.
    r = client.post(
        VERIFY_URL,
        {"username": "manyi", "pin": "4321", "purpose": PURPOSE_PRICE_VARIANCE},
        format="json",
    )
    assert r.status_code == 429


@pytest.mark.django_db
def test_success_clears_the_failure_counter(cashier_user, manager_with_pin):
    client = client_for(cashier_user)
    # A few failures, but below the limit...
    for _ in range(FAILURE_LIMIT - 1):
        client.post(VERIFY_URL, {"username": "manyi", "pin": "0000", "purpose": PURPOSE_PRICE_VARIANCE}, format="json")
    # ...then a success resets the count.
    ok = client.post(VERIFY_URL, {"username": "manyi", "pin": "4321", "purpose": PURPOSE_PRICE_VARIANCE}, format="json")
    assert ok.status_code == 200
    # A fresh wrong attempt is a plain 401, not a lockout — counter reset.
    again = client.post(VERIFY_URL, {"username": "manyi", "pin": "0000", "purpose": PURPOSE_PRICE_VARIANCE}, format="json")
    assert again.status_code == 401


@pytest.mark.django_db
def test_invalid_purpose_rejected(cashier_user, manager_with_pin):
    resp = client_for(cashier_user).post(
        VERIFY_URL,
        {"username": "manyi", "pin": "4321", "purpose": "not_a_real_purpose"},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_verify_pin_does_not_touch_caller_session(cashier_user, manager_with_pin):
    """
    Approval happens inside the cashier's session — it must not issue a
    token or otherwise re-authenticate. The cashier can still call a
    normal authenticated endpoint afterward as themselves.
    """
    client = client_for(cashier_user)
    client.post(VERIFY_URL, {"username": "manyi", "pin": "4321", "purpose": PURPOSE_PRICE_VARIANCE}, format="json")
    me = client.get("/api/v1/auth/me/")
    assert me.status_code == 200
    assert me.data["username"] == "ambe"  # still the cashier


@pytest.mark.django_db
def test_anonymous_cannot_call_verify_pin(manager_with_pin):
    resp = APIClient().post(
        VERIFY_URL,
        {"username": "manyi", "pin": "4321", "purpose": PURPOSE_PRICE_VARIANCE},
        format="json",
    )
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Approval token helper
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_token_wrong_purpose_rejected(manager_with_pin):
    token = issue_approval_token(manager_with_pin, PURPOSE_PRICE_VARIANCE)
    with pytest.raises(ApprovalError):
        verify_approval_token(token, purpose=PURPOSE_CREDIT_OVERRIDE)


@pytest.mark.django_db
def test_token_expired_rejected(manager_with_pin):
    token = issue_approval_token(manager_with_pin, PURPOSE_PRICE_VARIANCE)
    # max_age=-1 forces the age check to treat any token as expired.
    with pytest.raises(ApprovalError):
        verify_approval_token(token, purpose=PURPOSE_PRICE_VARIANCE, max_age=-1)


def test_token_tampered_rejected():
    with pytest.raises(ApprovalError):
        verify_approval_token("not.a.real.token", purpose=PURPOSE_PRICE_VARIANCE)


def test_missing_token_rejected():
    with pytest.raises(ApprovalError):
        verify_approval_token("", purpose=PURPOSE_PRICE_VARIANCE)
