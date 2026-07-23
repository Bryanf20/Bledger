"""
Finances & cashbook (Phase 2 design §7B.2–7B.3): expense/income entries
(editable & deletable, unlike sales), category management, and the
net-profit P&L (gross margin − expenses + income).
"""
import pytest
from rest_framework.test import APIClient

from apps.auth_users.models import Branch, BledgerUser
from apps.finances.models import CashbookEntry, ExpenseCategory
from apps.inventory.models import Category, Product
from apps.sales.models import Sale, SaleLineItem

BRANCH_ID = "HQ"

pytestmark = pytest.mark.django_db


@pytest.fixture
def branch(db):
    return Branch.objects.create(
        business_name="Tabi Provisions", branch_name="Buea", phone="677",
        deployment_mode="standalone", setup_complete=True, code="BUE",
    )


@pytest.fixture
def owner_user(db, branch):
    return BledgerUser.objects.create_user(
        branch=branch, name="Owner", username="owner1", role="owner", password="ownerpass123"
    )


@pytest.fixture
def manager_user(db, branch):
    return BledgerUser.objects.create_user(
        branch=branch, name="Manager", username="manager1", role="manager", password="managerpass123"
    )


@pytest.fixture
def cashier_user(db, branch):
    u = BledgerUser.objects.create_user(branch=branch, name="Cashier", username="cashier1", role="cashier")
    u.set_pin("1234")
    u.save()
    return u


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


def test_seed_defaults_is_idempotent(manager_user):
    client = client_for(manager_user)
    r1 = client.post("/api/v1/finances/expense-categories/seed-defaults/")
    assert r1.status_code == 200
    assert len(r1.data) == 7  # Rent, Transport, Salaries, Utilities, Supplies, Losses/Damage, Other
    # Second call adds nothing.
    r2 = client.post("/api/v1/finances/expense-categories/seed-defaults/")
    assert len(r2.data) == 7
    assert ExpenseCategory.objects.filter(branch_id=BRANCH_ID).count() == 7


def test_cashier_cannot_manage_finances(cashier_user):
    assert client_for(cashier_user).get("/api/v1/finances/cashbook/").status_code == 403
    assert client_for(cashier_user).get("/api/v1/finances/expense-categories/").status_code == 403


# ---------------------------------------------------------------------------
# Cashbook entries — editable & deletable (§7B.2)
# ---------------------------------------------------------------------------


@pytest.fixture
def rent_category(db):
    return ExpenseCategory.objects.create(branch_id=BRANCH_ID, name="Rent")


def test_record_expense(manager_user, rent_category):
    resp = client_for(manager_user).post(
        "/api/v1/finances/cashbook/",
        {"direction": "expense", "category": str(rent_category.id), "amount": 50000,
         "occurred_on": "2026-07-01", "description": "July rent"},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["amount"] == 50000
    assert resp.data["recorded_by"] is not None  # stamped from request.user


def test_expense_is_editable(manager_user, rent_category):
    client = client_for(manager_user)
    e = client.post(
        "/api/v1/finances/cashbook/",
        {"direction": "expense", "category": str(rent_category.id), "amount": 50000, "occurred_on": "2026-07-01"},
        format="json",
    ).data
    # Fix a typo — unlike a sale, an expense can be edited.
    r = client.patch(f"/api/v1/finances/cashbook/{e['id']}/", {"amount": 45000}, format="json")
    assert r.status_code == 200
    assert r.data["amount"] == 45000


def test_expense_is_soft_deletable(manager_user, rent_category):
    client = client_for(manager_user)
    e = client.post(
        "/api/v1/finances/cashbook/",
        {"direction": "expense", "category": str(rent_category.id), "amount": 50000, "occurred_on": "2026-07-01"},
        format="json",
    ).data
    r = client.delete(f"/api/v1/finances/cashbook/{e['id']}/")
    assert r.status_code == 204
    # Soft delete — gone from the default manager, still in all_objects.
    assert not CashbookEntry.objects.filter(pk=e["id"]).exists()
    assert CashbookEntry.all_objects.filter(pk=e["id"]).exists()


def test_income_cannot_have_category(manager_user, rent_category):
    resp = client_for(manager_user).post(
        "/api/v1/finances/cashbook/",
        {"direction": "income", "category": str(rent_category.id), "amount": 1000, "occurred_on": "2026-07-01"},
        format="json",
    )
    assert resp.status_code == 400


def test_entries_scoped_to_branch(manager_user):
    other_cat = ExpenseCategory.objects.create(branch_id="OTHER", name="Rent")
    CashbookEntry.objects.create(branch_id="OTHER", direction="expense", category=other_cat, amount=1, occurred_on="2026-07-01")
    resp = client_for(manager_user).get("/api/v1/finances/cashbook/")
    assert resp.data["count"] == 0


# ---------------------------------------------------------------------------
# Net-profit P&L (§7B.3)
# ---------------------------------------------------------------------------


def _completed_sale(cashier, product, qty, unit_price, unit_cost):
    total = qty * unit_price
    sale = Sale.objects.create(
        branch_id=BRANCH_ID, cashier=cashier, payment_method=Sale.CASH,
        subtotal=total, total_amount=total, status=Sale.COMPLETED,
        reference=f"BLD-BUE-2026-{Sale.objects.count() + 1:04d}",
    )
    SaleLineItem.objects.create(
        branch_id=BRANCH_ID, sale=sale, product=product, quantity=qty,
        catalogue_price=unit_price, actual_price=unit_price,
        unit_cost_at_sale=unit_cost, line_total=total,
    )
    return sale


def test_pnl_net_profit_math(owner_user, cashier_user, rent_category):
    cat = Category.objects.create(branch_id=BRANCH_ID, name="Grains", sort_order=1)
    product = Product.objects.create(branch_id=BRANCH_ID, name="Rice", category=cat, retail_price=4500, stock_level=50)

    # Sell 10 @ 4500, cost 3000 → gross margin 15000.
    _completed_sale(cashier_user, product, 10, 4500, 3000)
    # Expense: 5000 rent today. Income: 1000 non-sale.
    from django.utils import timezone
    today = timezone.localdate().isoformat()
    client = client_for(owner_user)
    client.post("/api/v1/finances/cashbook/", {"direction": "expense", "category": str(rent_category.id), "amount": 5000, "occurred_on": today}, format="json")
    client.post("/api/v1/finances/cashbook/", {"direction": "income", "amount": 1000, "occurred_on": today}, format="json")

    resp = client.get("/api/v1/finances/pnl/?period=today")
    assert resp.status_code == 200
    assert resp.data["gross_margin"] == 15000
    assert resp.data["total_expenses"] == 5000
    assert resp.data["total_income"] == 1000
    # net = 15000 − 5000 + 1000 = 11000
    assert resp.data["net_profit"] == 11000
    assert resp.data["expenses_by_category"][0]["total"] == 5000


def test_pnl_is_owner_only(manager_user):
    assert client_for(manager_user).get("/api/v1/finances/pnl/").status_code == 403
