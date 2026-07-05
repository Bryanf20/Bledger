"""
Self-contained fixtures for the sales test suite.

ASSUMPTION FLAGGED (same category as the inventory conftest's open
items): BledgerUser.objects.create_user()'s exact kwargs and
Category/Product's exact field names are taken from the design doc
schema, not read from the real auth_users/inventory source. Cross-check
against those modules directly — this is the second time this
assumption has been made without verification; worth actually
confirming once rather than re-flagging a third time on the next app.
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


def api_client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client
