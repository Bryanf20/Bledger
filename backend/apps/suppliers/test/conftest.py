"""
Self-contained fixtures for the suppliers test suite — same pattern as
apps.sales.tests.conftest (which itself flags the create_user()/field
assumption; see that module's docstring and the project's open items).
"""
import pytest
from rest_framework.test import APIClient

from apps.auth_users.models import Branch, BledgerUser
from apps.inventory.models import Category, Product

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
        bulk_price=4000,
        bulk_min_qty=12,
        stock_level=50,
        low_stock_threshold=5,
    )


@pytest.fixture
def second_product(db, category):
    return Product.objects.create(
        branch_id=BRANCH_ID,
        name="Sugar 1kg",
        category=category,
        unit="bag",
        retail_price=900,
        stock_level=10,
        low_stock_threshold=5,
    )


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
