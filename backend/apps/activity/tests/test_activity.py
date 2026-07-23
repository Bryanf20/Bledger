"""
Activity log (step 8c): role-tiered visibility (managers see key events,
owners see everything, cashiers see nothing) and that the key mutations
actually write a log row.
"""
import pytest
from django.conf import settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.activity.models import ActivityLog
from apps.auth_users.models import Branch, BledgerUser

BRANCH_ID = settings.BRANCH_ID

pytestmark = pytest.mark.django_db


@pytest.fixture
def branch(db):
    return Branch.objects.create(
        business_name="Tabi Provisions", branch_name="Buea", phone="677",
        deployment_mode="standalone", setup_complete=True, code="BUE",
    )


@pytest.fixture
def owner_user(branch):
    return BledgerUser.objects.create_user(
        branch=branch, username="owner1", name="Owner", role="owner", password="ownerpass123"
    )


@pytest.fixture
def manager_user(branch):
    return BledgerUser.objects.create_user(
        branch=branch, username="manager1", name="Manager", role="manager", password="managerpass123"
    )


@pytest.fixture
def cashier_user(branch):
    u = BledgerUser.objects.create_user(branch=branch, username="cashier1", name="Cashier", role="cashier")
    u.set_pin("1234")
    u.save()
    return u


def client_for(user):
    c = APIClient()
    token, _ = Token.objects.get_or_create(user=user)
    c.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return c


def _seed_rows():
    ActivityLog.objects.create(branch_id=BRANCH_ID, action="sale.void", summary="major one", is_major=True)
    ActivityLog.objects.create(branch_id=BRANCH_ID, action="product.update", summary="minor one", is_major=False)


# ---------------------------------------------------------------------------
# Visibility
# ---------------------------------------------------------------------------


def test_cashier_has_no_access(cashier_user):
    assert client_for(cashier_user).get("/api/v1/activity/").status_code == 403


def test_manager_sees_only_major(manager_user):
    _seed_rows()
    resp = client_for(manager_user).get("/api/v1/activity/")
    assert resp.status_code == 200
    actions = {r["action"] for r in resp.data["results"]}
    assert actions == {"sale.void"}


def test_owner_sees_everything(owner_user):
    _seed_rows()
    resp = client_for(owner_user).get("/api/v1/activity/")
    actions = {r["action"] for r in resp.data["results"]}
    assert actions == {"sale.void", "product.update"}


def test_scoped_to_branch(owner_user):
    ActivityLog.objects.create(branch_id="OTHER", action="sale.void", summary="elsewhere", is_major=True)
    resp = client_for(owner_user).get("/api/v1/activity/")
    assert resp.data["count"] == 0


def test_action_filter(owner_user):
    _seed_rows()
    resp = client_for(owner_user).get("/api/v1/activity/?action=product.update")
    assert {r["action"] for r in resp.data["results"]} == {"product.update"}


# ---------------------------------------------------------------------------
# Events get logged
# ---------------------------------------------------------------------------


def test_login_is_logged(owner_user):
    APIClient().post("/api/v1/auth/login/", {"username": "owner1", "password": "ownerpass123"}, format="json")
    assert ActivityLog.objects.filter(action="auth.login", actor=owner_user).exists()


def test_expense_record_is_logged(manager_user):
    client_for(manager_user).post(
        "/api/v1/finances/cashbook/",
        {"direction": "expense", "amount": 5000, "occurred_on": "2026-07-01"},
        format="json",
    )
    entry = ActivityLog.objects.get(action="expense.record")
    assert entry.actor_id == manager_user.id
    assert entry.is_major is True


def test_credit_limit_change_is_logged(manager_user):
    client = client_for(manager_user)
    customer = client.post("/api/v1/customers/", {"name": "Mimi", "phone": "699"}, format="json").data
    client.patch(f"/api/v1/customers/{customer['id']}/", {"credit_limit": 20000}, format="json")
    entry = ActivityLog.objects.get(action="credit.limit_change")
    assert entry.metadata["to"] == 20000


def test_staff_create_is_logged(owner_user):
    client_for(owner_user).post(
        "/api/v1/users/",
        {"name": "New Cashier", "username": "cash2", "role": "cashier", "pin": "4321"},
        format="json",
    )
    assert ActivityLog.objects.filter(action="staff.create").exists()
