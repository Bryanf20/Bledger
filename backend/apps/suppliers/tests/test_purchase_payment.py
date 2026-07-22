"""
Tests for PurchasePayment / PurchaseViewSet.record_payment -- the fix
for the "no way to update a partial/credit purchase" gap. Self-contained
fixtures, same pattern as apps.suppliers.tests.conftest.
"""
import pytest
from rest_framework.test import APIClient

from apps.auth_users.models import Branch, BledgerUser
from apps.inventory.models import Category, Product
from apps.suppliers.models import Purchase, PurchasePayment, Supplier
from apps.sync.models import OutboxEntry

BRANCH_ID = "HQ"


@pytest.fixture
def branch(db):
    return Branch.objects.create(
        business_name="Tabi Provisions",
        branch_name="Buea Main Branch",
        address="Molyko, Buea",
        phone="677123456",
        deployment_mode="standalone",
        setup_complete=True,
        code="BUE",
    )


@pytest.fixture
def manager_user(db, branch):
    return BledgerUser.objects.create_user(
        branch=branch, name="Manny Manager", username="manager1", role="manager", password="managerpass123"
    )


@pytest.fixture
def cashier_user(db, branch):
    user = BledgerUser.objects.create_user(
        branch=branch, name="Cash Cashier", username="cashier1", role="cashier"
    )
    user.set_pin("1234")
    user.save()
    return user


@pytest.fixture
def category(db):
    return Category.objects.create(branch_id=BRANCH_ID, name="Grains", sort_order=1)


@pytest.fixture
def product(db, category):
    return Product.objects.create(
        branch_id=BRANCH_ID,
        name="Mama Gold rice 5kg",
        category=category,
        unit="bag",
        retail_price=4500,
        stock_level=50,
        low_stock_threshold=5,
    )


@pytest.fixture
def supplier(db):
    return Supplier.objects.create(branch_id=BRANCH_ID, name="Eto'o Supplies")


@pytest.fixture
def manager_client(manager_user):
    client = APIClient()
    client.force_authenticate(user=manager_user)
    return client


@pytest.fixture
def cashier_client(cashier_user):
    client = APIClient()
    client.force_authenticate(user=cashier_user)
    return client


@pytest.fixture
def credit_purchase(db, manager_client, supplier, product):
    """A purchase recorded with amount_paid=0 -- starts as CREDIT, 10,000 XAF total."""
    resp = manager_client.post(
        "/api/v1/purchases/",
        {
            "supplier": str(supplier.id),
            "purchase_date": "2026-07-01",
            "amount_paid": 0,
            "items": [{"product": str(product.id), "quantity": 10, "unit_cost": 1000}],
        },
        format="json",
    )
    assert resp.status_code == 201
    return Purchase.objects.get(pk=resp.data["id"])


@pytest.mark.django_db
def test_record_partial_payment_updates_status_and_balance(manager_client, credit_purchase):
    resp = manager_client.post(
        f"/api/v1/purchases/{credit_purchase.id}/record-payment/",
        {"amount": 4000, "note": "First installment"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["amount_paid"] == 4000
    assert resp.data["payment_status"] == "partial"
    assert resp.data["balance_due"] == 6000
    assert len(resp.data["payments"]) == 1
    assert resp.data["payments"][0]["amount"] == 4000
    assert resp.data["payments"][0]["note"] == "First installment"


@pytest.mark.django_db
def test_second_payment_that_completes_balance_marks_paid(manager_client, credit_purchase):
    manager_client.post(
        f"/api/v1/purchases/{credit_purchase.id}/record-payment/", {"amount": 4000}, format="json"
    )
    resp = manager_client.post(
        f"/api/v1/purchases/{credit_purchase.id}/record-payment/", {"amount": 6000}, format="json"
    )
    assert resp.status_code == 200
    assert resp.data["amount_paid"] == 10000
    assert resp.data["payment_status"] == "paid"
    assert resp.data["balance_due"] == 0
    assert len(resp.data["payments"]) == 2


@pytest.mark.django_db
def test_overpayment_rejected(manager_client, credit_purchase):
    resp = manager_client.post(
        f"/api/v1/purchases/{credit_purchase.id}/record-payment/", {"amount": 15000}, format="json"
    )
    assert resp.status_code == 400
    credit_purchase.refresh_from_db()
    assert credit_purchase.amount_paid == 0


@pytest.mark.django_db
def test_payment_on_fully_paid_purchase_rejected(manager_client, credit_purchase):
    manager_client.post(
        f"/api/v1/purchases/{credit_purchase.id}/record-payment/", {"amount": 10000}, format="json"
    )
    resp = manager_client.post(
        f"/api/v1/purchases/{credit_purchase.id}/record-payment/", {"amount": 1}, format="json"
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_cashier_forbidden(cashier_client, credit_purchase):
    resp = cashier_client.post(
        f"/api/v1/purchases/{credit_purchase.id}/record-payment/", {"amount": 1000}, format="json"
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_record_payment_writes_outbox_entries_for_payment_and_purchase(manager_client, credit_purchase):
    resp = manager_client.post(
        f"/api/v1/purchases/{credit_purchase.id}/record-payment/", {"amount": 2500}, format="json"
    )
    payment_id = resp.data["payments"][0]["id"]

    payment_entry = OutboxEntry.objects.filter(record_id=payment_id).first()
    assert payment_entry is not None
    assert payment_entry.operation == OutboxEntry.INSERT

    purchase_entry = (
        OutboxEntry.objects.filter(record_id=credit_purchase.id).order_by("created_at").last()
    )
    assert purchase_entry is not None
    assert purchase_entry.operation == OutboxEntry.UPDATE


@pytest.mark.django_db
def test_zero_or_negative_amount_rejected(manager_client, credit_purchase):
    resp = manager_client.post(
        f"/api/v1/purchases/{credit_purchase.id}/record-payment/", {"amount": 0}, format="json"
    )
    assert resp.status_code == 400


"""
Covers the fix for: a purchase recorded with amount_paid > 0 must show
that amount in its `payments` list immediately, not just for
installments added afterward via record-payment. Append to
apps/suppliers/tests/test_purchase_payment.py (reuses that file's
fixtures) rather than a new file -- same feature area.
"""


@pytest.mark.django_db
def test_purchase_recorded_with_upfront_payment_creates_initial_payment_row(
    manager_client, supplier, product
):
    resp = manager_client.post(
        "/api/v1/purchases/",
        {
            "supplier": str(supplier.id),
            "purchase_date": "2026-07-05",
            "amount_paid": 6000,
            "items": [{"product": str(product.id), "quantity": 10, "unit_cost": 1000}],
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["amount_paid"] == 6000
    assert resp.data["payment_status"] == "partial"
    assert resp.data["balance_due"] == 4000
    assert len(resp.data["payments"]) == 1
    assert resp.data["payments"][0]["amount"] == 6000
    assert resp.data["payments"][0]["payment_date"] == "2026-07-05"
    assert resp.data["payments"][0]["note"] == "Paid at time of purchase"


@pytest.mark.django_db
def test_purchase_recorded_with_zero_upfront_payment_has_no_initial_payment_row(
    manager_client, credit_purchase
):
    # credit_purchase fixture is created with amount_paid=0 -- confirms
    # the `if amount_paid > 0:` guard actually skips creating a
    # zero-amount payment row (which PurchasePayment.amount, a
    # PositiveIntegerField, wouldn't even accept as 0 gracefully as a
    # *meaningful* payment anyway).
    assert credit_purchase.payments.count() == 0


@pytest.mark.django_db
def test_fully_paid_upfront_then_installment_still_ledger_consistent(manager_client, supplier, product):
    resp = manager_client.post(
        "/api/v1/purchases/",
        {
            "supplier": str(supplier.id),
            "purchase_date": "2026-07-05",
            "amount_paid": 10000,
            "items": [{"product": str(product.id), "quantity": 10, "unit_cost": 1000}],
        },
        format="json",
    )
    assert resp.data["payment_status"] == "paid"
    assert resp.data["balance_due"] == 0
    assert len(resp.data["payments"]) == 1

    purchase = Purchase.objects.get(pk=resp.data["id"])
    # Already fully paid -- a further record-payment call must be
    # rejected, same as the existing test_payment_on_fully_paid_
    # purchase_rejected case, just reached via the upfront path this
    # time instead of two prior record-payment calls.
    second = manager_client.post(
        f"/api/v1/purchases/{purchase.id}/record-payment/", {"amount": 1}, format="json"
    )
    assert second.status_code == 400
    