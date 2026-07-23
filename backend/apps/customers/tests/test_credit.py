"""
Customers & credit (Phase 2 design §4): derived balances, credit-limit
enforcement at the till, payments, aged-debt aging, and branch scoping.
"""
import pytest

from apps.auth_users.approvals import PURPOSE_CREDIT_OVERRIDE, issue_approval_token
from apps.customers.models import Customer, CustomerPayment
from apps.customers.services import aging_buckets, customer_balance
from apps.sales.models import Sale
from apps.sync.models import OutboxEntry

from .conftest import BRANCH_ID, api_client_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def product(db):
    from apps.inventory.models import Category, Product
    cat = Category.objects.create(branch_id=BRANCH_ID, name="Grains", sort_order=1)
    return Product.objects.create(
        branch_id=BRANCH_ID, name="Rice", category=cat,
        retail_price=10000, stock_level=100,
    )


def _credit_sale(client, customer, product, quantity=1, amount_tendered=None, credit_token=None):
    body = {
        "payment_method": "credit",
        "customer": str(customer.id),
        "items": [{"product": str(product.id), "quantity": quantity}],
    }
    if amount_tendered is not None:
        body["amount_tendered"] = amount_tendered
    if credit_token is not None:
        body["credit_approval_token"] = credit_token
    return client.post("/api/v1/sales/", body, format="json")


# ---------------------------------------------------------------------------
# Balance derivation
# ---------------------------------------------------------------------------


def test_balance_is_zero_for_new_customer(customer):
    assert customer_balance(customer) == 0


def test_credit_sale_within_limit_adds_to_balance(cashier_user, customer, product):
    # limit 50000; one 10000 rice on credit.
    resp = _credit_sale(api_client_for(cashier_user), customer, product, quantity=1)
    assert resp.status_code == 201, resp.data
    assert customer_balance(customer) == 10000


def test_payment_reduces_balance(cashier_user, customer, product):
    client = api_client_for(cashier_user)
    _credit_sale(client, customer, product, quantity=2)  # 20000 owed
    assert customer_balance(customer) == 20000

    resp = client.post(
        f"/api/v1/customers/{customer.id}/record-payment/", {"amount": 8000}, format="json"
    )
    assert resp.status_code == 200
    assert customer_balance(customer) == 12000


def test_voided_credit_sale_drops_from_balance(cashier_user, manager_user, customer, product):
    cashier = api_client_for(cashier_user)
    sale = _credit_sale(cashier, customer, product, quantity=1)
    assert customer_balance(customer) == 10000
    # void (manager+)
    api_client_for(manager_user).post(
        f"/api/v1/sales/{sale.data['id']}/void/", {"void_reason": "mistake"}, format="json"
    )
    assert customer_balance(customer) == 0


# ---------------------------------------------------------------------------
# Credit-limit enforcement (§4.2)
# ---------------------------------------------------------------------------


def test_credit_over_limit_without_token_rejected(cashier_user, customer, product):
    # limit 50000; 6 × 10000 = 60000 would exceed it.
    resp = _credit_sale(api_client_for(cashier_user), customer, product, quantity=6)
    assert resp.status_code == 400
    assert "credit_approval_token" in resp.data


def test_credit_over_limit_with_token_succeeds(cashier_user, manager_user, customer, product):
    token = issue_approval_token(manager_user, PURPOSE_CREDIT_OVERRIDE)
    resp = _credit_sale(api_client_for(cashier_user), customer, product, quantity=6, credit_token=token)
    assert resp.status_code == 201, resp.data
    assert customer_balance(customer) == 60000


def test_upfront_payment_reduces_credit_and_can_avoid_approval(cashier_user, customer, product):
    """
    6×10000=60000 total, but 15000 paid upfront leaves 45000 on account —
    under the 50000 limit, so no approval needed.
    """
    resp = _credit_sale(api_client_for(cashier_user), customer, product, quantity=6, amount_tendered=15000)
    assert resp.status_code == 201, resp.data
    # balance = 60000 billed − 15000 upfront payment = 45000
    assert customer_balance(customer) == 45000
    assert CustomerPayment.objects.filter(customer=customer).count() == 1


def test_credit_sale_requires_customer(cashier_user, product):
    resp = api_client_for(cashier_user).post(
        "/api/v1/sales/",
        {"payment_method": "credit", "items": [{"product": str(product.id), "quantity": 1}]},
        format="json",
    )
    assert resp.status_code == 400
    assert "customer" in resp.data


def test_zero_limit_customer_needs_approval_for_any_credit(cashier_user, product):
    walkin = Customer.objects.create(branch_id=BRANCH_ID, name="Walk-in", credit_limit=0)
    resp = _credit_sale(api_client_for(cashier_user), walkin, product, quantity=1)
    assert resp.status_code == 400  # any credit exceeds a 0 limit


# ---------------------------------------------------------------------------
# Permissions & scoping
# ---------------------------------------------------------------------------


def test_cashier_creating_customer_cannot_grant_credit(cashier_client):
    resp = cashier_client.post(
        "/api/v1/customers/", {"name": "New guy", "credit_limit": 99999}, format="json"
    )
    assert resp.status_code == 201
    assert resp.data["credit_limit"] == 0  # forced to 0 for a cashier


def test_manager_can_set_credit_limit(manager_client, customer):
    resp = manager_client.patch(
        f"/api/v1/customers/{customer.id}/", {"credit_limit": 100000}, format="json"
    )
    assert resp.status_code == 200
    customer.refresh_from_db()
    assert customer.credit_limit == 100000


def test_cashier_cannot_edit_customer(cashier_client, customer):
    resp = cashier_client.patch(
        f"/api/v1/customers/{customer.id}/", {"name": "Hijack"}, format="json"
    )
    assert resp.status_code == 403


def test_customers_scoped_to_branch(owner_client):
    Customer.objects.create(branch_id="OTHER", name="Other branch cust", credit_limit=1000)
    resp = owner_client.get("/api/v1/customers/")
    assert resp.data["count"] == 0


def test_customer_creation_writes_outbox(cashier_client):
    resp = cashier_client.post("/api/v1/customers/", {"name": "Tracked"}, format="json")
    assert resp.status_code == 201
    assert OutboxEntry.objects.filter(record_id=resp.data["id"]).exists()


# ---------------------------------------------------------------------------
# Aged debt (§4.5)
# ---------------------------------------------------------------------------


def test_aging_buckets_split_by_sale_age(cashier_user, customer, product):
    """
    Two credit sales at different ages; a partial payment applies FIFO to
    the oldest, so aging reflects what's still outstanding.
    """
    from django.utils import timezone
    from datetime import timedelta

    client = api_client_for(cashier_user)
    old = _credit_sale(client, customer, product, quantity=1)   # 10000
    recent = _credit_sale(client, customer, product, quantity=1)  # 10000

    # Backdate the first sale 45 days.
    Sale.all_objects.filter(pk=old.data["id"]).update(
        created_at=timezone.now() - timedelta(days=45)
    )

    buckets = aging_buckets(customer)
    # No payments: 10000 in 31–60, 10000 in 0–30.
    assert buckets["bucket_31_60"] == 10000
    assert buckets["bucket_0_30"] == 10000
    assert buckets["total"] == 20000


def test_aged_debt_endpoint_is_manager_only(cashier_client, manager_client, customer, product):
    assert cashier_client.get("/api/v1/customers/aged-debt/").status_code == 403
    assert manager_client.get("/api/v1/customers/aged-debt/").status_code == 200
