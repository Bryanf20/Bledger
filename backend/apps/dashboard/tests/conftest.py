"""
Fixtures matching the real project's convention (see apps.suppliers.test.conftest
and apps.sales.tests.conftest): force_authenticate rather than token auth,
and a hardcoded BRANCH_ID = "HQ" matching settings.BRANCH_ID, since
apps.core.middleware.DeploymentContextMiddleware stamps request.branch_id
from settings.BRANCH_ID directly — not from Branch's own pk or the user's
branch FK. Branch/BledgerUser rows still get created (a real Branch row
does exist per install) but inventory/sales data is created directly
under BRANCH_ID to guarantee it lands in the same scope the views query.
"""
import pytest
from rest_framework.test import APIClient

from apps.auth_users.models import Branch, BledgerUser
from apps.inventory.models import Category, Product
from apps.sales.models import Sale, SaleLineItem

BRANCH_ID = "HQ"


@pytest.fixture
def branch(db):
    return Branch.objects.create(
        business_name="Tabi Provisions",
        branch_name="Buea Main Branch",
        address="Molyko, Buea",
        phone="677123456",
        deployment_mode=Branch.DEPLOYMENT_STANDALONE,
        setup_complete=True,
        code="BUE",
    )


@pytest.fixture
def owner_user(db, branch):
    return BledgerUser.objects.create_user(
        branch=branch, name="Bea Owner", username="owner1", role="owner", password="ownerpass123"
    )


@pytest.fixture
def manager_user(db, branch):
    return BledgerUser.objects.create_user(
        branch=branch, name="Manny Manager", username="manager1", role="manager", password="managerpass123"
    )


@pytest.fixture
def cashier_user(db, branch):
    user = BledgerUser.objects.create_user(branch=branch, name="Cash Cashier", username="cashier1", role="cashier")
    user.set_pin("1234")
    user.save()
    return user


def api_client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def owner_client(owner_user):
    return api_client_for(owner_user)


@pytest.fixture
def manager_client(manager_user):
    return api_client_for(manager_user)


@pytest.fixture
def cashier_client(cashier_user):
    return api_client_for(cashier_user)


@pytest.fixture
def category(db):
    return Category.objects.create(branch_id=BRANCH_ID, name="Grains", sort_order=1)


@pytest.fixture
def product(db, category):
    return Product.objects.create(
        branch_id=BRANCH_ID,
        name="Rice 5kg",
        category=category,
        unit="bag",
        retail_price=4500,
        stock_level=20,
        low_stock_threshold=5,
    )


@pytest.fixture
def low_stock_product(db, category):
    return Product.objects.create(
        branch_id=BRANCH_ID,
        name="Sugar 2kg",
        category=category,
        unit="bag",
        retail_price=1500,
        stock_level=2,
        low_stock_threshold=5,
    )


@pytest.fixture
def out_of_stock_product(db, category):
    return Product.objects.create(
        branch_id=BRANCH_ID,
        name="Maggi cube",
        category=category,
        unit="pack",
        retail_price=100,
        stock_level=0,
        low_stock_threshold=10,
    )


def make_sale(cashier, product, quantity, unit_price, payment_method=Sale.CASH, when=None, status=Sale.COMPLETED, reference=None, unit_cost=0):
    total = quantity * unit_price
    sale = Sale.objects.create(
        branch_id=BRANCH_ID,
        cashier=cashier,
        payment_method=payment_method,
        subtotal=total,
        total_amount=total,
        status=status,
        reference=reference or f"BLD-2026-{Sale.objects.count() + 1:04d}",
    )
    if when:
        Sale.objects.filter(pk=sale.pk).update(created_at=when)
        sale.refresh_from_db()
    SaleLineItem.objects.create(
        branch_id=BRANCH_ID,
        sale=sale,
        product=product,
        quantity=quantity,
        catalogue_price=unit_price,
        actual_price=unit_price,
        # COGS snapshot (Phase 2 §7A.5) — 0 means "cost unknown".
        unit_cost_at_sale=unit_cost,
        line_total=total,
    )
    return sale
